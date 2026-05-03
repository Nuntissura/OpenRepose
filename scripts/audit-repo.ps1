[CmdletBinding()]
param()

# scripts/audit-repo.ps1
#
# Quarterly governance audit. Runs eight checks and exits non-zero on
# any violation.
#
# Original four checks (WP-I1-025 / WP-I1-035):
#   1. Disk-Agnostic Rule       - no hardcoded absolute paths in committed files.
#   2. Naming Convention Rule   - no blank-space characters in committed paths.
#   3. Research-First Rule      - IMPLEMENTATION / RESEARCH workpackets at
#                                 Workflow Version 1.1+ have a "## Research Notes"
#                                 section. Workflow Version 1.0 WPs are grandfathered.
#   4. Manual Impact Rule       - active IMPLEMENTATION workpackets at Workflow
#                                 Version 1.1+ contain a "Manual Impact:" line so
#                                 the operator has explicitly considered whether
#                                 the in-app manual needs an update. Bug-fix WPs
#                                 may use "Manual Impact: N/A (bug fix)". Only
#                                 active WPs in workpackets/ are checked;
#                                 archive/ is grandfathered (rule introduced
#                                 mid-iteration via WP-I1-035).
#
# Rule-registry checks added by WP-I3-009:
#   5. Rule-id-resolves-manual    every rule_id in topology.yaml `rule_registry.rules`
#                                 has its `manual:` value resolve to an existing
#                                 manual file or anchor. Three forms supported:
#                                   "<topic>"                    -> .gov/doc/manual/<topic>.md
#                                   "<topic>#<anchor>"           -> file + anchor
#                                   "../AGENTS.md#<anchor>"      -> .gov/AGENTS.md + anchor
#                                   "../workflow/README.md#..."  -> .gov/workflow/README.md + anchor
#                                 Anchor matching: GitHub-style slug from heading
#                                 text, OR explicit "{#anchor}" trailer on heading.
#   6. Citations-cite-real-rule-ids
#                                 every "by <RULE_ID>" citation and every
#                                 rule_id="<RULE_ID>" keyword arg in .product/src/
#                                 Python files cites a rule_id that exists in the
#                                 topology registry. Project-scoped rule families
#                                 (anything outside RUL/AMOOD/INTAKE/TARGET/REQ/SAFE)
#                                 emit an info line, not a violation.
#   7. Dispatcher-commands-have-help
#                                 every key in commands.py `_HANDLERS = { ... }`
#                                 dict appears in topology.yaml `i3_command_surface`
#                                 OR in the static pre-I3 allowlist below.
#   8. Project-rules-fresh        warn-only check for stale `last_validated_at` on
#                                 project-scoped rules in the `library_rules` PG
#                                 table. v0.1 SKIPs unless LIBRARY_DB_URL is set
#                                 and a python venv with psycopg is reachable.
#
# Exit codes:
#   0  clean (SKIP and warn lines do not fail the audit)
#   1  one or more violations
#   2  unexpected error (e.g., not a git repo)
#
# Run locally:
#   pwsh scripts/audit-repo.ps1
#
# Used by: .github/workflows/quarterly-audit.yml

$ErrorActionPreference = "Stop"

# Resolve repo root from this script's location, not from $PWD.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
try {
    $RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
} catch {
    Write-Error "audit-repo: cannot resolve repo root from script directory $ScriptDir"
    exit 2
}

Push-Location -LiteralPath $RepoRoot
try {
    $gitRoot = & git rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
        Write-Error "audit-repo: not a git repository at $RepoRoot"
        exit 2
    }
} finally {
    Pop-Location
}

$violations = New-Object System.Collections.Generic.List[string]
$infoLines  = New-Object System.Collections.Generic.List[string]
$skipLines  = New-Object System.Collections.Generic.List[string]

function Add-Violation {
    param([string]$Code, [string]$Detail)
    $violations.Add("[$Code] $Detail")
}
function Add-Info {
    param([string]$Code, [string]$Detail)
    $infoLines.Add("[$Code] $Detail")
}
function Add-Skip {
    param([string]$Code, [string]$Detail)
    $skipLines.Add("[$Code] $Detail")
}

# Listing all tracked files once.
$trackedFiles = & git -C $RepoRoot ls-files

