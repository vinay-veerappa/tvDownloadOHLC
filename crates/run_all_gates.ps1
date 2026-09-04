<#
.SYNOPSIS
    Run every Rust check in one command: build, unit tests, and all three gates.

.DESCRIPTION
    This repo has no CI (no .github/workflows, no tools/ci_local.py), so the gates are
    only ever as good as someone remembering to run them. This is the single entry point.

    ORDER MATTERS. Build and unit tests come first because they need no live system; the
    gates come after and DO touch live state:
      * Gate 1 reads the running daemon on 8635 (read-only).
      * Gate 2 is offline - it replays a year of parquet bars.
      * Gate 3 runs the sentinel against an isolated mock port (SENTINEL_TEST_PORT
        17890); it never touches the real NT8 on 7890.

    ⚠️ A full `cargo build --release` cannot replace a RUNNING binary - Windows holds the
    file lock. If trading_daemon / fj_widget / pnl_widget_gdi are live, the build fails
    with "failed to remove file". Use -SkipBuild, or stop them first.

.PARAMETER SkipBuild
    Skip the release build (use when the live binaries hold their file locks).
.PARAMETER SkipGate1
    Skip the live-daemon contract check (use when the daemon is deliberately down).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File crates\run_all_gates.ps1
    powershell -ExecutionPolicy Bypass -File crates\run_all_gates.ps1 -SkipBuild
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipGate1
)

$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptDir)) { $ScriptDir = Split-Path -Parent $PSCommandPath }
$RepoRoot = Split-Path -Parent $ScriptDir

$env:PYO3_PYTHON = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $env:PYO3_PYTHON)) {
    Write-Error "venv python not found at $env:PYO3_PYTHON - PyO3 0.21 refuses system Python 3.14"
}

$results = [ordered]@{}
function Step([string]$name, [scriptblock]$body) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    try {
        & $body
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { throw "exit $LASTEXITCODE" }
        $results[$name] = "PASS"
        Write-Host "--- $name PASS" -ForegroundColor Green
    } catch {
        $results[$name] = "FAIL: $($_.Exception.Message)"
        Write-Host "--- $name FAIL: $($_.Exception.Message)" -ForegroundColor Red
    }
}

if (-not $SkipBuild) {
    Step "build (release)" { Push-Location $ScriptDir; try { cargo build --release } finally { Pop-Location } }
} else {
    Write-Host "=== build (release) SKIPPED ===" -ForegroundColor DarkGray
}

Step "cargo test (workspace)" { Push-Location $ScriptDir; try { cargo test } finally { Pop-Location } }

if (-not $SkipGate1) {
    Step "gate 1 - daemon contract" {
        & powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "gate1_contract.ps1")
    }
} else {
    Write-Host "=== gate 1 SKIPPED ===" -ForegroundColor DarkGray
}

Step "gate 2 - engine zero-divergence" {
    & (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $ScriptDir "gate2_parity.py")
}

Step "gate 3 - killswitch simulation" {
    & (Join-Path $ScriptDir "target\release\gate3_killswitch.exe")
}

Write-Host ""
Write-Host "================ SUMMARY ================" -ForegroundColor Cyan
$failed = 0
foreach ($k in $results.Keys) {
    if ($results[$k] -eq "PASS") {
        Write-Host ("  {0,-32} PASS" -f $k) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-32} {1}" -f $k, $results[$k]) -ForegroundColor Red
        $failed++
    }
}
Write-Host "========================================" -ForegroundColor Cyan
if ($failed -gt 0) { Write-Host "$failed step(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "All steps passed." -ForegroundColor Green
exit 0
