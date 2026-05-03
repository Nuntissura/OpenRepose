# WP-I3-005 - Default-Staging ComfyUI Bridge

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**:
  - `.gov/spec/openrepose_intake_v0_1.md` — Default-Staging ComfyUI Bridge
  - `.gov/spec/openrepose_rules_v0_1.md` — Error Citation Contract (INTAKE-002)
  - `.gov/spec/openrepose_library_v0_1.md` — ComfyUI Bridge / Custom Node Contract (the existing I2 contract this WP updates)
- **Linked Test Suite**: `.product/tests/test_comfyui_bridge.py` (extended); `.product/tests/test_intake_commands.py` (extended for `intake_begin_run`)
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Make intake the default destination for ComfyUI-generated outputs. After this WP, an operator launching ComfyUI for a batch run sets `OPENREPOSE_TASK_ID` (and optionally `OPENREPOSE_CARD_ID`) in the environment; every image saved through the OpenRepose bridge node lands at `outputs/intake/<task_dir>/raw/<filename>` and a `library_outputs` row is inserted at `status='pending'`. The legacy direct-library path remains usable but only with an explicit operator token in the bridge config (rule citation `INTAKE-002`).

## Linked Workpackets

- **Predecessor(s)**: WP-I3-004 (REVIEW — `intake_register_output` exists), WP-I3-003 (REVIEW — schema exists). Building on REVIEW per handoff guidance.
- **Successor(s)**: WP-I3-006 (AMood card creation — bridge gains card-aware behaviour once cards exist). WP-I3-010 (end-to-end EXP120 verification — exercises bridge → intake → triage → finalize).
- **Blocks**: WP-I3-010.
- **Blocked-By**: none.
- **Related**: WP-I2-005 (the I2 bridge node this WP modifies).

## Linked Requirements / Spec Sections

- `openrepose_intake_v0_1.md` / `## Default-Staging ComfyUI Bridge` (the canonical default/operator-token/refusal table)
- `openrepose_intake_v0_1.md` / `## Triage Commands / intake_register_output` (already wired in WP-I3-004 — payload shape this WP composes)
- `openrepose_rules_v0_1.md` / `## Initial Registry / INTAKE-002`

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Local codebase | `.product/comfyui-bridge/openrepose_bridge.py` (WP-I2-005, 227 lines) | Existing bridge is a single ComfyUI custom node (`OpenReposeBridge`) that POSTs `register_library_entry`. Stdlib-only — no `requests`/`pyyaml`. The new default-staging path needs to compose a different payload (`intake_register_output`) without violating the stdlib-only constraint. `urllib.request` already in use; same pattern works for the new POST. | adopt |
| 2026-05-03 | Spec gap | `openrepose_intake_v0_1.md` / `intake_register_output` lists `task_id, file_path, metadata, width, height` but `library_outputs.run_id` is NOT NULL. WP-I3-004 made `run_id` a required dispatcher field. | The bridge needs a way to create a `library_runs` row before it can call `intake_register_output`. Add a new dispatcher command `intake_begin_run` (input: `card_id` OR `task_id` + optional `card_slug` for ergonomics + optional sampler/cfg/steps/seed/workflow_json; output: `run_id`) — bridge calls it once per ComfyUI save, then `intake_register_output` once per image. Same one-run-per-save pattern as the underlying ComfyUI semantic. | adopt |
| 2026-05-03 | Spec | `openrepose_intake_v0_1.md` / "Default-Staging ComfyUI Bridge" | Three behavioural branches: (a) `OPENREPOSE_TASK_ID` set → intake path; (b) `operator_token` in bridge config → legacy direct-library path; (c) neither → refuse with INTAKE-002 citation in the bridge logs (the bridge does NOT silently fall back). The spec also allows `OPENREPOSE_LEGACY_DIRECT_WRITE=1` for one WP cycle as a transition aid; this WP adds the flag, the next bridge WP removes it. | adopt-with-fallback |
| 2026-05-03 | Local codebase | `.product/tests/test_comfyui_bridge.py` (existing) | Tests already mock the POST endpoint via a stdlib `http.server`. Same fixture pattern works for the new payload shape. | adopt |
| 2026-05-03 | Python docs | https://docs.python.org/3/library/hashlib.html | `content_hash` per spec is sha256 of file bytes; bridge already reads bytes for the b64 image payload — compute the hash on the same buffer to avoid a second read. | adopt |

