<#
.SYNOPSIS
    Launches the Independent Floating FinancialJuice Squawk & News Widget.

.DESCRIPTION
    Starts the local widget server and opens a frameless, native-looking floating desktop window
    (using Edge or Chrome App Mode). The window is independent of TradingView and stays active
    across all monitors. Self-contained — no NT8 bridge or CDP pump required.

.PARAMETER Port
    Local server port (default: 8636).

.PARAMETER Width
    Window width (default: 420).

.PARAMETER Height
    Window height (default: 640).

.PARAMETER Stop
    Stops any running FinancialJuice widget server processes.

.EXAMPLE
    .\launch_fj_widget.ps1
    # Launches floating FinancialJuice widget

.EXAMPLE
    .\launch_fj_widget.ps1 -Stop
    # Stops widget server
#>

[CmdletBinding()]
param(
    [int]$Port = 8636,
    [int]$Width = 520,
    [int]$Height = 680,
    [switch]$Stop
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ServerScript = Join-Path $ScriptDir "fj_widget_server.js"

if ($Stop) {
    Write-Host "[+] Stopping running fj_widget_server processes..." -ForegroundColor Cyan
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*fj_widget_server.js*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "  * Stopped server process $($_.ProcessId)" -ForegroundColor Green
    }
    exit 0
}

# Check if server is already running
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

# Locate Edge or Chrome for App Mode (frameless native window)
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