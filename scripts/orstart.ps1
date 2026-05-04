[CmdletBinding()]
param(
    [switch]$Brief,
    [switch]$NoLive
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location -LiteralPath $RepoRoot

function Write-Section {
    param([string]$Title)

    Write-Output ""
    Write-Output ("=" * 88)
    Write-Output $Title
    Write-Output ("=" * 88)
}

function Write-Subsection {
    param([string]$Title)

    Write-Output ""
    Write-Output ("-" * 88)
    Write-Output $Title
    Write-Output ("-" * 88)
}

function Show-File {
    param([string]$RelativePath)

    Write-Section "FILE: $RelativePath"
    $path = Join-Path $RepoRoot $RelativePath

    if (-not (Test-Path -LiteralPath $path)) {
        Write-Output "MISSING: $RelativePath"
        return
    }

    $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($content)) {
        Write-Output "(empty file)"
        return
    }

    Write-Output $content.TrimEnd()
}

function Show-Command {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Subsection $Title
    try {
        $result = & $Command
        if ($null -eq $result) {
            Write-Output "(no output)"
        } else {
            $result | Out-String -Width 240 | Write-Output
        }
    } catch {
        Write-Output "Unavailable: $($_.Exception.Message)"
    }
}

function Show-WorkflowState {
    Write-Section "WORKFLOW STATE"

    $taskboard = Join-Path $RepoRoot ".gov/workflow/TASKBOARD.md"
    if (Test-Path -LiteralPath $taskboard) {
        Show-File ".gov/workflow/TASKBOARD.md"
    } else {
        Write-Output "MISSING: .gov/workflow/TASKBOARD.md"
    }

    Show-Command "Active workpackets in .gov/workflow/workpackets/" {
        $wpDir = Join-Path $RepoRoot ".gov/workflow/workpackets"
        if (-not (Test-Path -LiteralPath $wpDir)) {
            "Missing folder: $wpDir"
            return
        }
        $files = Get-ChildItem -LiteralPath $wpDir -File -Filter "WP-*.md" -ErrorAction SilentlyContinue |
            Sort-Object Name
        if (-not $files -or $files.Count -eq 0) {
            "(no active workpackets)"
            return
        }
        $files | Select-Object Name, Length, LastWriteTime
    }

    Show-Command "Archived workpackets in .gov/workflow/archive/" {
        $arDir = Join-Path $RepoRoot ".gov/workflow/archive"
        if (-not (Test-Path -LiteralPath $arDir)) {
            "Missing folder: $arDir"
            return
        }
        $files = Get-ChildItem -LiteralPath $arDir -File -Filter "WP-*.md" -ErrorAction SilentlyContinue |
            Sort-Object Name
        if (-not $files -or $files.Count -eq 0) {
            "(no archived workpackets)"
            return
        }
        $files | Select-Object Name, LastWriteTime
    }
}

function Show-SpecState {
    Write-Section "SPEC STATE"

    $specReadme = Join-Path $RepoRoot ".gov/spec/README.md"
    if (Test-Path -LiteralPath $specReadme) {
        Show-File ".gov/spec/README.md"
    } else {
        Write-Output "MISSING: .gov/spec/README.md"
    }

    Show-Command "Spec files in .gov/spec/" {
        $specDir = Join-Path $RepoRoot ".gov/spec"
        Get-ChildItem -LiteralPath $specDir -File -Filter "*.md" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne "README.md" } |
            Sort-Object Name |
            Select-Object Name, Length, LastWriteTime
    }
}

function Show-BuildState {
    Write-Section "BUILD AND OUTPUT FOLDER STATE"

    foreach ($folder in "target", "dist", "outputs") {
        Show-Command "$folder/ contents" {
            $path = Join-Path $RepoRoot $folder
            if (-not (Test-Path -LiteralPath $path)) {
                "Missing folder: $folder"
                return
            }
            $entries = Get-ChildItem -LiteralPath $path -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -ne ".gitkeep" -and $_.Name -ne "README.md" }
            if (-not $entries -or $entries.Count -eq 0) {
                "(empty - clean)"
                return
            }
            $entries | Sort-Object Name | Select-Object Name, Length, LastWriteTime
        }
    }
}