## Reality Boundary

- **Real Seam**: `.product/comfyui-bridge/openrepose_bridge.py` gains environment-variable detection (`OPENREPOSE_TASK_ID`, `OPENREPOSE_CARD_ID`, `OPENREPOSE_OPERATOR_TOKEN`, `OPENREPOSE_LEGACY_DIRECT_WRITE`); a new `build_intake_register_output_payload` helper composes the intake POST shape; the save-and-register loop branches on env state and calls either (intake path: `intake_begin_run` once + `intake_register_output` per image) or (legacy direct-write path: existing `register_library_entry`) or refuses with an INTAKE-002 log line. New OpenRepose-side dispatcher command `intake_begin_run` creates a `library_runs` row and returns its `run_id`. Manual + bridge README updated.
- **User-Visible Win**: an operator launches ComfyUI with `set OPENREPOSE_TASK_ID=<uuid>` (and optionally `set OPENREPOSE_CARD_ID=<uuid>`); every Save through the OpenRepose bridge node lands in the intake queue ready for triage. Without the env var, the bridge refuses to write to the library and logs `INTAKE-002` so the operator/LLM gets immediate feedback instead of silent contamination.
- **Proof Target**: pytest extends `test_comfyui_bridge.py` with three new branch tests (intake path success, legacy path with token, refusal-no-env) + payload-shape unit tests. End-to-end test: bridge against an in-process `http.server` against a real `App`; image bytes go through the full pipeline; `library_outputs` row appears at `status='pending'` in the ephemeral PG.
- **Allowed Temporary Fallbacks**: `OPENREPOSE_LEGACY_DIRECT_WRITE=1` env var bypasses the new gate and forces the legacy direct-write path even without a token (transition aid for in-flight workflows). Marked `# FALLBACK v0.1` in the bridge code; removal lands in the next bridge WP. The intake path also tolerates a missing `OPENREPOSE_CARD_ID`: the bridge calls `intake_begin_run` with only `task_id` + workflow params, and the dispatcher accepts `card_id=NULL` for v0.1 (WP-I3-006 will populate cards; bridge gains card binding in a successor WP). All NULL-card runs are still triageable.
- **Promotion Guard**: do not declare WP-I3-005 stable until: (a) a real-PG end-to-end test drives 5+ images through the bridge → intake → soft_accept → finalize, (b) refusal path emits the exact INTAKE-002 citation shape from `openrepose_rules_v0_1.md`, (c) the legacy-fallback flag is documented + Manual Impact reflects the operator setup change.

## In Scope

- Edit `.product/comfyui-bridge/openrepose_bridge.py`:
  - Read `OPENREPOSE_TASK_ID`, `OPENREPOSE_CARD_ID` (optional), `OPENREPOSE_OPERATOR_TOKEN` (optional), `OPENREPOSE_LEGACY_DIRECT_WRITE` (FALLBACK) at node-call time.
  - Branch in `save_and_register`:
    - `OPENREPOSE_TASK_ID` set: call `intake_begin_run` once → for each saved image, call `intake_register_output` with `run_id`, `task_id`, `file_path` (relative to outputs root), `content_hash` (sha256), `width`, `height`. POST URL is the same `/command` endpoint.
    - `OPENREPOSE_TASK_ID` not set + `OPENREPOSE_OPERATOR_TOKEN` set: legacy `register_library_entry` path with `operator_token` field on the payload.
    - `OPENREPOSE_LEGACY_DIRECT_WRITE=1`: legacy path even without a token (FALLBACK).
    - Neither: refuse — log `INTAKE-002` citation in bridge stderr; do not POST anything; image still saved to ComfyUI's output dir (per spec rule that image-save never fails because of OpenRepose).
  - New helper `build_intake_register_output_payload(...)`.
  - New helper `build_intake_begin_run_payload(...)`.
  - New helper `compute_image_metadata(image_path)` returning `(content_hash, width, height)` reading bytes once.
  - Existing `build_register_payload` retained for legacy path; add `operator_token` keyword arg (optional).

