# I2 Library backend — operator setup guide

Authoritative steps for bringing Feature 3 (the OpenPose Library +
ComfyUI bridge + multi-operator concurrency) online on a fresh
workstation. Spec: `.gov/spec/openrepose_library_v0_1.md`.
Implementation: WP-I2-001..008 in `.gov/workflow/` (active +
archive subfolders).

The library is **opt-in**. With `Settings.library_db_url` empty,
OpenRepose runs Feature 1 + Feature 2 exactly as before; library
commands return a structured "library subsystem is disabled" error and
no pool / migration code touches the network.

## 1. PostgreSQL backend

Pick one path. Both produce a Postgres 16+ instance reachable on the
operator's machine.

### 1a. Docker (recommended for first install)

```powershell
# From the repo root:
docker compose up -d postgres
```

This launches `openrepose-postgres` using the `docker-compose.yml`
shipped in the repo (postgres:16-alpine, healthcheck, named
`openrepose_pgdata` volume). Defaults match the example DSN:

- user: `openrepose`
- password: `openrepose`
- db: `openrepose`
- port: `5432`

Override via `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `POSTGRES_PORT`) when sharing the workstation with
other Postgres consumers.

Stop with `docker compose down`; wipe the volume with
`docker compose down -v`.

### 1b. Native install

Install PostgreSQL ≥ 16 from your platform's package manager (Windows:
the EnterpriseDB installer; macOS: `brew install postgresql@16`; Linux
distros via apt / dnf / pacman). Create the database + user:

```bash
sudo -u postgres psql -c "CREATE USER openrepose WITH PASSWORD 'openrepose';"
sudo -u postgres psql -c "CREATE DATABASE openrepose OWNER openrepose;"
```

The migrator runs `CREATE EXTENSION IF NOT EXISTS` for `uuid-ossp`,
`pg_trgm`, `unaccent`. On most distros these ship with the standard
postgres package (`postgresql-contrib` on Debian/Ubuntu).

## 2. OpenRepose settings

Open OpenRepose, go to **Options** → **Library** section, set:

- **Library DB URL**: `postgresql://openrepose:openrepose@localhost:5432/openrepose`
  (matches the docker-compose defaults above; substitute when using a
  different cluster). Stored as a password field — never echoed to the
  log file or to the `dump_settings` LLM command (the dispatcher
  redacts the password before returning).
- **Library root**: blank → defaults to `<export_folder>/library/`.
  Set explicitly when you want library files on a different drive.
- **Operator slug**: blank → falls back to the OS username. Set when
  multiple operators share the workstation under one user account.

Click **Apply settings**. OpenRepose persists to
`<AppConfigLocation>/openrepose/settings.json` at schema_version 2;
older v1 files migrate forward in place on next launch.

## 3. First launch

Restart OpenRepose. Watch the log for:

```
OK   library.migrate: applied=1
OK   app.start: ... library_connected=yes
```

Then verify via the LLM control surface (any HTTP-capable client; the
inbox channel works too):

```powershell
# Enable HTTP first if you haven't:
.\openrepose serve --http-port 8765

# Check schema:
curl -X POST http://localhost:8765/command `
  -H "Content-Type: application/json" `
  -d '{"command":"dump_library_schema"}'
```

Expected response:

```json
{
  "command": "dump_library_schema",
  "status": "ok",
  "payload": {
    "schema_version": 1,
    "tables": ["entry_tags","library_entries","notes","prompts",
               "schema_version","story_beats","tags"],
    "functions": ["library_search"],
    "ddl_hash": "<16-hex>"
  }
}
```

Snapshot the empty Library tab to confirm GUI wiring:

```powershell
curl -X POST http://localhost:8765/command `
  -H "Content-Type: application/json" `
  -d '{"command":"snapshot","target":"library_search_results"}'
```

Look at the returned `out_path` — should be a PNG showing the "no
entries" placeholder. Repeated registers + searches will populate it.

## 4. ComfyUI custom node

Install the bridge — see `.product/comfyui-bridge/README.md` for
operator-side details. Summary:

```powershell
# Symlink (Windows, run elevated):
New-Item -ItemType SymbolicLink `
  -Path  "<ComfyUI>\custom_nodes\openrepose-bridge" `
  -Value "<repo>\.product\comfyui-bridge"
```

Restart ComfyUI. The node appears under the **OpenRepose** category as
"OpenRepose Bridge (Save + Register)". Drop it where your normal
`SaveImage` node lives, set the `avatar_slug` input (e.g. `aeri`) and
optional `tags`, and run a workflow. Each successful image save
auto-registers a library entry in OpenRepose.

If OpenRepose is not running when ComfyUI saves an image, the bridge
logs `WARN openrepose_bridge.post_failed` and continues; no image
loss. Re-running the same workflow with OpenRepose running picks up
the next save.

## 5. Multi-operator workflow

Multiple operators on the same workstation can share the library.
Each operator:

1. Sets a distinct **Operator slug** in Options. The slug lands in
   `library_entries.created_by` and appears in the GUI lock indicator
   when another operator currently holds a row.
2. Connects to the same `library_db_url`.
3. Edits independent entries freely. Concurrent edits to the same
   entry — `update_library_entry` or `delete_library_entry` — surface
   a structured error containing `retry_after=5` and add the entry to
   `state.library.locked_entries` for the GUI lock badge.

Schema migrations are protected by a session-scope advisory lock
(`pg_advisory_lock(0x0FEED053)`); a second OpenRepose instance
starting concurrently waits, then sees zero pending migrations after
the first commits. No double-apply risk.

## 6. Backup / restore

Filesystem half (`outputs/library/<entry-uuid>/`):

```powershell
# robocopy is preferred on Windows for large libraries:
robocopy outputs\library backup\library /MIR
```

Database half:

```bash
pg_dump --format=custom --file=backup/library.dump openrepose
```

Restore on a fresh workstation:

```bash
pg_restore --dbname=openrepose backup/library.dump
robocopy backup\library outputs\library /MIR  # restore filesystem half
```

The pg_dump round-trip (entries + tags + prompts + story_beats +
notes) is verified by
`.product/tests/test_library_pg_dump_restore.py`. The filesystem half
is independent from the DB; lost files render as labeled placeholders
in the Library tab and the `library_entry` snapshot target.

## 7. Smoke test checklist (post-install)

Run through this once after the initial install. Each line maps to a
spec promotion guard:

- [ ] `dump_library_schema` returns `schema_version=1` and the
      expected 7 tables + `library_search` function.
- [ ] `register_library_entry` (via curl or the ComfyUI bridge)
      returns an `entry_id`; the corresponding folder appears under
      the configured library root.
- [ ] `library_search` with the entry's title returns it (rank ≥ 0.4).
- [ ] `set_library_tags` with `replace=true` keeps `auto:` smart tags
      while replacing manual tags.
- [ ] Two operator slugs editing different entries simultaneously
      both succeed; editing the same entry second yields the locked
      error message with `retry_after`.
- [ ] `snapshot library_entry` and `snapshot library_search_results`
      both produce non-empty PNGs in `outputs/.runtime/snapshots/`.
- [ ] `pg_dump` + `pg_restore` round-trip preserves every entry, tag,
      prompt revision, story beat, and note byte-for-byte.

When all seven items check out, the WP-I2-008 promotion guard for the
spec is satisfied and Feature 3 can be promoted from `DRAFT` to
`STABLE` in a follow-up commit.
