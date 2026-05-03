# WP-I1-030 - Export Polish (PNG + Pretty JSON + Slug Sanitization)

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / Output Formats (extend with PNG + pretty JSON guarantees), Feature 1 / Inputs (avatar slug sanitization).
- **Linked Test Suite**: extend `.product/tests/test_command_handlers.py` + new `.product/tests/test_export_png_and_json_format.py`.
- **Linked Check Script**: N/A.

## Intent

Three small operator-facing fixes bundled together because they all touch the export path and were surfaced together during WP-I1-017 GUI inspection on 2026-05-03:

1. **PNG output alongside JSON.** `export_single` / `export_batch` currently write only the JSON keypoint file. The renderer (`render/draw_openpose.render_openpose_to_png`) exists but is not called. Operator expected a PNG too — they need the rendered wireframe image, not just the keypoint coordinates.
2. **Pretty-printed JSON.** `serialize_to_string(..., indent=None)` produces a single-line wall of numbers; the operator could not eyeball-verify which keypoints were zeroed after toggling visibility. Switch to `indent=2`. Spec contract is unchanged (whitespace-insensitive JSON).
3. **Avatar slug sanitization.** When the operator opens a portrait via File → Open, `main_window._on_open` uses `Path(path).stem` raw as the avatar slug. A filename like `0-degree frontal view Master Base ChatGPT Image May 1, 2026, 05_03_37 AM.png` produces a folder name containing spaces and commas. Sanitize: lowercase, replace runs of non-`[a-z0-9-]` with single `-`, trim leading/trailing `-`.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (DONE), WP-I1-027 (REVIEW — provides the export folder primitive this WP writes into).
- **Successor(s)**: none planned.
- **Blocks**: none.
- **Blocked-By**: none.
- **Related**: WP-I1-017 + WP-I1-029 + WP-I1-023 (the visibility / frame WPs whose effect on JSON is hard to verify without pretty-printing).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / Output Formats — extend with PNG output guarantee + JSON pretty-print.
- `.gov/spec/openrepose_v0_1.md` Feature 1 / Inputs — extend with the slug sanitization rule.
- `.gov/AGENTS.md` Naming Convention Rule — sanitization brings operator-supplied slugs into compliance with the no-blank-space convention.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Existing `render/draw_openpose.render_openpose_to_png` | local | Already implements the PNG renderer; just needs to be called from the export handlers next to the JSON write. | adopt |
| 2026-05-03 | Operator UX feedback 2026-05-03 | this session | Single-line JSON is unreadable; pretty-printing at `indent=2` matches `dump_state` / `dump_calibration` formatting. | adopt |
| 2026-05-03 | Slugify pattern (Python ecosystem) | python-slugify, django.utils.text.slugify | Standard pattern: NFKD-normalize, strip diacritics, lowercase, replace runs of non-alphanumerics with `-`, trim. Hand-rolled regex (`re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")`) covers our case without a new dep. | adopt (hand-rolled) |
| 2026-05-03 | OpenPose / DWPose JSON consumers (ComfyUI) | upstream `RenderPeopleKps` | Whitespace-insensitive — pretty-printing the JSON does not change downstream behavior. | adopt |

