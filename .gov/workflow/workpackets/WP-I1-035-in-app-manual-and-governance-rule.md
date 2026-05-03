# WP-I1-035 - In-App Manual + Manual-Impact Governance Rule

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (Help tab — extend with manual browser).
- **Linked Test Suite**: `.product/tests/test_manual_browser.py` (NEW); extend `.product/tests/test_audit_repo.py` for the new manual-impact check.

## Intent

Operator surfaced two coupled needs during 2026-05-03 inspection:

1. **In-app manual** so any new model / human collaborator with no context can use the app via a built-in reference. Indexed, browsable from the Help tab, written in plain Markdown.
2. **Governance rule** that product-code changes review whether the manual needs updating. Bug fixes are exempt. Enforced by audit (mechanical check that IMPLEMENTATION-class WPs at v1.1+ contain a `Manual Impact:` line).

The manual lives in `.gov/doc/manual/` as Markdown (one topic per file). The Help tab gets a tree view (index) + Markdown renderer (topic body). Audit script gains a rule that scans IMPLEMENTATION WPs for the `Manual Impact:` field; missing → exit 1.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-025 (audit script), WP-I0-004 (GUI / Help tab) — both DONE.
- **Successor(s)**: every future IMPLEMENTATION WP picks up the new rule.
- **Blocks**: none directly; future WPs at v1.1+ that don't include `Manual Impact:` will fail the audit after this lands.
- **Related**: WP-I1-026 (Workflow Version 1.1 + Research Notes audit precedent — same enforcement pattern).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements — Help tab gains manual browser.
- `.gov/AGENTS.md` — new "Manual Impact Rule" section; topology.yaml `repo_rules:` block updated.
- `.gov/templates/WP_TEMPLATE.md` — new `Manual Impact` checklist line in IMPLEMENTATION sections.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | PySide6 QTextBrowser | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTextBrowser.html | Native Qt widget for rich text + markdown rendering. setMarkdown() method handles GitHub-flavored markdown. Operator can scroll + select + copy. | adopt — no extra dep needed |
| 2026-05-03 | PySide6 QTreeView for index | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTreeView.html | Standard pattern: QFileSystemModel pointed at .gov/doc/manual/ shows the manual file tree; selection switches the QTextBrowser content. | adopt |
| 2026-05-03 | WP-I1-025 audit script pattern | local `scripts/audit-repo.ps1` | Existing script greps committed WP files for `## Research Notes` heading on IMPLEMENTATION/RESEARCH classes at Workflow Version 1.1+. Same pattern for `Manual Impact:` line on IMPLEMENTATION class. | adopt |
| 2026-05-03 | Operator GUI inspection 2026-05-03 | this session | Operator wants the rule to apply to product code changes only; bug fixes can mark `Manual Impact: N/A (bug fix)`. Audit accepts the N/A form. | adopt |

## Reality Boundary

- **Real Seam**: real `.gov/doc/manual/` folder with at least an `index.md` + topic-per-feature MD files; real Help tab in the GUI showing tree + Markdown viewer; real audit script extension that fails CI when an IMPLEMENTATION WP at v1.1+ omits the `Manual Impact:` line.
- **User-Visible Win**: a fresh assistant or human collaborator opens the GUI Help tab and sees the manual tree; clicking a topic shows formatted documentation. Every future product code change WP file says explicitly whether the manual needs updating.
- **Proof Target**: pytest covers (a) Help tab renders the manual tree; (b) selecting a topic loads its Markdown into the viewer; (c) audit fails when an IMPLEMENTATION WP at v1.1+ has no `Manual Impact:` line; (d) audit accepts `Manual Impact: N/A (bug fix)` form.

## In Scope

- New `.gov/doc/manual/index.md` + at least 5 starter topic files: `getting-started.md`, `feature-1-yaw-exporter.md`, `feature-2-calibration-overlay.md`, `feature-3-library-postgresql.md` (refers to v0.1 spec), `keyboard-shortcuts.md`. Each Markdown, indexable.
- `gui/help_pane.py`: replace static help text with a QSplitter containing a QTreeView of `.gov/doc/manual/` (file system model rooted there) + a QTextBrowser rendering the selected file's Markdown. Operator can browse + read.
- `.gov/AGENTS.md`: new "Manual Impact Rule" section: every IMPLEMENTATION-class WP at Workflow Version 1.1+ must contain a `Manual Impact:` line in the Definition Of Done OR Change Ledger section. Bug-fix WPs may use `Manual Impact: N/A (bug fix)` with brief reason.
- `.gov/topology.yaml`: `repo_rules:` block extended with `manual_impact_rule`.
- `.gov/templates/WP_TEMPLATE.md`: Definition Of Done section gains a `[ ] Manual Impact:` checklist item with the placeholder hint.
- `scripts/audit-repo.ps1`: new check enforcing the rule. Search every `WP-*.md` (workpackets/ + archive/); if Workflow Version >= 1.1 AND Packet Class == IMPLEMENTATION AND no `Manual Impact:` line, exit 1.
- `.product/tests/test_audit_repo.py`: extend with new fixtures for the manual-impact check (WP missing the field → audit fails; WP with N/A bug-fix form → passes).
- `.product/tests/test_manual_browser.py` (NEW): pytest-qt smoke for the Help tab manual browser.

## Out Of Scope

- Generating the manual from spec sections automatically (manual is hand-written Markdown for v0.1; auto-generation is a future polish).
- Multi-language manual (English only in v0.1).
- Search across manual content (operator browses by tree; full-text search is a polish followup).
- Tooltip/in-context help (separate WP if needed).