- Edit `.product/src/openrepose/commands.py`:
  - Add `_h_intake_begin_run` handler. Signature: `task_id` (required), optional `card_id`, `card_slug` (resolved via `library_entries.title` lookup if no `card_id`), `sampler`, `cfg`, `steps`, `seed`, `pose_guide_id`, `workflow_json`. Inserts `library_runs` row, returns `run_id`.
  - Register `intake_begin_run` in `_HANDLERS`.
  - **Decision (2026-05-03)**: do NOT add a dispatcher-side INTAKE-002 guard on `register_library_entry`. Per spec, INTAKE-002 is the bridge's contract; non-bridge callers (existing I2 tests, GUI, other LLM agents using the dispatcher directly for non-bridge work) must continue to call `register_library_entry` freely. The bridge enforces INTAKE-002 by refusing to POST in the absence of env/token; nothing slips past it via the bridge path.

- Edit `.product/src/openrepose/library/intake/__init__.py`:
  - Re-export `begin_run` from a new `runs.py` module (keeps the data layer consistent).

- New `.product/src/openrepose/library/intake/runs.py`:
  - `begin_run(conn, *, task_id, card_id, sampler, cfg, steps, seed, pose_guide_id, workflow_json) -> LibraryRun`.
  - Card resolution: when `card_id is None` but `card_slug` supplied, the dispatcher resolves to the card via `library_entries.title = slug AND batch_id = (SELECT id FROM library_batches WHERE task_id = :task_id LIMIT 1)`.

- Tests:
  - `.product/tests/test_comfyui_bridge.py` — three new branch tests (intake-path happy, legacy-with-token, refused-no-env) + payload-shape unit tests for `build_intake_register_output_payload` and `build_intake_begin_run_payload`.
  - `.product/tests/test_intake_commands.py` — happy-path test for `intake_begin_run` (with/without card_id; verifies the row hits `library_runs`).

- Manual: extend `.gov/doc/manual/intake-and-triage.md#default-intake` with operator setup steps (`set OPENREPOSE_TASK_ID=...` on Windows; `export OPENREPOSE_TASK_ID=...` on POSIX); brief note about the legacy fallback flag.

## Out Of Scope

