# WP-I0-002 - LLM Control Surface

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: DONE
- **Iteration**: I0
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` sections "LLM Control Surface", "Mechanical Log Format"
- **Linked Test Suite**: `.product/tests/test_state_file.py`, `.product/tests/test_log_format.py`, `.product/tests/test_command_handlers.py`, `.product/tests/test_http_channel.py`, `.product/tests/test_inbox_channel.py`
- **Linked Check Script**: `N/A` (use `pytest`)

## Intent

Build the headless command + state + log surface that any LLM agent uses to drive OpenRepose without provider-specific code. Three pieces: (1) the atomic-write `state.json` that always reflects current app state; (2) the mechanical log format with stdout + rolling file sinks; (3) the command handlers reachable via either an opt-in HTTP localhost endpoint or an opt-in file-watch inbox. No GUI; everything is testable headlessly.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001
- **Successor(s)**: WP-I0-003, WP-I0-004
- **Blocks**: WP-I0-003, WP-I0-004
- **Blocked-By**: WP-I0-001 (rig + rotation must exist for command handlers to call into)
- **Related**: none

## Linked Requirements / Spec Sections

- LLM Control Surface (state.json schema, command schema, channel A HTTP, channel B file-watch)
- Mechanical Log Format (four shapes: OK / WARN / ERR / DBG; dotted op namespace; stdout + rolling file sink)

## Reality Boundary

- **Real Seam**: real `state.json` written atomically on every command; real HTTP server bound to `127.0.0.1:8765` when enabled; real file-watch on the inbox folder; real command dispatch into the WP-I0-001 rig/rotation/serialize functions.
- **User-Visible Win**: an LLM in a separate process can `POST /command {"command": "import_portrait", "path": "...", "avatar_slug": "aeri"}` and observe `state.json` update plus log lines appearing in `target/logs/openrepose-YYYYMMDD.log`. Same outcome by dropping a JSON file in `outputs/.runtime/inbox/`.
- **Proof Target**: pytest suite passes; one manual test where a curl POST drives the app from `import_portrait` through `set_yaw_bin` to `export_single` and the resulting JSON file is at the expected path.
- **Allowed Temporary Fallbacks**: `snapshot` command can return a typed `NotImplemented` error in this WP (the snapshot subsystem ships in WP-I0-003); state.json records the rejection; the command channel itself works.
- **Promotion Guard**: `snapshot` returning NotImplemented is allowed only until WP-I0-003 is `DONE`. WP-I0-003 removes the fallback.

## In Scope

- `.product/src/openrepose/state.py` — `AppState` class; atomic `write_state(state, path)`; bounded retention on `exports`/`snapshots`/`errors` arrays.
- `.product/src/openrepose/log.py` — log emitter with the four shapes; sinks to stdout, rolling file under `target/logs/`, and an in-memory ring buffer the GUI will read in WP-I0-004.
- `.product/src/openrepose/commands.py` — command schema validation (typed `Command` subclasses), dispatch, error handling. Subclasses: `ImportPortrait`, `SetYaw`, `SetYawBin`, `ExportSingle`, `ExportBatch`, `Snapshot`, `DumpRig`, `DumpState`, `ClearOutputs`.
- `.product/src/openrepose/channels/http.py` — opt-in HTTP server (uses `http.server` from stdlib; no Flask/FastAPI for v0.1). Bound to `127.0.0.1` only.
- `.product/src/openrepose/channels/inbox.py` — file-watch inbox using `watchdog` (or polling fallback). Processes JSON files in mtime order, one at a time, moves to `processed/` with `<status>` annotation.
- `.product/src/openrepose/app.py` — top-level `App` class that wires state + log + channels + command dispatch together. Provides `run_headless()` for the CLI.
- `.product/src/openrepose/cli.py` — extend with `serve` subcommand: `python -m openrepose.cli serve [--http-port 8765] [--inbox]`.
- `.product/tests/test_state_file.py` — atomic-write race tests, schema validation, retention bounds.
- `.product/tests/test_log_format.py` — exact format compliance for each shape; key=value parser round-trips.
- `.product/tests/test_command_handlers.py` — each command type validates inputs, dispatches correctly, updates state, emits log lines.
- `.product/tests/test_http_channel.py` — server starts, accepts a command, returns state, returns log; rejects requests not from 127.0.0.1.
- `.product/tests/test_inbox_channel.py` — drop file -> processed; processed file in correct location with correct status; preserves order on multiple drops.

## Out Of Scope

- GUI of any kind.
- Snapshot subsystem (handled in WP-I0-003).
- Authentication / TLS on the HTTP channel; single-user local-only is sufficient for v0.1.
- Concurrent command execution; commands serialize through a single worker.
- Network-level command channels (over LAN, over WAN).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I0-002-llm-control-surface.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/state.py` (NEW)
- `.product/src/openrepose/log.py` (NEW)
- `.product/src/openrepose/commands.py` (NEW)
- `.product/src/openrepose/channels/__init__.py` (NEW)
- `.product/src/openrepose/channels/http.py` (NEW)
- `.product/src/openrepose/channels/inbox.py` (NEW)
- `.product/src/openrepose/app.py` (NEW)
- `.product/src/openrepose/cli.py` (extended with `serve` subcommand)
- `.product/tests/test_state_file.py` (NEW)
- `.product/tests/test_log_format.py` (NEW)
- `.product/tests/test_command_handlers.py` (NEW)
- `.product/tests/test_http_channel.py` (NEW)
- `.product/tests/test_inbox_channel.py` (NEW)

