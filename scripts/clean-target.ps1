[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

$folders = @("target", "dist", "outputs")
$keepNames = @(".gitkeep", "README.md")

Write-Output "Cleaning build / installer / output folders in: $RepoRoot"
if ($DryRun) {
    Write-Output "(dry-run mode; no files will be deleted)"
}
Write-Output ""

$totalRemoved = 0

foreach ($folder in $folders) {
    $path = Join-Path $RepoRoot $folder
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Output "  $folder/ : missing (skipping)"
        continue
    }

    $entries = Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue |
        Where-Object { $keepNames -notcontains $_.Name }

    if (-not $entries -or $entries.Count -eq 0) {
        Write-Output "  $folder/ : already clean"
        continue
    }

    Write-Output "  $folder/ : removing $($entries.Count) entr$(if ($entries.Count -eq 1) { 'y' } else { 'ies' })"
    foreach ($entry in $entries) {
        Write-Output "    - $($entry.Name)"
        if (-not $DryRun) {
            Remove-Item -LiteralPath $entry.FullName -Recurse -Force -ErrorAction Stop
            $totalRemoved += 1
        }
    }
}

Write-Output ""
if ($DryRun) {
    Write-Output "Dry run complete. No files removed."
} else {
    Write-Output "Cleanup complete. Removed $totalRemoved top-level entr$(if ($totalRemoved -eq 1) { 'y' } else { 'ies' })."
    Write-Output "Run 'git status --short' before pushing to confirm nothing inside target/ dist/ outputs/ is staged."
}
