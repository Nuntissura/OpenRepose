[CmdletBinding()]
param()

# scripts/audit-repo.ps1
#
# Quarterly governance audit. Checks three rules from .gov/AGENTS.md:
#
#   1. Disk-Agnostic Rule       - no hardcoded absolute paths in committed files.
#   2. Naming Convention Rule   - no blank-space characters in committed paths.
#   3. Research-First Rule      - IMPLEMENTATION / RESEARCH workpackets at
#                                 Workflow Version 1.1+ have a "## Research Notes"
#                                 section. Workflow Version 1.0 WPs are grandfathered.
#
# Exit codes:
#   0  clean
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

function Add-Violation {
    param([string]$Code, [string]$Detail)
    $violations.Add("[$Code] $Detail")
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

# ---------- Report ----------

Write-Output ""
Write-Output "audit-repo  root=$RepoRoot  tracked=$($trackedFiles.Count)"
Write-Output "checks: hardcoded-paths  blank-space-paths  wp-research-notes"

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