### Build / Output

- `pyproject.toml` (add `watchdog` to dependencies)
- `target/test-artifacts/WP-I0-002/`
- `target/logs/` (created at runtime; gitignored)
- `outputs/.runtime/` (created at runtime; gitignored)

## Risks And Dependencies

- **Risk**: `watchdog` differs in behavior across platforms. **Mitigation**: pin to a known-good version; provide a polling fallback for environments where the native backend fails.
- **Risk**: HTTP server thread interferes with main thread on app shutdown. **Mitigation**: server runs on a daemon thread; clean shutdown in `App.stop()`.
- **Dependency**: WP-I0-001 must be DONE so command handlers have rig/rotation/serialize functions to call.

## Definition Of Done

- [ ] `from openrepose.app import App; app = App()` constructs without error.
- [ ] `app.handle_command({"command": "import_portrait", "path": "<fixture>", "avatar_slug": "aeri"})` updates `state.json` to `rig.status="ok"`.
- [ ] `state.json` writes are atomic (verified by stress test reading the file repeatedly during writes; never gets a malformed JSON).
- [ ] All four log shapes emit correctly to stdout AND to `target/logs/openrepose-<date>.log`.
- [ ] Log shape validator accepts the four shapes and rejects malformed lines (used in test).
- [ ] HTTP channel: `app.start_http(port=8765)`; `curl -X POST http://127.0.0.1:8765/command -d '{...}'` receives 200 + JSON response; non-127.0.0.1 origin rejected.
- [ ] Inbox channel: dropping `cmd.json` into `outputs/.runtime/inbox/` causes the command to execute; result lands in `outputs/.runtime/processed/cmd.ok.json` (or `.err.json`).
- [ ] `pytest .product/tests/test_state_file.py .product/tests/test_log_format.py .product/tests/test_command_handlers.py .product/tests/test_http_channel.py .product/tests/test_inbox_channel.py` returns zero failures.
- [ ] No use of forbidden yaw phrases anywhere in this WP's code; verified by grep test.
- [ ] `target/test-artifacts/WP-I0-002/pytest_results.xml` saved.
- [ ] Manual run: `python -m openrepose.cli serve --http-port 8765 --inbox`, drive through `import_portrait` -> `set_yaw_bin "her-right 30"` -> `export_single`; verify `outputs/aeri/.../aeri_yaw_her-right-30.json` exists and parses.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Headless end-to-end: import -> set_yaw_bin -> export_single (no GUI). Asserts files appear at expected paths.
- [ ] State.json reflects each command in order; `last_command.status` transitions from `in_progress` to `ok`.
- [ ] Log file contains one OK line per successful command, one ERR line per failed command.