# ---------- Check 1: hardcoded absolute paths ----------
#
# Patterns considered violations:
#   <DriveLetter>:\Projects   or  <DriveLetter>:/Projects
#   /home/<user>/...
#   C:\Users\<name>\...
#
# Allowlist:
#   - .gov/AGENTS.md line containing the word "Forbidden:" — that line documents
#     the rule itself by quoting the bad patterns. Single explicit allowance.
#   - Anything under .gov/doc/ — operator-supplies path examples live here.

$pathPatterns = @(
    '[A-Za-z]:\\Projects',
    '[A-Za-z]:/Projects',
    '/home/[A-Za-z0-9_-]+/',
    'C:\\Users\\[A-Za-z0-9_-]+\\'
)

foreach ($file in $trackedFiles) {
    if ($file.StartsWith('.gov/doc/')) { continue }

    $abs = Join-Path $RepoRoot $file
    if (-not (Test-Path -LiteralPath $abs)) { continue }

    # Skip binary files (rough heuristic: known binary extensions).
    $ext = [System.IO.Path]::GetExtension($file).ToLowerInvariant()
    if ($ext -in '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.zip', '.exe', '.dll', '.so', '.bin', '.safetensors', '.ckpt', '.pt', '.pth', '.onnx') { continue }

    $lineNo = 0
    foreach ($line in (Get-Content -LiteralPath $abs -Encoding UTF8 -ErrorAction SilentlyContinue)) {
        $lineNo++
        foreach ($pattern in $pathPatterns) {
            if ($line -match $pattern) {
                # Allowlist: AGENTS.md "Forbidden:" example line.
                if ($file -eq '.gov/AGENTS.md' -and $line -match '^Forbidden:') {
                    continue
                }
                Add-Violation 'hardcoded-path' "${file}:${lineNo}  matched /$pattern/  ::  $($line.Trim())"
            }
        }
    }
}

# ---------- Check 2: blank-space characters in committed paths ----------

foreach ($file in $trackedFiles) {
    if ($file -match ' ') {
        Add-Violation 'blank-space-path' "$file"
    }
}

# ---------- Check 3: Research Notes presence on Workflow Version 1.1+ WPs ----------

$wpDirs = @(
    (Join-Path $RepoRoot '.gov/workflow/workpackets'),
    (Join-Path $RepoRoot '.gov/workflow/archive')
)

