# WP-I2-008 - Library Multi-Operator Tests + Operator Setup Doc

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
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

- [ ] All 4 verification items pass.
- [ ] Setup doc covers docker-compose path + native Postgres install + ComfyUI custom node install + smoke test.
- [ ] pytest zero failures; audit clean.
- [ ] Operator confirms 3-operator concurrent session works (per the spec Promotion Guard) — closes I2 + promotes Feature 3 spec from DRAFT to STABLE in a follow-up commit.

## Headless LLM Operation Compliance

- [x] N/A — VERIFICATION + DOCUMENTATION.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT. Closes the I2 iteration when DONE.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence — final WP of the iteration.
