# OpenRepose Tests

Test suite for OpenRepose product code. Tests run against the locked yaw terminology and the spec contract; workpackets cite the test files they add.

## Layout

```text
.product/tests/
  README.md           this file
  conftest.py         (future) pytest fixtures
  test_*.py           (future) test modules paired with .product/src/openrepose/ modules
```

## Running

```powershell
pytest .product/tests
```

Test artifacts (junit XML, coverage HTML) write to `target/test-artifacts/` (gitignored). Workpacket Evidence sections cite the artifact paths.

## Rules

- No test changes the locked yaw terminology or the OpenPose schema contract.
- Tests use deterministic seeds when randomness is involved.
- Tests do not write to `outputs/` unless the test explicitly verifies an export feature; in that case the test cleans up after itself.
- A workpacket of class `IMPLEMENTATION` must include matching tests under this folder.
- A workpacket of class `VERIFICATION` may add tests for already-implemented behavior.