foreach ($dir in $wpDirs) {
    if (-not (Test-Path -LiteralPath $dir)) { continue }
    Get-ChildItem -LiteralPath $dir -Filter 'WP-*.md' -File | ForEach-Object {
        $content = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8

        # Workflow Version: anything not 1.1+ is grandfathered.
        if ($content -notmatch '(?m)^\s*-\s*\*\*Workflow Version\*\*:\s*`?1\.1`?') {
            return
        }

        # Packet Class: only IMPLEMENTATION and RESEARCH are subject to the rule.
        if ($content -notmatch '(?m)^\s*-\s*\*\*Packet Class\*\*:\s*`?(IMPLEMENTATION|RESEARCH)`?') {
            return
        }

        if ($content -notmatch '(?m)^##\s+Research Notes\s*$') {
            $rel = $_.FullName.Substring($RepoRoot.Length).TrimStart('\','/').Replace('\','/')
            Add-Violation 'wp-research-notes' "$rel  IMPLEMENTATION/RESEARCH at Workflow Version 1.1+ missing '## Research Notes'"
        }
    }
}

# ---------- Check 4: Manual Impact line on active IMPLEMENTATION WPs at v1.1+ ----------
#
# Only active WPs (workpackets/) are checked. Archived WPs are grandfathered
# because this rule was introduced mid-iteration by WP-I1-035.

$activeWpDir = Join-Path $RepoRoot '.gov/workflow/workpackets'
if (Test-Path -LiteralPath $activeWpDir) {
    Get-ChildItem -LiteralPath $activeWpDir -Filter 'WP-*.md' -File | ForEach-Object {
        $content = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8

        if ($content -notmatch '(?m)^\s*-\s*\*\*Workflow Version\*\*:\s*`?1\.1`?') {
            return
        }
        if ($content -notmatch '(?m)^\s*-\s*\*\*Packet Class\*\*:\s*`?IMPLEMENTATION`?') {
            return
        }
        # Allow optional markdown bold around the label, then a colon, then
        # any text. Examples that match: "Manual Impact: Yes",
        # "**Manual Impact**: N/A (bug fix)", "  - **Manual Impact**: ..."
        if ($content -notmatch '(?m)Manual Impact[\*\s]{0,5}:') {
            $rel = $_.FullName.Substring($RepoRoot.Length).TrimStart('\','/').Replace('\','/')
            Add-Violation 'wp-manual-impact' "$rel  active IMPLEMENTATION at Workflow Version 1.1+ missing 'Manual Impact:' line"
        }
    }
}

# ---------- Helpers for rule-registry checks ----------

# Parse rule_registry.rules from topology.yaml. The block is a flat list of
# entries shaped:
#   <RULE_ID>: { name: "...", severity: <enum>, manual: "<link>", short: "...", ... }
# We restrict parsing to lines between the "rule_registry:" header and the next
# top-level YAML key, and then between the "rules:" sub-key and the next
# sibling sub-key (e.g. "project_scoped:").
function Get-RuleRegistry {
    param([string]$TopologyPath)

    if (-not (Test-Path -LiteralPath $TopologyPath)) {
        throw "topology.yaml not found at $TopologyPath"
    }

    $lines = Get-Content -LiteralPath $TopologyPath -Encoding UTF8

    $inRegistry = $false
    $inRules    = $false
    $registry   = @{}

    foreach ($line in $lines) {
        if ($line -match '^rule_registry:\s*$') {
            $inRegistry = $true
            continue
        }
        if ($inRegistry) {
            # Top-level YAML key terminates the registry block.
            if ($line -match '^[A-Za-z]') {
                $inRegistry = $false
                $inRules    = $false
                continue
            }
            if ($line -match '^\s{2}rules:\s*$') {
                $inRules = $true
                continue
            }
            # Sibling 2-space sub-key terminates the rules sub-block.
            if ($inRules -and $line -match '^\s{2}[A-Za-z]') {
                $inRules = $false
                continue
            }
        }

        if ($inRules) {
            # RULE_ID: { ... manual: "<link>" ... }
            $m = [regex]::Match($line, '^\s+([A-Z][A-Z0-9]*-\d+):\s*\{[^}]*?manual:\s*"([^"]+)"[^}]*\}')
            if ($m.Success) {
                $rid = $m.Groups[1].Value
                $mlink = $m.Groups[2].Value
                $registry[$rid] = $mlink
            }
        }
    }

    return $registry
}

# GitHub-style slug for a heading text. Lowercase, drop punctuation other
# than dash and space, collapse spaces to dashes, then collapse runs of dashes.
function Get-HeadingSlug {
    param([string]$Heading)
    $s = $Heading.ToLowerInvariant()
    $s = ($s -replace '[^a-z0-9 \-]', '')
    $s = ($s -replace '\s+', '-')
    $s = ($s -replace '-+', '-')
    return $s.Trim('-')
}

# Read every anchor from a markdown file. Anchors are either explicit
# "{#anchor-name}" trailers on heading lines or GitHub-slug forms.
function Get-MarkdownAnchors {
    param([string]$MdPath)

    $anchors = New-Object System.Collections.Generic.HashSet[string]
    if (-not (Test-Path -LiteralPath $MdPath)) {
        return $anchors
    }

    foreach ($line in (Get-Content -LiteralPath $MdPath -Encoding UTF8)) {
        if ($line -match '^(#{1,6})\s+(.+?)\s*$') {
            $headingText = $Matches[2].Trim()

            # Explicit trailer: "## Title {#explicit-anchor}"
            $explicit = [regex]::Match($headingText, '\{#([A-Za-z0-9_\-]+)\}\s*$')
            if ($explicit.Success) {
                $null = $anchors.Add($explicit.Groups[1].Value)
                $headingText = ($headingText -replace '\{#[A-Za-z0-9_\-]+\}\s*$', '').Trim()
            }

            # Always also add the GitHub-style slug.
            $slug = Get-HeadingSlug $headingText
            if ($slug) { $null = $anchors.Add($slug) }
        }
    }

    return $anchors
}

# Resolve a manual: link (as used in topology.yaml rule_registry) against
# the on-disk manual + governance docs. Returns $null on success, or a
# string describing why resolution failed.
function Test-ManualLink {
    param([string]$Link, [string]$RepoRoot)

    if (-not $Link) { return "empty link" }

    # Forms:
    #   ../AGENTS.md#anchor
    #   ../workflow/README.md#anchor
    #   topic
    #   topic#anchor

    $anchor = $null
    $target = $Link
    $hashIdx = $Link.IndexOf('#')
    if ($hashIdx -ge 0) {
        $target = $Link.Substring(0, $hashIdx)
        $anchor = $Link.Substring($hashIdx + 1)
    }

    # Map link target to an on-disk markdown path.
    $mdPath = $null
    if ($target -eq '../AGENTS.md') {
        $mdPath = Join-Path $RepoRoot '.gov/AGENTS.md'
    } elseif ($target -eq '../workflow/README.md') {
        $mdPath = Join-Path $RepoRoot '.gov/workflow/README.md'
    } elseif ($target -match '^[A-Za-z0-9_\-]+(\.md)?$') {
        $topic = if ($target.EndsWith('.md')) { $target } else { "$target.md" }
        $mdPath = Join-Path $RepoRoot ".gov/doc/manual/$topic"
    } else {
        return "unrecognized link form: '$Link'"
    }

    if (-not (Test-Path -LiteralPath $mdPath)) {
        return "manual file not found: $mdPath"
    }

    if ($anchor) {
        $anchors = Get-MarkdownAnchors $mdPath
        if (-not $anchors.Contains($anchor)) {
            return "anchor '#$anchor' not found in $mdPath"
        }
    }

    return $null
}

$topologyPath = Join-Path $RepoRoot '.gov/topology.yaml'

# ---------- Check 5: rule_id resolves to manual anchor ----------

$registry = $null
try {
    $registry = Get-RuleRegistry -TopologyPath $topologyPath
} catch {
    Add-Violation 'rule-id-resolves-manual' "could not parse rule_registry from topology.yaml: $_"
}

if ($registry -and $registry.Count -eq 0) {
    Add-Violation 'rule-id-resolves-manual' "rule_registry parse returned 0 entries (regex out of date?)"
}

if ($registry -and $registry.Count -gt 0) {
    foreach ($rid in $registry.Keys) {
        $link = $registry[$rid]
        $err = Test-ManualLink -Link $link -RepoRoot $RepoRoot
        if ($err) {
            Add-Violation 'rule-id-resolves-manual' "$rid -> '$link': $err"
        }
    }
}

# ---------- Check 6: citations cite real rule_ids ----------
#
# Two regex shapes scanned in .product/src/**/*.py:
#   "by <RULE_ID>"               (literal in error strings)
#   rule_id="<RULE_ID>"          (keyword arg to format_citation)
#   rule_id='<RULE_ID>'
#
# Global families (RUL-, AMOOD-, INTAKE-, TARGET-, REQ-, SAFE-) MUST be in
# the registry. Other prefixes are project-scoped (operator-authored, lives
# in DB at runtime); those emit info, not violation.

$globalFamilies = @('RUL', 'AMOOD', 'INTAKE', 'TARGET', 'REQ', 'SAFE')
# Families that look like rule_ids syntactically but are reserved for
# something else, so the audit silently ignores them in citation scanning.
$nonRuleFamilies = @('WP')   # workpacket IDs (WP-I3-003, WP-I0-001, ...)
$pyFiles = Get-ChildItem -LiteralPath (Join-Path $RepoRoot '.product/src') -Recurse -Filter '*.py' -File -ErrorAction SilentlyContinue

# Literal citation: `by <RULE_ID> (<rule_name>)`. Open paren after the ID
# is the disambiguator — without it, "set by WP-I0-003 wiring" (a comment
# referencing a workpacket) would false-positive. Workpacket IDs and rule
# IDs are syntactically identical otherwise.
$citationLiteralPattern = '\bby\s+([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+)\s+\('
$citationKwargPattern   = 'rule_id\s*=\s*["'']([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+)["'']'

if ($pyFiles) {
    foreach ($py in $pyFiles) {
        $rel = $py.FullName.Substring($RepoRoot.Length).TrimStart('\','/').Replace('\','/')
        $lineNo = 0
        foreach ($line in (Get-Content -LiteralPath $py.FullName -Encoding UTF8)) {
            $lineNo++

            $found = New-Object System.Collections.Generic.List[string]
            $m = [regex]::Matches($line, $citationLiteralPattern)
            foreach ($hit in $m) { $found.Add($hit.Groups[1].Value) }
            $m = [regex]::Matches($line, $citationKwargPattern)
            foreach ($hit in $m) { $found.Add($hit.Groups[1].Value) }

            foreach ($rid in $found) {
                $family = ($rid -split '-')[0]
                if ($nonRuleFamilies -contains $family) {
                    continue
                }
                if ($globalFamilies -contains $family) {
                    if (-not ($registry -and $registry.ContainsKey($rid))) {
                        Add-Violation 'citations-cite-real-rule-ids' "${rel}:${lineNo}  $rid not in topology rule_registry  ::  $($line.Trim())"
                    }
                } else {
                    Add-Info 'citations-cite-real-rule-ids' "${rel}:${lineNo}  $rid (project-scoped family '$family'; not validated by audit)"
                }
            }
        }
    }
}

# ---------- Check 7: dispatcher commands have help (declared in topology) ----------
#
# Read commands.py _HANDLERS = { ... } block; each "<name>": _h_<name>.
# Verify each <name> appears in topology.yaml `i3_command_surface` OR in the
# pre-I3 allowlist below (Feature 1 + Feature 2 + Feature 3 library commands
# documented in feature-*-*.md manual topics).

$preI3Allowlist = @(
    # Feature 1 — yaw exporter (WP-I0-001..004, WP-I1-022/023/027/030)
    'import_portrait', 'set_yaw', 'set_yaw_bin', 'export_single', 'export_batch',
    'snapshot', 'dump_rig', 'dump_state', 'clear_outputs',
    # Feature 2 — calibration overlay (WP-I1-001/028/034)
    'set_calibration_points', 'dump_calibration', 'clear_calibration', 'delete_markers',
    'get_calibration_status',
    # Feature 1 polish (WP-I1-017/029/030/031/032/033)
    'set_body_part_visibility', 'get_body_part_visibility',
    'set_marker_visibility', 'get_marker_visibility', 'reset_marker_visibility',
    'set_frame_scale', 'set_frame_offset', 'set_frame_anchor', 'reset_frame', 'get_frame',
    'dump_settings',
    # Feature 3 — OpenPose library (WP-I2-004)
    'register_library_entry', 'update_library_entry', 'delete_library_entry',
    'library_search', 'get_library_entry', 'set_library_tags', 'dump_library_schema'
)

$commandsPath = Join-Path $RepoRoot '.product/src/openrepose/commands.py'

# Parse i3_command_surface from topology.yaml.
function Get-I3CommandSurface {
    param([string]$TopologyPath)

    $cmds = New-Object System.Collections.Generic.HashSet[string]
    if (-not (Test-Path -LiteralPath $TopologyPath)) { return $cmds }

    $inSurface = $false
    foreach ($line in (Get-Content -LiteralPath $TopologyPath -Encoding UTF8)) {
        if ($line -match '^i3_command_surface:\s*$') {
            $inSurface = $true
            continue
        }
        if ($inSurface -and $line -match '^[A-Za-z]') {
            $inSurface = $false
            continue
        }
        if ($inSurface) {
            $m = [regex]::Match($line, '^\s+-\s+([a-z_][a-z0-9_]*)\b')
            if ($m.Success) {
                $null = $cmds.Add($m.Groups[1].Value)
            }
        }
    }
    return $cmds
}

$i3Surface = Get-I3CommandSurface -TopologyPath $topologyPath

if (-not (Test-Path -LiteralPath $commandsPath)) {
    Add-Violation 'dispatcher-commands-have-help' "commands.py not found at $commandsPath"
} else {
    $commandsRaw = Get-Content -LiteralPath $commandsPath -Raw -Encoding UTF8
    $startIdx = $commandsRaw.IndexOf('_HANDLERS = {')
    if ($startIdx -lt 0) {
        Add-Violation 'dispatcher-commands-have-help' "_HANDLERS dict not located in commands.py"
    } else {
        $endIdx = $commandsRaw.IndexOf('}', $startIdx)
        if ($endIdx -lt 0) {
            Add-Violation 'dispatcher-commands-have-help' "_HANDLERS dict close-brace not found in commands.py"
        } else {
            $block = $commandsRaw.Substring($startIdx, ($endIdx - $startIdx + 1))
            $matches = [regex]::Matches($block, '"([a-z_][a-z0-9_]*)"\s*:\s*_h_[a-z_]+')
            if ($matches.Count -eq 0) {
                Add-Violation 'dispatcher-commands-have-help' "_HANDLERS parse returned 0 commands (regex out of date?)"
            }
            foreach ($mm in $matches) {
                $cmd = $mm.Groups[1].Value
                if ($preI3Allowlist -contains $cmd) { continue }
                if ($i3Surface.Contains($cmd)) { continue }
                Add-Violation 'dispatcher-commands-have-help' "$cmd not in topology i3_command_surface and not in pre-I3 allowlist"
            }
        }
    }
}

# ---------- Check 8: project-scoped rules freshness ----------
#
# Warn-only check. Reads library_rules.last_validated_at; rows older than 30
# days are surfaced as warn lines (do not fail audit). If LIBRARY_DB_URL is
# not set, emit a single SKIP line — running the audit must not require
# Postgres on a fresh clone.

$libraryDbUrl = $env:LIBRARY_DB_URL
if (-not $libraryDbUrl) {
    Add-Skip 'project-rules-fresh' "LIBRARY_DB_URL not set; DB-backed freshness check skipped (v0.1 behavior)"
} else {
    $venvPy = Join-Path $RepoRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPy)) {
        Add-Skip 'project-rules-fresh' "venv python not found at $venvPy; DB-backed check skipped"
    } else {
        $pyScript = @'
import os, sys
try:
    import psycopg
except ImportError:
    print("SKIP: psycopg not installed", flush=True); sys.exit(0)
url = os.environ["LIBRARY_DB_URL"]
try:
    with psycopg.connect(url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rule_id, scope_type, last_validated_at "
                        "FROM library_rules "
                        "WHERE last_validated_at IS NULL "
                        "   OR last_validated_at < (now() - interval '30 days') "
                        "ORDER BY rule_id")
            for rid, scope, ts in cur.fetchall():
                ts_str = ts.isoformat() if ts else "NULL"
                print(f"WARN: {rid} scope={scope} last_validated_at={ts_str}", flush=True)
except Exception as e:
    print(f"SKIP: {e}", flush=True); sys.exit(0)
'@
        $tmp = Join-Path $env:TEMP "audit-rules-fresh-$([guid]::NewGuid().ToString('N')).py"
        Set-Content -LiteralPath $tmp -Value $pyScript -Encoding UTF8
        try {
            $pyOut = & $venvPy $tmp 2>&1
            foreach ($line in $pyOut) {
                if ($line -match '^WARN:\s*(.+)$') {
                    Add-Info 'project-rules-fresh' $Matches[1]
                } elseif ($line -match '^SKIP:\s*(.+)$') {
                    Add-Skip 'project-rules-fresh' $Matches[1]
                }
            }
        } finally {
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        }
    }
}

# ---------- Report ----------

$checkNames = @(
    'hardcoded-paths',
    'blank-space-paths',
    'wp-research-notes',
    'wp-manual-impact',
    'rule-id-resolves-manual',
    'citations-cite-real-rule-ids',
    'dispatcher-commands-have-help',
    'project-rules-fresh'
)

Write-Output ""
Write-Output "audit-repo  root=$RepoRoot  tracked=$($trackedFiles.Count)"
Write-Output "checks: $($checkNames -join '  ')"

if ($infoLines.Count -gt 0) {
    Write-Output ""
    Write-Output "audit-repo: INFO  $($infoLines.Count) note(s):"
    foreach ($i in $infoLines) {
        Write-Output "  $i"
    }
}

if ($skipLines.Count -gt 0) {
    Write-Output ""
    Write-Output "audit-repo: SKIP  $($skipLines.Count) deferred check(s):"
    foreach ($s in $skipLines) {
        Write-Output "  $s"
    }
}

if ($violations.Count -eq 0) {
    Write-Output ""
    Write-Output "audit-repo: OK   no violations"
    exit 0
}

Write-Output ""
Write-Output "audit-repo: ERR  $($violations.Count) violation(s):"
foreach ($v in $violations) {
    Write-Output "  $v"
}
exit 1