## Expected Files Touched

### Governance
- `.gov/workflow/workpackets/WP-I1-035-in-app-manual-and-governance-rule.md` (this file).
- `.gov/workflow/TASKBOARD.md`.
- `.gov/AGENTS.md` — new rule section.
- `.gov/topology.yaml` — `repo_rules:` extension.
- `.gov/templates/WP_TEMPLATE.md` — DoD checklist extension.
- `.gov/doc/manual/index.md` (NEW).
- `.gov/doc/manual/getting-started.md` (NEW).
- `.gov/doc/manual/feature-1-yaw-exporter.md` (NEW).
- `.gov/doc/manual/feature-2-calibration-overlay.md` (NEW).
- `.gov/doc/manual/feature-3-library-postgresql.md` (NEW).
- `.gov/doc/manual/keyboard-shortcuts.md` (NEW).
- `.gov/spec/openrepose_v0_1.md` — Help tab description extended.

### Product
- `.product/src/openrepose/gui/help_pane.py` — replace with manual browser.
- `.product/tests/test_manual_browser.py` (NEW).
- `.product/tests/test_audit_repo.py` (extend with manual-impact check fixtures).

### Scripts
- `scripts/audit-repo.ps1` — new manual-impact check.

### Build / Output
- `target/test-artifacts/WP-I1-035/`.

## Risks And Dependencies

- **Risk**: every existing IMPLEMENTATION WP at v1.1+ in `archive/` is missing the `Manual Impact:` line. **Mitigation**: audit grandfathers archived WPs (only enforces on NEW or IN-PROGRESS WPs going forward, OR retroactively patches archived WPs with `Manual Impact: N/A (legacy)`); decision at promotion. Recommend retroactive patch with `N/A (pre-rule)` since it's a one-shot.
- **Risk**: manual files become stale. **Mitigation**: the rule itself is the mitigation — every product change reviews manual impact.
- **Risk**: operator forgets to update the manual on real changes. **Mitigation**: audit only enforces field presence; operator must answer Yes/No truthfully. Honor system + operator self-review.

## Definition Of Done

- [ ] `.gov/doc/manual/` exists with index + 5 starter topics.
- [ ] Help tab renders the tree + Markdown viewer; selection works.
- [ ] AGENTS.md + topology.yaml + WP_TEMPLATE updated for the new rule.
- [ ] Audit script enforces `Manual Impact:` on IMPLEMENTATION WPs at v1.1+; passes on the existing live tree (after retroactive patch).
- [ ] pytest zero failures.
- [ ] Audit clean.
- [ ] Operator confirms Help tab shows manual cleanly.
- [ ] **Manual Impact**: Yes — adds new manual primitive (Help tab browser); creates 5 starter manual files. (Eat your own dog food.)

## Headless LLM Operation Compliance

- [x] N/A — Help tab is operator-facing only; no new commands or state. Manual files are read-only Markdown.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Operator approved scope; awaits explicit promotion + fast-track authorization.
- 2026-05-03: Operator authorized fast-track. Implementation:
  - 6 Markdown topic files under `.gov/doc/manual/` (index + getting-started + feature-1 + feature-2 + feature-3 + keyboard-shortcuts).
  - `gui/help_pane.py` rewritten as a manual browser (QSplitter with QListWidget topic index + QTextBrowser Markdown viewer; resolves manual root by walking up from `__file__` so packaged builds gracefully degrade with a "manual not bundled" placeholder).
  - `.gov/AGENTS.md` gains a new "Manual Impact Rule" section between Deletion Protocol and Headless Verification Checklist.
  - `.gov/topology.yaml` `repo_rules:` block extended with `manual_impact_rule` entry (rule + enforcement + manual_location + grandfather note).
  - `.gov/templates/WP_TEMPLATE.md` Definition Of Done section adds the Manual Impact checkbox with the three accepted forms.
  - `scripts/audit-repo.ps1`: 4th check `wp-manual-impact` only on `.gov/workflow/workpackets/` (active); archived WPs grandfathered. Regex tolerates markdown bold around the label (`**Manual Impact**:` matches via `Manual Impact[\*\s]{0,5}:` pattern). Output banner updated.
  - 6 active IMPLEMENTATION WPs at v1.1+ patched with `**Manual Impact**:` lines (WP-I1-034 + WP-I2-003/004/005/006/007). Existing test_audit_repo fixture updated to include Manual Impact in the v1.1 IMPLEMENTATION case.
  - 4 new audit tests + 4 new manual-browser tests cover: missing field detected, present field passes, N/A bug-fix form passes, archived WP grandfathered, DOCUMENTATION class exempt, manual root resolves, topic list populates, index loads by default, no focus-stealing APIs in help_pane.
  - Full suite 346/346 (was 342/342; +4 manual browser tests; audit tests run as part of the full suite). Audit clean. Status IN-PROGRESS -> REVIEW.
- 2026-05-03: Operator GUI inspection — clicking links inside the rendered Markdown topic (e.g. the topic list inside index.md) did nothing. QTextBrowser was rendering the links as clickable but our setOpenExternalLinks(False) without setOpenLinks(False) meant Qt swallowed them silently. Fix: setOpenLinks(False) + connect anchorClicked → _on_anchor_clicked which loads the linked .md file from the manual root (path-traversal-safe, external links ignored). _load_topic also syncs the left-column selection to the loaded topic. 3 new tests cover: in-viewer link navigation works, external links ignored, path traversal refused. Full suite 350/350. Status IN-PROGRESS -> REVIEW.