- Bridge gains card-aware binding (auto-map workflow → `card_id` from a registry). Future WP after WP-I3-006.
- Removing the `OPENREPOSE_LEGACY_DIRECT_WRITE` fallback flag. Next bridge WP after a clean operator transition.
- Changing the `register_library_entry` schema or behaviour for non-bridge callers.
- Pose-guide auto-registration from ComfyUI (the bridge does not know about pose guides; that's a Feature 1 + bridge follow-up).
- Live operator-token issuance / rotation (still SHA-256 fallback per WP-I3-004).
- Retry logic on bridge POST failures (existing best-effort behaviour preserved).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-005-default-staging-comfyui-bridge.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/manual/intake-and-triage.md`

### Product (`.product/`)

- `.product/comfyui-bridge/openrepose_bridge.py` (extend)
- `.product/comfyui-bridge/README.md` (new operator setup section)
- `.product/src/openrepose/commands.py` (new `_h_intake_begin_run` handler + INTAKE-002 guard on `register_library_entry`)
- `.product/src/openrepose/library/intake/__init__.py` (re-export `begin_run`)
- `.product/src/openrepose/library/intake/runs.py` (new)
- `.product/tests/test_comfyui_bridge.py` (extend)
- `.product/tests/test_intake_commands.py` (extend)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-005/pytest_results.xml`

## Risks And Dependencies

- **Risk**: env-var-driven branching is easy to misread in the bridge logs. **Mitigation**: bridge emits a one-line stderr summary at node-call time naming the active path (`intake-default | legacy-with-token | legacy-fallback-flag | refused`) so operators can confirm the chosen branch from ComfyUI's console.
- **Risk**: card-slug → card_id lookup in `intake_begin_run` is ambiguous when multiple batches share a task. **Mitigation**: v0.1 takes the first matching card via `LIMIT 1` and logs a WARN if more than one matches. Operator can supply `card_id` directly when binding gets ambiguous; documented in the manual.
- **Risk**: legacy-fallback flag becomes permanent because operators forget to remove it. **Mitigation**: bridge stderr log line names the flag explicitly; next bridge WP removes the code path so operators are forced to migrate.
- **Risk**: `intake_register_output` requiring `run_id` is awkward for the bridge — the bridge would need to remember the run_id across save iterations within the same node call. **Mitigation**: `OpenReposeBridge.save_and_register` already iterates per-image inside one method call; the run_id is a local variable assigned once before the loop and reused per image. Single ComfyUI save = single `library_runs` row.
- **Dependency**: WP-I3-004 dispatcher (REVIEW). **Owner**: assistant. **Status**: REVIEW — building on it.
- **Dependency**: WP-I3-003 schema (REVIEW). **Status**: REVIEW.

## Definition Of Done

- [x] `.product/comfyui-bridge/openrepose_bridge.py` reads `OPENREPOSE_TASK_ID` / `OPENREPOSE_CARD_ID` / `OPENREPOSE_OPERATOR_TOKEN` / `OPENREPOSE_LEGACY_DIRECT_WRITE` from environment.
- [x] When `OPENREPOSE_TASK_ID` is set, bridge calls `intake_begin_run` once per ComfyUI save and `intake_register_output` once per image.
- [x] When neither `OPENREPOSE_TASK_ID` nor `OPENREPOSE_OPERATOR_TOKEN` (and no legacy flag) is set, bridge refuses to POST and logs the INTAKE-002 citation; image still saves to ComfyUI's output dir.
- [x] `register_library_entry` dispatcher handler is unchanged (decided 2026-05-03: INTAKE-002 enforcement lives in the bridge only; non-bridge callers preserve the I2 contract).
- [x] New `intake_begin_run` dispatcher command creates a `library_runs` row and returns `run_id`; supports `card_id` direct or `card_slug` resolution against the active task's batch.
- [x] All branches covered by tests in `test_comfyui_bridge.py` (intake-path happy, legacy-with-token, refused-no-env, payload-shape).
- [x] `intake_begin_run` covered by `test_intake_commands.py`.
- [x] Full pytest suite remains green (530+ passing).
- [x] `powershell -ExecutionPolicy Bypass -File scripts/audit-repo.ps1` exits 0.
- [x] **Manual Impact**: Yes — extends `intake-and-triage.md#default-intake` with operator-setup env-var steps + legacy-fallback note; updates `.product/comfyui-bridge/README.md` with the same.

## Test Coverage Plan

### Functional Flow Tests
- [x] Intake path: env has `OPENREPOSE_TASK_ID`; one ComfyUI save with two images → 1 `library_runs` row + 2 `library_outputs` rows at `status='pending'`.
- [x] Legacy path with token: env has `OPENREPOSE_OPERATOR_TOKEN` (no task id) → `library_entries` row created via existing code path.
- [x] Refused path: neither env nor token → no DB write; bridge logs INTAKE-002; image still saved to disk.
- [x] Legacy fallback flag: `OPENREPOSE_LEGACY_DIRECT_WRITE=1` → legacy path runs even without a token (FALLBACK exercised + log line names it).

### Code Correctness Tests
- [x] `build_intake_register_output_payload` returns the exact dict shape `intake_register_output` expects.
- [x] `build_intake_begin_run_payload` returns the exact dict shape `intake_begin_run` expects.
- [x] `compute_image_metadata` returns sha256 hex + width + height for a small fixture PNG.
- [x] Card-slug resolution in `intake_begin_run`: passing `card_slug` resolves to the only matching card; WARN logged when multiple matches; ERR when no match.

### Red-Team / Abuse Tests
- [x] Bridge with empty string `OPENREPOSE_TASK_ID=""` is treated as unset (refusal path).
- [x] Bridge invokes the legacy path with `OPENREPOSE_OPERATOR_TOKEN="bogus"`: the bridge passes the token through and the dispatcher's existing `register_library_entry` runs unchanged (token-tightening on the dispatcher side is explicitly out of scope per Decisions Log; the I3 kill switches that matter are at intake_finalize / intake_register_output, not at register_library_entry which is for ad-hoc operator work).

### Performance / Reliability Tests
- [x] N/A — no perf budget; the bridge is per-image best-effort.

## Rollback Plan

- Files to revert: bridge module + new `runs.py` + commands.py additions + new tests.
- Files to keep: WP file + taskboard row.
- Recovery command: `git revert <impl-commit-hash>`. Existing I2 bridge contract continues to work (legacy path unchanged); only the new default behaviour is removed.

## Decisions Log

- 2026-05-03: **One new dispatcher command `intake_begin_run` instead of stuffing run-creation into `intake_register_output`**. Reason: clear separation between "begin one ComfyUI save" and "record one output of that save". Bridge happens to call them in a 1:N pattern but the contract works for non-bridge callers too. Alternative: auto-create on first `intake_register_output` per `(task_id, sampler, seed)` tuple (rejected — implicit behaviour hides the run boundary).
- 2026-05-03: **Bridge refuses, doesn't fall back, when neither env var nor token is set**. Reason: the spec's INTAKE-002 rule is "writes to intake unless operator token allows direct library" — silent fall-through to legacy was the I2 default and is exactly what the I3 work prevents. Refusal + clear log line forces operator to choose explicitly. Alternative: graceful fallback to legacy + WARN (rejected — defeats the point of WP-I3-005).
- 2026-05-03: **`OPENREPOSE_LEGACY_DIRECT_WRITE` flag for one WP cycle**. Reason: operators with in-flight ComfyUI workflows tied to the I2 bridge need a one-WP-cycle escape hatch. Flag is loud (named in stderr; FALLBACK comment in code; Fallback Register entry); next WP removes it. Alternative: hard cutover (rejected — risks operator workflow disruption).
- 2026-05-03: **Card-slug resolution via `LIMIT 1` + WARN on ambiguity**. Reason: WP-I3-006 will introduce a stricter card namespace; for v0.1 the operator usually has one batch per task and slug uniqueness within a batch is enforced. WARN log gives the operator a feedback signal without a hard fail. Alternative: hard fail on ambiguity (rejected — operator UX during the I3 transition is too brittle).

## Fallback Register

- **Path**: `.product/comfyui-bridge/openrepose_bridge.py`
- **Required Label In Code/UI**: `# FALLBACK v0.1: OPENREPOSE_LEGACY_DIRECT_WRITE=1 forces the legacy direct-library path even without an operator token. Removed in the next bridge WP after operator transition.`
- **Successor / Debt Owner**: future bridge-hardening WP (not yet drafted)
- **Exit Condition To Remove**: operator confirms no in-flight workflows depend on the legacy path; subsequent bridge WP deletes the env-var branch.

## Change Ledger

- **What Became Real**: ComfyUI bridge node (`.product/comfyui-bridge/openrepose_bridge.py`) gains four-branch dispatch on `OPENREPOSE_TASK_ID` / `OPENREPOSE_OPERATOR_TOKEN` / `OPENREPOSE_LEGACY_DIRECT_WRITE` env vars, refusing with INTAKE-002 stderr citation when none is set. Intake path POSTs `intake_begin_run` once per ComfyUI save then `intake_register_output` per image, shipping bytes inline (b64) so the dispatcher writes the file into `outputs/intake/<task_dir>/raw/`. New helpers: `select_path()`, `build_intake_begin_run_payload()`, `build_intake_register_output_payload()`, `compute_image_metadata()`. New OpenRepose dispatcher command `intake_begin_run` creates one `library_runs` row and supports `card_id` direct or `card_slug` resolution under the active task's batch (multi-match logged WARN). New `library/intake/runs.py` module with `begin_run` + `resolve_card_by_slug` data-layer helpers. `_h_intake_register_output` extended to accept inline bytes (`image_b64` + `filename`) and write them to disk + auto-compute sha256 when no `content_hash` is supplied. `register_library_entry` is **unchanged** per Decisions Log (INTAKE-002 enforcement lives in the bridge; non-bridge callers preserve the I2 contract). One bug caught + fixed: psycopg cannot auto-adapt a Python dict to JSONB — wrapped `workflow_json` with `psycopg.types.json.Jsonb`. Manual extended (`intake-and-triage.md#default-intake` gains operator setup steps + branch table + card-binding section); bridge README rewritten with the four-branch table + intake-path bindings + new troubleshooting rows. 14 new tests (11 in `test_comfyui_bridge.py` covering env-branch selection, payload-builder shapes, image-metadata helper, end-to-end intake flow, card-slug resolution, and `register_library_entry` legacy-call regression; 2 in `test_intake_commands.py` for `intake_begin_run` row creation + `image_b64` ingestion). Full suite 544/544 passed (was 530); audit clean.
- **What Remains Simulated**: card creation still requires direct SQL or future `library_create_card` (WP-I3-006); the bridge's intake path requires the operator to set `OPENREPOSE_CARD_ID`/`OPENREPOSE_CARD_SLUG` until then. The `OPENREPOSE_LEGACY_DIRECT_WRITE` flag is the documented v0.1 fallback (see Fallback Register); next bridge WP removes it. Bridge does not auto-register pose guides — pose-guide pairing happens via Feature 1 + a follow-up WP. The bridge ships images inline (b64) instead of via shared filesystem path because ComfyUI and OpenRepose need not share an outputs root in v0.1; future WP can switch to direct filesystem write when both processes run on the same host.
- **Next Blocking Real Seam**: WP-I3-006 (AMood data-model commands + dedupe) makes `library_create_card` available so the bridge's card-binding can be a documented operator workflow; WP-I3-007 (requirements editor) populates `library_rules` so auto-route fires on real intake; WP-I3-008 (Triage GUI tab) consumes `state.library.intake` + 3 new snapshot targets; WP-I3-010 closes I3 with an end-to-end EXP120 walkthrough that exercises the bridge → intake → triage → finalize flow at production scale.

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP file + taskboard row).
2. Data-layer commit (`library/intake/runs.py` + `_h_intake_begin_run`).
3. Bridge commit (env-var branching + new payload helpers).
4. Test + manual commit + REVIEW transition.