Decision: PNG output always-on (operator's clear expectation; cost is one cv2.imwrite per export). JSON pretty-print always-on (matches the rest of OpenRepose's JSON outputs; downstream consumers don't care). Slug sanitization applied on new imports only (existing operator folders are not renamed — that would be destructive and potentially break their workflow); operator can manually rename old folders if they want.

## Reality Boundary

- **Real Seam**: `_h_export_single` and `_h_export_batch` write a `.png` next to each `.json` (matching basename). `serialize_to_string` defaults to `indent=2`. `main_window._on_open` (and CLI `gui` subcommand) sanitize the avatar slug.
- **User-Visible Win**: operator opens a portrait, exports, and finds both `aeri_yaw_0.json` and `aeri_yaw_0.png` in the export folder. Opening the JSON in any editor shows readable indented structure where `[0.0, 0.0, 0.0]` triples are immediately visible. Operator-supplied filenames with spaces / commas / mixed case produce folder names like `aeri-master-2026-05-01` instead of `0-degree frontal view Master Base ChatGPT Image May 1, 2026, 05_03_37 AM`.
- **Proof Target**: pytest covers (a) PNG file exists alongside JSON for both single + batch; (b) PNG is non-empty and decodes; (c) JSON parsed by `json.loads` survives round-trip and contains `\n` characters (pretty-printed); (d) slug sanitization unit tests cover spaces, commas, mixed case, leading/trailing punctuation, all-special-char edge case (degenerates to `unknown-<timestamp>`). Manual: operator opens a real long-named portrait and confirms the resulting folder name is readable.
- **Allowed Temporary Fallbacks**: existing operator export folders are NOT renamed (sanitization applies on new imports only).
- **Promotion Guard**: do not promote until operator confirms a real export produces both PNG and JSON in a sanitized folder.

## In Scope

- `.product/src/openrepose/openpose_serialize.py`: `serialize_to_string()` default `indent` changes from `None` to `2`. Existing callers passing `indent=None` keep that behavior; only the dispatcher's export handlers benefit.
- `.product/src/openrepose/commands.py`: `_h_export_single` and `_h_export_batch` write the rendered PNG alongside the JSON via `render_openpose_to_png` (passing the same `body_part_visibility` / `marker_visibility` / `frame` state). Returned `payload["files"]` includes both paths.
- `.product/src/openrepose/util/slugify.py` (NEW): `sanitize_avatar_slug(text: str, fallback: str = "unknown") -> str` helper. Rules: NFKD normalize → ASCII strip → lowercase → replace `[^a-z0-9]+` with `-` → strip `-`. Empty result → fallback. No new dep.
- `.product/src/openrepose/gui/main_window.py`: `_on_open` calls `sanitize_avatar_slug(Path(path).stem)` instead of the raw stem.
- `.product/src/openrepose/cli.py`: `gui` and `import` subcommands sanitize the slug if the operator passes a non-conforming one (with a warn log if mutated).
- Tests: per-condition slugify tests; PNG existence + non-empty + decodable; JSON pretty-print presence; manifest still includes both paths.

## Out Of Scope

- Renaming existing operator folders (would be destructive; if operator wants to clean up old folders they do it manually).
- Configurable indent / PNG-on-off flags. v0.1 ships with always-on; if the operator later wants a no-PNG mode for performance, that's a separate WP.
- A separate "Reframer-only" PNG output (e.g. just the rendered frame without keypoints) — out of scope.
- Support for other image formats (JPEG, WebP). PNG only in v0.1.
- Backporting sanitization to dispatcher-level `import_portrait` command when called by the LLM. The LLM is expected to supply a sane avatar_slug; sanitization is applied silently.

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-030-export-polish-png-pretty-json-slug.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row at READY when promoted.
- `.gov/spec/openrepose_v0_1.md` — Feature 1 / Output Formats + Inputs short extension.

### Product (`.product/`)
- `.product/src/openrepose/openpose_serialize.py` — change default indent.
- `.product/src/openrepose/commands.py` — write PNG in both export handlers.
- `.product/src/openrepose/util/__init__.py` (NEW), `.product/src/openrepose/util/slugify.py` (NEW).
- `.product/src/openrepose/gui/main_window.py` — sanitize on file-open.
- `.product/src/openrepose/cli.py` — sanitize on CLI path.
- `.product/tests/test_export_png_and_json_format.py` (NEW).
- `.product/tests/test_slugify.py` (NEW).

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-030/`

## Risks And Dependencies

- **Risk**: PNG render adds latency to batch export (13 PNGs vs 13 JSONs). **Mitigation**: render is cheap (~30ms per image; 13 angles = ~400ms added to a batch). Acceptable.
- **Risk**: existing tests assert exactly-N files in `payload["files"]`. **Mitigation**: bump the count in `test_export_batch_default_13_angles` (was 14: 13 JSON + 1 manifest; becomes 27: 13 JSON + 13 PNG + 1 manifest).
- **Risk**: pretty-printing increases JSON file size ~3x. **Mitigation**: trivially small; not a concern.
- **Risk**: slug sanitization could collide with an existing folder when two different filenames sanitize to the same slug. **Mitigation**: do not deduplicate at sanitization time; the operator can disambiguate via the run_tag in the batch path or by setting an explicit slug in Options.

## Definition Of Done

- [ ] `serialize_to_string` default indent is 2; export handlers benefit; `dump_state` / `dump_calibration` already pretty-print.
- [ ] `_h_export_single` writes PNG alongside JSON.
- [ ] `_h_export_batch` writes PNGs for every angle alongside JSONs; manifest includes both paths.
- [ ] `sanitize_avatar_slug()` helper covers spaces, commas, mixed case, NFKD-normalizable characters, leading/trailing punctuation, all-special degenerates to fallback.
- [ ] `main_window._on_open` and `cli.py` use the sanitizer.
- [ ] Existing `test_command_handlers.test_export_batch_default_13_angles` updated for the new file count.
- [ ] `pytest` zero failures; junit XML at `target/test-artifacts/WP-I1-030/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms manual export produces both PNG and JSON in a sanitized folder.

## Test Coverage Plan

### Functional Flow Tests
- [ ] `export_single` writes both `<slug>_yaw_<bin>.json` and `<slug>_yaw_<bin>.png`.
- [ ] `export_batch` writes 13 JSONs + 13 PNGs + 1 manifest.
- [ ] PNG decodes via `cv2.imread` and is non-empty.
- [ ] JSON contains newline characters (pretty-printed) and round-trips through `json.loads` -> `json.dumps`.
- [ ] Slugify: `"My Portrait, 2026-05-01.png"` → `"my-portrait-2026-05-01"`; `"   "` → fallback; `"AERI Master.PNG"` → `"aeri-master"`.

### Code Correctness Tests
- [ ] PNG render honors `body_part_visibility` + `marker_visibility` + `frame` (same as the snapshot path).
- [ ] PNG canvas size matches the JSON's `canvas_width` / `canvas_height`.
- [ ] Manifest `files` list includes every PNG path.

### Red-Team / Abuse Tests
- [ ] Slugify on a path containing `..`: `..` does not appear in the resulting slug (no path traversal).
- [ ] Slugify on a path containing emoji / RTL text: degenerates to fallback or sanitized ASCII; never raises.

### Performance / Reliability Tests
- [ ] Batch of 13 angles completes within 1.5x of pre-WP baseline.

## Rollback Plan

- Files to revert: `openpose_serialize.py`, `commands.py`, `util/slugify.py`, `gui/main_window.py`, `cli.py`, the new test files, the spec extension, the taskboard row.
- Files to keep: previously written exports (no schema change).
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: PNG always-on (no toggle). Reason: the operator clearly expects PNG; toggling adds UI surface for no real benefit at this stage.
- 2026-05-03: JSON pretty-print always-on (no toggle). Reason: matches dump_state / dump_calibration; downstream JSON consumers don't care about whitespace.
- 2026-05-03: Slug sanitization applies to NEW imports only. Reason: renaming existing operator folders would be destructive and risk breaking external workflows.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row + spec extension.
2. Implementation: slugify util + PNG export + pretty-print default + GUI / CLI wiring.
3. Verification: pytest + junit XML + manual operator export confirmation.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_export_png_and_json_format.py .product/tests/test_slugify.py --junitxml=target/test-artifacts/WP-I1-030/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-030/pytest_results.xml` plus operator-confirmed sample PNG + pretty JSON paths.

## Headless LLM Operation Compliance

- [ ] N/A — no new commands, no new state, no new snapshot target. PNG output is added to the existing `export_single` / `export_batch` payloads (LLM agent gets paths to both PNG + JSON in `payload["files"]`).
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` from any path.
- [ ] No modal dialogs.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Awaits operator promotion to READY.
