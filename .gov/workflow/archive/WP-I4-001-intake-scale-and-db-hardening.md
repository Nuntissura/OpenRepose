# WP-I4-001 - Intake Scale And DB Hardening

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-04
- **Last Updated**: 2026-05-04
- **Status**: DONE
- **Iteration**: I4
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: `.gov/spec/openrepose_intake_v0_1.md`, `.gov/spec/openrepose_library_v0_1.md`, `.gov/spec/openrepose_requirements_v0_1.md`, `.gov/spec/openrepose_rules_v0_1.md`
- **Linked Test Suite**: `.product/tests/test_intake_scale_db_hardening.py`, `.product/tests/test_e2e_parallel_intake.py`, `.product/tests/test_intake_dispatcher_i4.py`
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Harden the existing I3 intake system so multiple LLM/model workers can submit hundreds of files per project in parallel without duplicate rows, stale file paths, search contamination, partial DB writes, or unsafe cleanup. This WP does not replace intake; it extends the locked `Project -> Task -> Batch -> Card -> Run -> Output` pipeline with bulk registration, idempotency, producer attribution, durable file-state tracking, and tighter transaction ownership.

## Linked Workpackets

- **Predecessor(s)**: WP-I3-010 (I3 end-to-end verification; currently REVIEW, acceptable to build on REVIEW per I3 precedent)
- **Successor(s)**: future I4 soak / production-scale triage WP; future bridge-hardening WP that removes `OPENREPOSE_LEGACY_DIRECT_WRITE`
- **Blocks**: large-scale multi-model production runs that expect 100+ files per model per project
- **Blocked-By**: none
- **Related**: WP-I3-004, WP-I3-005, WP-I3-006, WP-I3-007, WP-I3-008, WP-I3-010

## Linked Requirements / Spec Sections

- `openrepose_intake_v0_1.md` / `## Hierarchy`
- `openrepose_intake_v0_1.md` / `## Folder Layout`
- `openrepose_intake_v0_1.md` / `## Two-Stage Acceptance`
- `openrepose_intake_v0_1.md` / `## Default-Staging ComfyUI Bridge`
- `openrepose_intake_v0_1.md` / `## Triage Commands`
- `openrepose_library_v0_1.md` / `## Database Schema`
- `openrepose_library_v0_1.md` / `## Multi-Operator Concurrency`
- `openrepose_requirements_v0_1.md` / `## Counters and Satisfaction Semantics`
- `openrepose_rules_v0_1.md` / `## Severity Tiers`

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Local spec | `.gov/spec/openrepose_intake_v0_1.md` | Intake already owns the staging contract: raw outputs enter `library_outputs`, stay isolated under `outputs/intake/`, soft-accept/finalize move files toward `library/<project>/<batch>/`, and search excludes pending by default. Hardening must extend this system, not add a parallel ingest layer. | adopt |
| 2026-05-04 | Local workpacket | `.gov/workflow/archive/WP-I3-004-intake-project-task-command-surface.md` | I3 shipped the command surface and documented known filesystem/DB sync risks. This WP converts those risks into durable file-state handling and transaction-owned command services. | adapt |
| 2026-05-04 | Local workpacket | `.gov/workflow/archive/WP-I3-005-default-staging-comfyui-bridge.md` | Bridge default-staging already calls `intake_begin_run` then `intake_register_output`. Bulk ingestion should preserve that shape by making the bulk command per-run and keeping the single-output command as the primitive. | adopt |
| 2026-05-04 | Local workpacket | `.gov/workflow/workpackets/WP-I3-010-e2e-exp120-verification.md` | I3 e2e covers 50 outputs, auto-route, soft-accept, finalize, counters, and wholesale reject. I4 should raise that proof standard to multi-producer 100+ output batches with idempotent retries. | adopt |
| 2026-05-04 | PostgreSQL docs | https://www.postgresql.org/docs/current/static/sql-insert.html | `INSERT ... ON CONFLICT` is the native idempotent insert/upsert mechanism for unique-key collision handling. Use it for bulk intake idempotency rather than pre-read / insert race patterns. | adopt |
| 2026-05-04 | PostgreSQL docs | https://www.postgresql.org/docs/current/sql-select.html | `FOR UPDATE SKIP LOCKED` is explicitly useful for queue-like multi-consumer workloads. Use it for claim/lease semantics where multiple LLM agents process intake rows concurrently. | adopt |
| 2026-05-04 | PostgreSQL docs | https://www.postgresql.org/docs/16/explicit-locking.html | Transaction-level advisory locks release at transaction end and fit short structural critical sections. Prefer row locks / unique constraints for output ingestion; reserve advisory locks for project/card structural edits. | adapt |