## Proof Of Implementation

- **Command Runs**: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_comfyui_bridge.py .product/tests/test_intake_commands.py --junitxml=target/test-artifacts/WP-I3-005/pytest_results.xml -q` returns 0; full suite remains green.
- **Proof Artifact**: `target/test-artifacts/WP-I3-005/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

- [x] An LLM agent does not need to touch this feature directly — the bridge is operator-launched ComfyUI tooling. State surface remains via WP-I3-004's `state.library.intake`.
- [x] N/A snapshot — bridge has no GUI surface.
- [x] No code path in the new bridge logic calls any GUI focus method.
- [x] No modal dialogs anywhere.
- [x] Tests cover the bridge-side payload + dispatcher-side handler from headless code (no GUI imports).

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-005/`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**:
  - WP-I3-005 dedicated suite: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_comfyui_bridge.py .product/tests/test_intake_commands.py --junitxml=target/test-artifacts/WP-I3-005/pytest_results.xml -q` → 45/45 passed in 125.61s.
  - Full regression sweep: `.\.venv\Scripts\python.exe -m pytest .product/tests/ -q` → 544/544 passed in 1359.69s. One pre-existing `PermissionError` warning in `test_state_write_atomic_no_partial` reader thread is unchanged from WP-I3-002 baseline.
