[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path,

    [switch]$Yes
)

# scripts/safe-delete.ps1
#
# Operator-side guarded deletion. Companion to .claude/commands/safe-delete.md.
#
# Why this exists:
#   Past disasters: wrong git tooling and accidental directory-climbing deleted
#   entire repos, and once an entire disk. This script is the only sanctioned
#   way to delete tracked files or repo folders on the operator side.
#
# Usage:
#   .\scripts\safe-delete.ps1 target\test-artifacts\WP-I1-001
#   .\scripts\safe-delete.ps1 outputs\.runtime\snapshots\old.png -Yes
#
# Refuses:
#   - absolute paths (drive letters, leading slashes, UNC paths)
#   - paths containing ".."
#   - paths that resolve outside the repo root
#   - the repo root itself or .git / .gov / .product / scripts wholesale
#
# Logs to:
#   target/safe-delete-log/<YYYYMMDD-HHMMSS>.log

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..")).Path

function Refuse {
    param([string]$Reason)
    Write-Output "[safe-delete] ERR  refused: $Reason"
    exit 2
}

# 1. Argument hygiene.
if ([string]::IsNullOrWhiteSpace($Path)) {
    Refuse "empty path"
}
if ($Path -match '^[A-Za-z]:[\\/]' -or $Path.StartsWith('\\') -or $Path.StartsWith('/')) {
    Refuse "absolute path not allowed (must be relative to repo root)"
}
if ($Path -match '\.\.') {
    Refuse "path contains '..'; directory-climbing not allowed"
}

# 2. Resolve under repo root and verify containment.
$candidate = Join-Path $RepoRoot $Path
if (-not (Test-Path -LiteralPath $candidate)) {
    Refuse "target does not exist: $candidate"
}
$resolved = (Resolve-Path -LiteralPath $candidate).Path

# Containment check (case-insensitive on Windows).
$rootPrefix = $RepoRoot.TrimEnd('\','/')
if ($resolved -ieq $rootPrefix) {
    Refuse "resolved path equals the repo root"
}
if (-not $resolved.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Refuse "resolved path escapes the repo root: $resolved"
}

# 3. Forbidden top-level targets.
$forbiddenTopLevel = @(".git", ".gov", ".product", "scripts")
$relativeFromRoot  = $resolved.Substring($rootPrefix.Length).TrimStart('\','/')
$firstSegment      = ($relativeFromRoot -split '[\\/]')[0]

if ($forbiddenTopLevel -contains $firstSegment -and ($relativeFromRoot -eq $firstSegment)) {
    Refuse "wholesale deletion of $firstSegment is never allowed; name a narrower target"
}
if ($firstSegment -eq ".git") {
    Refuse "deletions inside .git/ are forbidden; use git itself for repo surgery"
}

# 4. Inspect the target.
$entry = Get-Item -LiteralPath $resolved -Force
$isDir = $entry.PSIsContainer

if ($isDir) {
    $stats = Get-ChildItem -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
    $entryCount = ($stats.Count) + 1  # children plus the directory itself
    $totalBytes = if ($stats.Sum) { $stats.Sum } else { 0 }
} else {
    $entryCount = 1
    $totalBytes = $entry.Length
}
$lastWrite = $entry.LastWriteTime.ToString("yyyy-MM-ddTHH:mm:ss")

Write-Output "[safe-delete] root:        $RepoRoot"
Write-Output "[safe-delete] requested:   $Path"
Write-Output "[safe-delete] resolved:    $resolved"
Write-Output "[safe-delete] kind:        $(if ($isDir) { 'directory' } else { 'file' })"
Write-Output "[safe-delete] entries:     $entryCount"
Write-Output "[safe-delete] total_bytes: $totalBytes"
Write-Output "[safe-delete] last_write:  $lastWrite"

# 5. Confirmation.
if (-not $Yes) {
    Write-Output ""
    Write-Output "Type DELETE to proceed (anything else aborts):"
    $answer = Read-Host
    if ($answer -cne "DELETE") {
        Refuse "operator did not confirm with literal token DELETE"
    }
}

# 6. Log to target/safe-delete-log/.
$logDir = Join-Path $RepoRoot "target/safe-delete-log"
if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "$timestamp.log"
@(
    "timestamp:   $timestamp",
    "root:        $RepoRoot",
    "requested:   $Path",
    "resolved:    $resolved",
    "kind:        $(if ($isDir) { 'directory' } else { 'file' })",
    "entries:     $entryCount",
    "total_bytes: $totalBytes",
    "last_write:  $lastWrite",
    "confirmed:   $(if ($Yes) { '-Yes flag' } else { 'DELETE token' })"
) | Out-File -FilePath $logFile -Encoding utf8

# 7. Delete.
Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop

# 8. Verify.
if (Test-Path -LiteralPath $resolved) {
    Write-Output "[safe-delete] ERR  removal failed; path still exists"
    exit 3
}

Write-Output "[safe-delete] OK   removed: $resolved entries=$entryCount bytes=$totalBytes log=$logFile"
exit 0
