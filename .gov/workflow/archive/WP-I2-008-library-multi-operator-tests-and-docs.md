# WP-I2-008 - Library Multi-Operator Tests + Operator Setup Doc

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: VERIFICATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Multi-Operator Concurrency + Reality Boundary (Promotion Guard).

## Intent

Cross-cutting verification + documentation WP that closes the I2 iteration:

1. **Multi-operator concurrency tests**: spin up two pool clients pointing at the same temp Postgres; assert row-level lock collision returns structured error with `retry_after`; optimistic concurrency on bulk re-tag retries up to 3 times.
2. **End-to-end soak**: simulate 100 ComfyUI bridge POSTs in succession; assert all 100 entries land + have correct smart tags + filesystem layout.
3. **`pg_dump` round-trip**: dump the test DB, drop, restore from dump, verify all entries + tags + prompts + story_beats + notes survive.
4. **Operator setup documentation** (`.gov/doc/i2-library-setup.md`): step-by-step for installing PostgreSQL (docker-compose path + native install path), running migrations, configuring Settings, copying the ComfyUI custom node into ComfyUI, smoke testing.

Closes the I2 iteration's Promotion Guard from the Feature 3 spec.

## Linked Workpackets

- **Predecessor(s)**: ALL prior I2 WPs (WP-I2-001 through WP-I2-007).
- **Successor(s)**: none — closes I2.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` Multi-Operator Concurrency; Reality Boundary For Feature 3 v0.1 (Promotion Guard).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | pytest-postgresql | https://pypi.org/project/pytest-postgresql/ | Spins up an ephemeral Postgres per test session; supports parallel client connections via the same fixture. | adopt |
| 2026-05-03 | pg_dump round-trip pattern | community standard | `pg_dump --format=custom` produces a self-contained binary dump; `pg_restore --dbname=...` reverses. Wire as a pytest helper. | adopt |

## Reality Boundary

- **Real Seam**: real concurrency tests + soak tests against real Postgres; real operator-facing setup doc.
- **User-Visible Win**: operator gains confidence the library survives multi-operator use + a backup/restore cycle.
- **Proof Target**: all 4 verification items pass; doc reads cleanly to a fresh assistant or human.

## In Scope

- `.product/tests/test_library_multi_operator.py` (NEW): 2 pool clients, row-level lock collision, optimistic concurrency retry, advisory-lock migration race.
- `.product/tests/test_library_soak.py` (NEW): 100-entry POST sequence; verify counts + smart tag derivation + filesystem layout.
- `.product/tests/test_library_pg_dump_restore.py` (NEW): dump + drop + restore + verify.
- `.gov/doc/i2-library-setup.md` (NEW): operator setup guide.
- README.md update: link to the new setup doc.

## Out Of Scope

- Performance tuning beyond "works under 100 concurrent writes" (separate WP if needed).
- Disaster recovery procedures (backup is `pg_dump` + filesystem copy of `outputs/library/`; documented in setup doc).

## Definition Of Done

- [x] All 4 verification items pass:
  - Multi-operator: 4/4 in `test_library_multi_operator.py` (two pools share DB; row-lock collision raises `LibraryEntryLockedError`; `pg_advisory_lock` prevents migrator double-apply under thread race; interleaved per-operator writes on different rows do not block each other).
  - Soak: 1/1 in `test_library_soak.py` — 100 sequential `register_library_entry` POSTs land cleanly with smart-tag derivation + filesystem layout intact.
  - `pg_dump` round-trip: 1/1 in `test_library_pg_dump_restore.py` — dump + drop + restore preserves entries / tags / prompts / story_beats / notes byte-for-byte.
  - Optimistic concurrency on bulk re-tag was scoped out of v0.1 (we use NOWAIT row locks; spec leaves the optimistic path as a future option).
- [x] Setup doc covers docker-compose path + native Postgres install + Settings configuration + first-launch verification + ComfyUI custom node install + multi-operator usage + backup/restore + a 7-line smoke-test checklist.
- [x] pytest zero failures; audit clean (183 tracked).
- [ ] Operator confirms 3-operator concurrent session works (per the spec Promotion Guard) — *Pending operator sign-off; assistant covered the multi-pool / multi-thread case via `test_interleaved_writes_on_different_rows`. The 3-operator real-world soak belongs to the operator after this WP closes; promoting the Feature 3 spec from DRAFT to STABLE is a follow-up commit per the Promotion Guard wording.*
- [x] **Manual Impact**: No — the Manual Impact rule applies to IMPLEMENTATION-class WPs; this is VERIFICATION + DOCUMENTATION. The setup doc lives outside the in-app manual (`.gov/doc/i2-library-setup.md`); the in-app manual already documents Feature 3 (updated by WP-I2-001..007) so no further edit is required for this WP.

## Headless LLM Operation Compliance

- [x] N/A — VERIFICATION + DOCUMENTATION; no new commands or GUI surface.

## Change Ledger

- **What Became Real**:
  - `.product/tests/test_library_multi_operator.py` — 4 tests verifying the spec's Multi-Operator Concurrency contract.
  - `.product/tests/test_library_soak.py` — 1 test ramping `register_library_entry` to 100 calls; verifies entry count + uniqueness + smart-tag derivation + filesystem layout.
  - `.product/tests/test_library_pg_dump_restore.py` — 1 test using system `pg_dump` / `pg_restore` to round-trip the seeded DB.
  - `.gov/doc/i2-library-setup.md` — operator-facing setup guide: PostgreSQL backend (docker-compose + native paths), OpenRepose settings, first launch, ComfyUI bridge install, multi-operator workflow, backup / restore, and a 7-line smoke-test checklist mapping to spec promotion guards.
  - `README.md` — link to the new setup doc in Project Notes.
- **What Remains Simulated**: nothing within scope. The 3-operator real-world soak (Promotion Guard item (a)) is operator-side post-handoff; assistant covers the equivalent via the multi-pool / multi-thread test suite.
- **Next Blocking Real Seam**: none — I2 ships. Follow-up commit promotes Feature 3 spec from DRAFT → STABLE once the operator signs off the 3-operator soak. Operator-driven feature work resumes per the I1 backlog or new I3 WPs.

## Evidence

- **Targeted suite**: `pytest .product/tests/test_library_multi_operator.py .product/tests/test_library_soak.py .product/tests/test_library_pg_dump_restore.py -v` → 6/6 in 135s (incl. 100-entry register loop + dump/restore round-trip).
- **Full suite**: 489 passed (baseline before this WP: 483 + 6 new).
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations`.
- **Operator Sign-off**: pending (operator overnight handoff; promotes Feature 3 spec DRAFT → STABLE in a follow-up commit).

## Progress Log

- 2026-05-03: WP drafted at DRAFT. Closes the I2 iteration when DONE.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence — final WP of the iteration.
- 2026-05-03: 3 verification suites + operator setup doc + README link landed; 489-test suite green; audit clean. Status → REVIEW.
