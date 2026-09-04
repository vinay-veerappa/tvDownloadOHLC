<#
.SYNOPSIS
    Launches the Independent Floating FinancialJuice Squawk & News Widget.

.DESCRIPTION
    Launches the pure native Rust desktop widget (fj_widget.exe) with embedded WebView2,
    hardware acceleration, and in-process reverse proxy.
    Falls back to legacy browser App Mode if the Rust binary has not yet been compiled.

.PARAMETER Port
    Local server port (default: 8636).

.PARAMETER Width
    Window width (default: 520).

.PARAMETER Height
    Window height (default: 680).

.PARAMETER Stop
    Stops any running FinancialJuice widget processes.

.EXAMPLE
    .\launch_fj_widget.ps1
    # Launches floating FinancialJuice widget

.EXAMPLE
    .\launch_fj_widget.ps1 -Stop
    # Stops widget
#>

[CmdletBinding()]
param(
    [int]$Port = 8636,
    [int]$Width = 520,
    [int]$Height = 680,
    [switch]$Stop
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$RustWidget = Join-Path $RootDir "crates\target\release\fj_widget.exe"

if ($Stop) {
    Write-Host "[+] Stopping running FinancialJuice widget processes..." -ForegroundColor Cyan
    Get-Process fj_widget -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-Process fj_daemon -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*fj_widget_server.js*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "  * Stopped legacy server process $($_.ProcessId)" -ForegroundColor Green
    }
    Write-Host "[OK] Stopped FinancialJuice processes." -ForegroundColor Green
    exit 0
}

# Preferred path: Standalone Native Rust Widget (WebView2 + Tao)
if (Test-Path $RustWidget) {
    Write-Host "[+] Launching FinancialJuice Native Rust Desktop Widget ($Width x $Height)..." -ForegroundColor Green
    Start-Process -FilePath $RustWidget -ArgumentList "--port $Port --width $Width --height $Height"
    Write-Host "[OK] FinancialJuice Native Widget launched successfully." -ForegroundColor Green
    exit 0
}

# Fallback path: Legacy Node.js + Edge/Chrome App Mode
Write-Host "[!] Note: fj_widget.exe not found at $RustWidget. Falling back to browser app mode..." -ForegroundColor Yellow
$ServerScript = Join-Path $ScriptDir "fj_widget_server.js"

$serverRunning = $false
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1
    if ($health.status -eq "ok") { $serverRunning = $true }
} catch {}

if (-not $serverRunning) {
    Write-Host "[+] Starting background widget server on port $Port..." -ForegroundColor Cyan
    $env:FJ_WIDGET_PORT = $Port.ToString()
    $nodeExe = (Get-Command node).Source
    $wsh = New-Object -ComObject WScript.Shell
    $wsh.Run("`"$nodeExe`" `"$ServerScript`"", 0, $false)
    Start-Sleep -Milliseconds 600
}

$edgePaths = @(
    "$env:ProgramFiles (x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
)

$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$browserExe = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browserExe) {
    $browserExe = $chromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
}

$widgetUrl = "http://127.0.0.1:$Port/fj-widget"

if ($browserExe) {
    Write-Host "[+] Launching FinancialJuice Floating Widget ($Width x $Height)..." -ForegroundColor Green
    $argsList = @(
        "--app=$widgetUrl",
        "--window-size=$Width,$Height",
        "--window-name=FinancialJuice_Widget"
    )
    Start-Process -FilePath $browserExe -ArgumentList $argsList
} else {
    Write-Host "[+] Opening in default browser: $widgetUrl" -ForegroundColor Green
    Start-Process $widgetUrl
}

Write-Host "[OK] FinancialJuice Widget launched successfully." -ForegroundColor Green