- **Audit**: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/audit-repo.ps1` → `audit-repo: OK no violations` (exit 0).
- **Logs**: pytest stdout in this session; junit XML at `target/test-artifacts/WP-I3-005/pytest_results.xml`.
- **Screenshots / Exports**: N/A — non-GUI surface.
- **Build Artifacts**: N/A.
- **Proof Artifact**: `target/test-artifacts/WP-I3-005/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP drafted at READY per operator authorization ("draft and kick off" 2026-05-03). Predecessors WP-I3-003 + WP-I3-004 at REVIEW; building on them per handoff stance. Kickoff commit + push will land this WP file + taskboard row before any `.product/` file is opened.
- 2026-05-03: Kickoff push landed (commit `9bb4231`) on `origin/main`. Status READY -> IN-PROGRESS.
- 2026-05-03: Decision (drop dispatcher-side INTAKE-002 guard from `register_library_entry` per re-read of spec). New `library/intake/runs.py` + `_h_intake_begin_run` handler + bridge module rewrite + extended `_h_intake_register_output` for inline b64 image bytes. First test run hit `psycopg.errors.ProgrammingError: cannot adapt type 'dict' using placeholder` — wrapped `workflow_json` with `psycopg.types.json.Jsonb`. 45/45 in WP test files; 544/544 full suite; audit clean. Manual + bridge README updated. Status IN-PROGRESS -> REVIEW.