## Reality Boundary

Sacred. Captured before work starts.

- **Real Seam**: Existing intake DB and command paths become scale-safe: bulk registration, idempotent retries, producer attribution, durable file-state/outbox records, transaction-owned command services, and search/status filtering corrections.
- **User-Visible Win**: The operator can point multiple model workers at one OpenRepose project/task and receive 100+ files per worker without duplicate library pollution, lost provenance, stale DB file paths, or manual cleanup after retry/crash paths.
- **Proof Target**: A new parallel e2e test submits at least 3 producer streams with at least 100 outputs each into one project/task, retries one producer payload, soft-accepts/finalizes a subset, and proves row counts, duplicate counts, file states, target counters, and search results remain correct.
- **Allowed Temporary Fallbacks**: Bulk tests may use small synthetic PNG bytes or deterministic tiny fixture files instead of production-size renders; producer model names may be synthetic; physical file moves may run inside a temp outputs root.
- **Promotion Guard**: Do not transition this WP to REVIEW until the multi-producer e2e proof passes, all changed DB paths use command/service-owned transactions, and the old stale-file-path/search-contamination risks are closed by assertions.

## In Scope

- Extend the existing intake spec with I4 hardening details: bulk registration, idempotency, producer attribution, storage state, and retry/recovery semantics.
- Add a migration after `005_i3_amood_tsv_views.sql` for intake hardening fields/tables.
- Add output-level producer attribution: `source_model`, `agent_id`, `producer_run_id`, and `idempotency_key`.
- Add uniqueness for safe retry, scoped to task/run/producer identity.
- Add storage-state tracking for `library_outputs`: raw, diagnostic, rejected, soft_accepted, accepted, missing, and file_op_failed.
- Add append-only output lifecycle events for audit/recovery.
- Add a durable file-operation outbox for moves/deletes that can be retried after a crash.
- Add `intake_register_outputs_bulk` as the bulk counterpart to `intake_register_output`.
- Keep `intake_register_output` intact as the single-output primitive and make bulk registration share its validation/auto-route path.
- Update soft-accept, reject, diagnostic auto-route, finalize, and wholesale-reject paths so `library_outputs.file_path` and storage state match the actual file location.
- Add explicit recovery/audit command for broken output paths and pending/failed file operations.
- Fix library search default filtering so main library search excludes non-promoted intake/staging rows unless an explicit include flag is supplied.
- Normalize transaction ownership for the touched intake/library DB paths: low-level data functions should not commit; command/service handlers should own commit/rollback.
- Add queue-safe claim semantics for concurrent LLM/worker triage where needed, using row locks and `SKIP LOCKED`.
- Add tests for duplicate retries, concurrent bulk producers, stale path prevention, search filtering, rollback behavior, and file-operation failure recovery.

## Out Of Scope