function Show-ProductLayout {
    Write-Section "PRODUCT LAYOUT (.product/)"

    Show-Command "Source modules under .product/src/" {
        $srcDir = Join-Path $RepoRoot ".product/src"
        if (-not (Test-Path -LiteralPath $srcDir)) {
            "Missing folder: .product/src"
            return
        }
        Get-ChildItem -LiteralPath $srcDir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in ".py", ".rs", ".ts", ".js", ".pyi" } |
            Sort-Object FullName |
            Select-Object @{N="Path";E={$_.FullName.Replace($RepoRoot.Path + [IO.Path]::DirectorySeparatorChar, "")}}, Length, LastWriteTime
    }

    Show-Command "Tests under .product/tests/" {
        $tDir = Join-Path $RepoRoot ".product/tests"
        if (-not (Test-Path -LiteralPath $tDir)) {
            "Missing folder: .product/tests"
            return
        }
        Get-ChildItem -LiteralPath $tDir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in ".py", ".rs", ".ts" } |
            Sort-Object FullName |
            Select-Object @{N="Path";E={$_.FullName.Replace($RepoRoot.Path + [IO.Path]::DirectorySeparatorChar, "")}}, Length, LastWriteTime
    }
}

Write-Section "ORSTART BOOTSTRAP"
Write-Output "Purpose: give any fresh assistant or human collaborator the OpenRepose rules, codex, agent instructions, topology, spec status, workflow taskboard, and build/output state."
Write-Output "Repo: $RepoRoot"
Write-Output "Remote of record: https://github.com/Nuntissura/OpenRepose"
Write-Output "Run from anywhere inside the repo with: .\orstart"
Write-Output "Options: -Brief, -NoLive"
Write-Output ""
Write-Output "Assistant instruction: treat this output as startup context. Do not rely on memory for repo rules, spec state, or workflow status."
Write-Output "Assistant instruction: read .gov/CODEX.md after startup; treat it as a binding project contract alongside .gov/AGENTS.md."
Write-Output "Assistant instruction: follow the codex rules and instructions before advising, editing, or changing workflow state."

Write-Subsection "Git identity and worktree state"
$prevPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    Write-Output "pwd: $(Get-Location)"
    $gitRoot = & git rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
        Write-Output "git: not initialized in this directory yet."
        Write-Output "First-time setup:"
        Write-Output "  git init"
        Write-Output "  git remote add origin https://github.com/Nuntissura/OpenRepose.git"
        Write-Output "  git add ."
        Write-Output "  git commit -m `"Initial scaffold`""
        Write-Output "  git push -u origin main"
    } else {
        Write-Output "git root:    $gitRoot"
        $branch = & git rev-parse --abbrev-ref HEAD 2>$null
        Write-Output "branch:      $branch"
        $remote = & git config --get remote.origin.url 2>$null
        if ([string]::IsNullOrWhiteSpace($remote)) {
            Write-Output "remote:      (no origin configured)"
        } else {
            Write-Output "remote:      $remote"
        }
        Write-Output "status:"
        & git status --short
    }
} finally {
    $global:LASTEXITCODE = 0
    $ErrorActionPreference = $prevPref
}

$coreFiles = @(
    "README.md",
    ".gov/AGENTS.md",
    ".gov/CODEX.md",
    ".gov/topology.yaml",
    ".gov/README.md",
    ".gov/workflow/README.md"
)

foreach ($file in $coreFiles) {
    Show-File $file
}

if (-not $Brief) {
    Show-File ".gov/templates/WP_TEMPLATE.md"
}

Show-SpecState
Show-WorkflowState
Show-BuildState

if (-not $Brief) {
    Show-ProductLayout
}

Write-Section "ORSTART COMPLETE"
Write-Output "Next step for the assistant: read the relevant spec section, check the active taskboard, open or update the workpacket that owns the requested change, then make the change. Update governance state in the same work session."