### Code Correctness Tests
- [ ] `Command.from_json(...)` typed validation: each subclass rejects missing/invalid fields with a structured error.
- [ ] State retention bounds: after 200 exports, `state.json` `exports` array has exactly 100 entries (FIFO).
- [ ] Log line parser round-trips through emit -> stdout -> parse without loss.

### Red-Team / Abuse Tests
- [ ] HTTP channel refuses connections from non-127.0.0.1 origins (test by binding to 127.0.0.1 and trying to connect via the host's external IP; should fail).
- [ ] Malformed JSON in inbox file: moved to `processed/<file>.err.json` with structured error; app continues.
- [ ] Command containing a forbidden yaw phrase (e.g. `"image-right 30"`) rejected with `OpenReposeForbiddenTerminologyError`.
- [ ] Concurrent commands serialize correctly; no race condition on `state.json` (verified by spawning 10 inbox files at once).

### Performance / Reliability Tests
- [ ] HTTP latency for a `set_yaw_bin` command under 50ms on the test machine.
- [ ] State.json write under 5ms on the test machine.

## Rollback Plan

- Files to revert: NEW files listed under Expected Files Touched.
- Files to keep: this WP file (move to archive with status `CANCELLED`).
- Recovery command: `git restore --staged .product/; git checkout -- .product/ pyproject.toml`.

## Decisions Log

- `2026-05-02`: chose stdlib `http.server` over Flask/FastAPI for the HTTP channel. Reason: zero dependencies, single-user local server, the app is not exposed publicly. Tradeoff: less ergonomic than FastAPI but the surface is tiny (3 endpoints).
- `2026-05-02`: file-watch inbox uses `watchdog` with polling fallback. Reason: native filesystem events on Windows are well-supported by watchdog; polling fallback covers WSL / network drives.

## Fallback Register

- **Path**: command handler for `snapshot` returns `NotImplementedError` until WP-I0-003 ships.
- **Required Label In Code/UI**: log line `WARN snapshot.unimplemented: subsystem=pending; wp=WP-I0-003`. Response payload includes `{"status": "error", "code": "SNAPSHOT_NOT_IMPLEMENTED"}`.
- **Successor / Debt Owner**: WP-I0-003.
- **Exit Condition To Remove**: WP-I0-003 reaches `DONE`.

## Change Ledger

- **What Became Real**:
  - Mechanical log emitter (`log.py`): four exact line shapes (OK/WARN/ERR/DBG), op-namespace validation (lowercase dotted), key-value formatting with quote-on-spaces, bool->yes/no, sinks to stdout + rolling per-day file under `target/logs/` + in-memory ring buffer.
  - Atomic state file (`state.py`): `AppState` dataclass mirroring the spec schema; `write()` does temp-file + `os.replace` with retry on Windows `PermissionError`; bounded retention (100 entries) on `exports`/`snapshots`/`errors` arrays; lifecycle helpers `begin_command`/`end_command`.
  - Command schema and dispatcher (`commands.py`): typed `CommandResult`, registered handlers for all 9 commands (`import_portrait`, `set_yaw`, `set_yaw_bin`, `export_single`, `export_batch`, `snapshot`, `dump_rig`, `dump_state`, `clear_outputs`); single-flight serialized through a per-app lock; structured error payloads with exception type names; `snapshot` returns `NotImplementedError` per WP-I0-003 fallback.
  - HTTP localhost channel (`channels/http.py`): stdlib `http.server`-based, bound to `127.0.0.1` exclusively, three endpoints (`POST /command`, `GET /state`, `GET /log?lines=N`); rejects non-127.0.0.1 origins with 403; no Flask/FastAPI dependency.
  - File-watch inbox channel (`channels/inbox.py`): polling-based (no `watchdog` dependency for v0.1), processes `*.json` files in mtime order, moves to `processed/<stem>.<ok|err>.json` with the original command + structured result; auto-creates inbox/processed dirs.
  - Top-level `App` class (`app.py`) wiring state + log + dispatcher + channels; `start_http()`, `start_inbox()`, `stop()`.
  - CLI extension: `openrepose serve [--http-port N] [--inbox]` keeps the headless surface alive with SIGINT/SIGTERM handling.
  - 33 new pytest tests across log format, state file, command handlers, HTTP channel, inbox channel. Full suite (with WP-I0-001 carry-over) is now 80 passed.
  - End-to-end manual run via inbox: dropped 3 JSON command files, app processed all 3 in order, rig fitted, yaw set, export wrote to `outputs/aeri_e2e/aeri_e2e_yaw_her-left-30.json`. Processed responses landed in `outputs/.runtime/processed/cmd{1,2,3}.ok.json`.
- **What Remains Simulated**:
  - `snapshot` command returns `NotImplementedError` until WP-I0-003 wires the snapshot handler. Dispatcher logs `ERR cmd.snapshot` and the response payload carries `type: NotImplementedError` so an LLM agent can detect the unwired state.
  - File-watch is poll-based (0.5s default). Native filesystem events via `watchdog` is a polish item for a later WP if iteration latency matters.
  - HTTP channel has no auth and no TLS. Single-user local-only is the documented v0.1 contract.
- **Next Blocking Real Seam**:
  - WP-I0-003 Snapshot Subsystem: implement offscreen pyrender FBO + `QWidget.grab()` plumbing so the LLM agent can pull visual artifacts of any module without operator focus theft. Wire the resulting handler into `CommandDispatcher._snapshot_handler` and remove the NotImplementedError fallback.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation commits: state, log, commands, channels (HTTP and inbox), app, cli extension.
3. Verification commit: pytest results saved.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_state_file.py .product/tests/test_log_format.py .product/tests/test_command_handlers.py .product/tests/test_http_channel.py .product/tests/test_inbox_channel.py --junitxml=target/test-artifacts/WP-I0-002/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I0-002/` plus a sample `outputs/.runtime/state.json` after the manual end-to-end run.
- **Claim Standard**: never mark `DONE` without junit XML and a sample state.json.

## Exit Criteria

- [ ] All Definition of Done items checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Test suite executed; junit XML saved.
- [ ] Evidence populated with concrete paths.
- [ ] Operator sign-off: APPROVED.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I0-002/pytest_results.xml` — 80 passed, 0 failed (across the full project suite including WP-I0-001 tests).
- **Logs**: stdout from the manual end-to-end inbox run (full transcript shown during REVIEW; key lines below):
  - `OK   app.start: outputs_root="..."`
  - `OK   rig.fit: portrait="..." face=478 body=33 t_ms=1142 body_partial=yes`
  - `OK   yaw.set_bin: bin="her-left 30" signed_deg=30.0`
  - `OK   export.single: avatar_slug=aeri_e2e bin="her-left 30" out="..."`
  - `OK   cmd.completed: command=export_single status=ok`
- **Screenshots / Exports**:
  - `target/test-artifacts/WP-I0-002/inbox_e2e_export.json` — the OpenPose JSON written by the export_single command driven via inbox.
  - `target/test-artifacts/WP-I0-002/inbox_e2e_state_after.json` — state.json snapshot after the 3-command run.
  - `target/test-artifacts/WP-I0-002/inbox_e2e_processed/cmd{1,2,3}.ok.json` — per-command response wrappers from the inbox channel.
- **Build Artifacts**: `pyproject.toml` extended; editable install reused.
- **Proof Artifact**: `target/test-artifacts/WP-I0-002/`
- **Operator Sign-off**: APPROVED 2026-05-02 — operator approved alongside WP-I0-003 in the same review pass. Quote: "wp 2 and 3 are pass".

## Progress Log

- `2026-05-02`: WP drafted, status DRAFT, blocked by WP-I0-001.
- `2026-05-02`: WP-I0-001 reached DONE; this WP unblocked, promoted DRAFT -> READY -> IN-PROGRESS. Implementation order: log -> state -> commands -> channels/http -> channels/inbox -> app -> cli serve subcommand, then tests.
- `2026-05-02`: implementation done. 80/80 pytest passing. Manual end-to-end via inbox channel confirmed: import_portrait -> set_yaw_bin -> export_single all process, state.json updates atomically, exports land at expected paths. Two small bugs found and fixed during the manual run (inbox processed_dir auto-creation, log error-message text). Status -> REVIEW.