- Replacing the I3 intake hierarchy or adding a second ingestion system.
- Replacing PostgreSQL with another queue/database.
- Multi-machine shared filesystem design.
- GUI redesign of the triage tab.
- ML-backed quality/adult/anatomy classifiers.
- Removing the `OPENREPOSE_LEGACY_DIRECT_WRITE` fallback flag from the bridge.
- Implementing production file-retention policies beyond safe state transitions and recovery hooks.
- Starting product implementation before the governance kickoff commit is committed and pushed per Work-Start Protocol.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I4-001-intake-scale-and-db-hardening.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_intake_v0_1.md`
- `.gov/spec/openrepose_library_v0_1.md`
- `.gov/doc/manual/intake-and-triage.md`

### Product (`.product/`)

- `.product/migrations/006_i4_intake_scale_hardening.sql`
- `.product/src/openrepose/commands.py`
- `.product/src/openrepose/library/search.py`
- `.product/src/openrepose/library/intake/outputs.py`
- `.product/src/openrepose/library/intake/tasks.py`
- `.product/src/openrepose/library/intake/runs.py`
- `.product/src/openrepose/library/intake/storage.py` (new if needed)
- `.product/src/openrepose/library/intake/bulk.py` (new if needed)
- `.product/tests/test_intake_scale_db_hardening.py`
- `.product/tests/test_e2e_parallel_intake.py`
- `.product/tests/test_intake_dispatcher_i4.py`

### Build / Output (gitignored)

- `target/test-artifacts/WP-I4-001/`
- Temporary `outputs/intake/` and `outputs/library/` trees under pytest temp roots only.

## Risks And Dependencies

- **Risk**: Scope can grow into XL if transaction-boundary cleanup tries to refactor every DB module in one pass. **Mitigation**: this WP owns touched intake/library paths plus any directly composed AMood/requirements paths needed for correctness; unrelated cleanup becomes follow-up WPs.
- **Risk**: DB/file atomicity cannot be literal because PostgreSQL and filesystem moves do not share a transaction manager. **Mitigation**: use durable file-operation rows plus retry/recovery state, and stop claiming "one transaction" for DB+filesystem effects where that is not true.
- **Risk**: Bulk registration with inline base64 for hundreds of files can be memory-heavy. **Mitigation**: support file-path payloads as the preferred bulk mode; cap bulk request size; retain single-output path for inline bytes and smaller calls.
- **Risk**: Incorrect idempotency scope could collapse intentionally duplicated outputs. **Mitigation**: use producer-supplied `idempotency_key` for retry identity; keep `content_hash` as dedup metadata/warning, not the only uniqueness key.
- **Risk**: Search filter changes can hide historical I2 entries with no I3 status. **Mitigation**: define compatibility behavior in spec and tests; promoted/complete I2 rows must remain discoverable or be explicitly migrated.
- **Dependency**: PostgreSQL features `ON CONFLICT`, row locks, and `SKIP LOCKED`. **Owner**: assistant. **Status**: satisfied by existing PostgreSQL dependency.
- **Dependency**: I3 intake schema and dispatcher. **Owner**: assistant. **Status**: present; WP-I3-010 pending operator sign-off.

## Definition Of Done

- [x] Spec updates describe I4 hardening as an extension of existing intake, not a replacement ingest system.
- [x] Migration `006_i4_intake_scale_hardening.sql` applies cleanly from a fresh database and from an I3-current database.
- [x] `library_outputs` records output-level producer attribution and idempotency data.
- [x] Bulk command `intake_register_outputs_bulk` registers at least 100 outputs in one logical request and returns per-file results.
- [x] Retrying an identical bulk payload creates zero duplicate output rows and returns duplicate/existing results.
- [x] Soft-accept, reject, auto-route diagnostic, finalize, and wholesale-reject update `file_path` and storage state consistently with file operations.
- [x] File-operation failure leaves a retryable DB state, not a silent stale path.
- [x] A recovery/audit command reports missing files, pending file operations, and failed file operations.
- [x] Main `library_search` excludes pending/diagnostic/rejected/soft_accepted intake rows by default, with an explicit include flag for staging rows.
- [x] Touched intake/library DB helpers no longer commit internally; command/service transaction boundaries are explicit and tested.
- [x] Parallel e2e test covers at least 3 producer identities submitting at least 100 outputs each to one task.
- [x] Audit script exits clean.
- [x] **Manual Impact**: Yes - update `intake-and-triage.md` with bulk registration, idempotency, producer attribution, storage-state recovery, and search filtering semantics.

## Test Coverage Plan

### Functional Flow Tests

- [ ] Single-run bulk registration creates 100 pending outputs with correct `task_id`, `run_id`, producer fields, `idempotency_key`, `content_hash`, `file_path`, and storage state.
- [ ] Three producer identities each register 100+ outputs against one project/task; task summary and target counters remain correct.
- [ ] Retried bulk payload returns duplicate/existing results without creating extra rows or incrementing received counts incorrectly.
- [ ] Auto-route in bulk mode sends failing rows to diagnostic state and records diagnostics rows.
- [ ] Soft-accept and finalize move files through the documented `soft_accepted/` and `accepted/` projections and update DB paths.
- [ ] Reject and wholesale-reject keep rejected rows queryable while cleaning or marking physical files according to the hardened contract.

### Code Correctness Tests

- [ ] Migration test verifies all new columns, constraints, indexes, and event/file-op tables.
- [ ] Unit tests cover idempotency conflict resolution with `ON CONFLICT`.
- [ ] Unit tests cover storage-state transitions and event records.
- [ ] Regression tests verify existing `intake_register_output` still works.
- [ ] Regression tests verify `intake_begin_run` still works for bridge callers.
- [ ] Search tests verify default promoted-only behavior plus explicit staging inclusion.

### Red-Team / Abuse Tests

- [ ] Bulk payload with duplicate idempotency keys in the same request is rejected or normalized deterministically.
- [ ] Bulk payload with mismatched `task_id` / `run_id` / `card_id` is rejected.
- [ ] Producer-supplied paths resolving outside allowed outputs roots are rejected.
- [ ] Missing files are recorded as `missing` / failed file-op state, not silently promoted.
- [ ] Bogus status transitions remain blocked by the two-stage acceptance and status enum constraints.
- [ ] Two concurrent producers submitting overlapping idempotency keys cannot create duplicate rows.

### Performance / Reliability Tests

- [ ] Parallel e2e proof submits at least 300 total outputs and completes within an agreed local budget.
- [ ] File-op retry/recovery test simulates a move failure, repairs it, and proves the DB returns to a clean state.
- [ ] Claim/lease path, if implemented, uses `FOR UPDATE SKIP LOCKED` so two workers do not claim the same output.
- [ ] Transaction rollback test injects a mid-command error and proves no partial DB state remains for the command.

## Rollback Plan

- Files to revert: product files changed under `.product/`, migration `006_i4_intake_scale_hardening.sql`, spec/manual updates, and new tests.
- Files to keep: this WP and taskboard history.
- Recovery command: `git revert <implementation-commit>` after operator confirmation. If migration was applied to a real local DB, create a forward repair migration rather than manual table deletion.

## Decisions Log

- 2026-05-04: Use existing I3 intake as the backbone. Reason: `Project -> Task -> Batch -> Card -> Run -> Output` is already locked in spec and verified by WP-I3-010; adding a separate ingest pipeline would duplicate state and create drift. Alternatives considered: new ingest sessions/files subsystem as a parallel pipeline, rejected.
- 2026-05-04: Make bulk registration per-run. Reason: the current bridge/default-staging flow already begins one `library_runs` row and then registers outputs; bulk should accelerate that contract rather than redefine it. Alternatives considered: bulk command that implicitly creates runs, rejected because hidden run boundaries make provenance harder.
- 2026-05-04: Treat `content_hash` as dedup evidence, not sole idempotency. Reason: two generated outputs can legitimately be byte-identical while representing separate requested samples; retry identity needs an explicit producer key. Alternatives considered: unique `(task_id, content_hash)`, rejected.
- 2026-05-04: Use durable file-operation tracking instead of claiming DB+filesystem atomicity. Reason: filesystem moves cannot roll back with PostgreSQL transactions. Alternatives considered: perform file moves before DB commits, rejected because it creates orphan-file failure modes.
- 2026-05-04: Keep search hardening in this WP. Reason: intake scale without default search filtering will contaminate the operator's main library view under exactly the multi-model load this WP enables. Alternatives considered: defer search to a smaller follow-up, rejected.

## Fallback Register

No fallback used for REVIEW. Synthetic tiny PNG bytes remain within the Reality Boundary's allowed test-fixture fallback; no production-path behavior is simulated.

## Change Ledger

- **What Became Real**: Migration 006 adds producer attribution, idempotency, `storage_state`, lifecycle events, and file-op outbox tables. Bulk registration, duplicate retry handling, auto-route diagnostic outbox rows, file-op processing/recovery, search filtering, and dispatcher commands are implemented and tested.
- **What Remains Simulated**: Test fixtures use synthetic tiny PNG bytes and synthetic producer/model ids as allowed by the Reality Boundary. No production image generation is part of this WP.
- **Next Blocking Real Seam**: Operator REVIEW sign-off. Future bridge-hardening WP still owns removing `OPENREPOSE_LEGACY_DIRECT_WRITE`.

## Checkpoint Commit Plan

1. Governance kickoff commit: this WP + taskboard row.
2. Spec/manual commit: intake hardening contract and operator docs.
3. Migration + data-layer commit.
4. Command/service transaction commit.
5. Bulk/concurrency tests commit.
6. REVIEW transition commit with evidence pointers.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_intake_scale_db_hardening.py .product/tests/test_e2e_parallel_intake.py --junitxml=target/test-artifacts/WP-I4-001/junit.xml`; `pytest .product/tests/test_intake_dispatcher_i4.py -x --tb=short`
- **Proof Artifact**: `target/test-artifacts/WP-I4-001/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

Required because this WP changes command surfaces used by LLM agents, but it adds no visual GUI surface.

- [x] An LLM agent can trigger bulk registration, recovery/audit, and any claim/lease command through HTTP or inbox without touching the GUI.
- [x] An LLM agent can read current intake/storage/producer state from documented command responses.
- [x] N/A - no new visual artifact required; existing triage snapshot targets remain unchanged.
- [x] No code path in this feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [x] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [x] Tests cover the headless path through dispatcher commands and/or HTTP/inbox-compatible command payloads.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite has executed results saved under `target/test-artifacts/WP-I4-001/`.
- [x] Evidence section populated with concrete paths.
- [x] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**:
  - `.\.venv\Scripts\python.exe -m pytest .product/tests/test_intake_scale_db_hardening.py .product/tests/test_e2e_parallel_intake.py --junitxml=target/test-artifacts/WP-I4-001/junit.xml -x --tb=short` - 17 passed in 313.77s.
  - `.\.venv\Scripts\python.exe -m pytest .product/tests/test_intake_dispatcher_i4.py -x --tb=short -vv -s` - 7 passed in 195.07s.
- **Logs**: `powershell -ExecutionPolicy Bypass -File scripts\audit-repo.ps1` - OK no violations; one expected SKIP because `LIBRARY_DB_URL` is unset.
- **Screenshots / Exports**: N/A - non-visual hardening WP.
- **Build Artifacts**: N/A - no distributable build in this WP.
- **Proof Artifact**: `target/test-artifacts/WP-I4-001/`
- **Operator Sign-off**: 2026-05-04 operator sign-off recorded in chat; WP accepted as done and finished.

## Progress Log

- 2026-05-04: WP initialized at READY as governance-only setup. No `.product/` implementation started.
- 2026-05-04: Status READY → IN-PROGRESS. Spec extension landed in `openrepose_intake_v0_1.md` "I4 Scale + DB Hardening Extension" + `openrepose_library_v0_1.md` "I4 Multi-Operator Concurrency Hardening". Manual extension landed in `intake-and-triage.md#i4-hardening` covering producer attribution, storage_state, bulk registration, recovery, search filter, and concurrent triage. Five new rule_ids defined: INTAKE-005..009 (block/warn/info mix). Migration `006_i4_intake_scale_hardening.sql` schema shape locked in spec; implementation pending in next commit.
- 2026-05-04: Migration/data-layer implementation landed in prior commits: `006_i4_intake_scale_hardening.sql`, `library/intake/storage.py`, `library/intake/bulk.py`, search filtering, and scale/e2e tests. Follow-up dispatcher patch wires `intake_register_outputs_bulk`, `intake_recover_audit`, `intake_recover_retry`, and `intake_process_file_ops`; `BulkIntakeError` and `StorageError` now inherit `IntakeOutputError` so dispatcher error envelopes stay structured.
- 2026-05-04: Status IN-PROGRESS → REVIEW. Proof: 17/17 scale + parallel e2e tests passed with JUnit at `target/test-artifacts/WP-I4-001/junit.xml`; 7/7 dispatcher smoke tests passed; `scripts/audit-repo.ps1` clean. Operator sign-off pending.
- 2026-05-04: Operator sign-off recorded; status REVIEW -> DONE; archived under `.gov/workflow/archive/`.
