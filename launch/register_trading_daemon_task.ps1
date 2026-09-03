<#
.SYNOPSIS
    Register (or remove) the trading_daemon (Fleet P&L engine) as a Scheduled Task that
    starts at logon.

.DESCRIPTION
    Track 1 of the Rust migration cut the Fleet P&L HUD over from Node
    (pnl_widget_server.js) to crates/trading_daemon. The HUD is inert unless the daemon
    is running, so "it works when I start it by hand" is not the same as running -- this
    registers start_trading_daemon.bat at logon, which matches the lifetime of the thing
    it serves (NinjaTrader is a desktop app in the operator's session).

    WHY NOT A WINDOWS SERVICE
    The daemon needs no elevation, binds a user-session port, and nothing to guard while
    the operator is logged out and NT8 is closed. A service would add privilege and
    complexity for no coverage. Same reasoning as RiskGuardAlertRelay.

    The .bat carries its own restart loop and log (logs\trading_daemon.log). This task's
    repeating trigger re-arms Task Scheduler's restart budget every 15 minutes, which is
    the fix for the measured seven-hour silent outage pattern documented in
    register_alert_relay_task.ps1.

.PARAMETER Remove
    Unregister the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File launch\register_trading_daemon_task.ps1
    powershell -ExecutionPolicy Bypass -File launch\register_trading_daemon_task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$TaskName = "TradingDaemon"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $PSScriptRoot "start_trading_daemon.bat"

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        Write-Host "Task '$TaskName' is not registered; nothing to remove."
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    Write-Host ""
    Write-Host "WARNING: the Fleet P&L HUD is now dead until the daemon is started by hand." -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $BatPath)) {
    Write-Error "launcher not found at $BatPath"
}

# Refuse to register a task that cannot possibly work. A scheduled task that starts,
# fails and disappears is worse than no task: Task Scheduler reports "last run: success"
# for a process that exited 2 immediately.
$DaemonExe = Join-Path $RepoRoot "crates\target\release\trading_daemon.exe"
if (-not (Test-Path $DaemonExe)) {
    Write-Error "trading_daemon.exe not found at $DaemonExe -- build first: cd crates && cargo build --release -p trading_daemon"
}

$action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $RepoRoot

# TWO triggers, and the second one is not redundant (see register_alert_relay_task.ps1:
# RestartCount 3 is a BUDGET, not a policy -- on a box that stays logged in for days,
# 'until the next logon' is 'never'). The 15-minute repeating trigger re-arms the budget;
# MultipleInstances=IgnoreNew makes each firing a no-op while healthy.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# -RepetitionDuration is OMITTED, not set to a large value. The obvious
# ([TimeSpan]::MaxValue) serialises to P99999999DT23H59M59S and Task Scheduler REFUSES
# the whole registration. Omitting it is how "indefinitely" is expressed.
$retryTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($logonTrigger, $retryTrigger) `
    -Settings $settings -Description "Fleet P&L daemon (Rust) on port 8635: HUD + NT8 poller + TV CDP pump" `
    -Force | Out-Null

# READ THE TASK BACK. Assert the repeating trigger actually got stored.
$registered = Get-ScheduledTask -TaskName $TaskName
$repeating = @($registered.Triggers | Where-Object { $_.Repetition.Interval })
if ($repeating.Count -eq 0) {
    Write-Error ("the repeating trigger was NOT stored. Without it the task recovers only " +
                 "3 times and then waits for the next LOGON.")
}
Write-Host "Registered '$TaskName' -> $BatPath"
Write-Host "  triggers: at logon ($env:USERNAME) + every 15 minutes (restart budget re-arm)"
Write-Host "  binary:   $DaemonExe"
Write-Host "  port:     8635  log: logs\trading_daemon.log"
Write-Host ""
Write-Host "Start it now: Start-ScheduledTask -TaskName 'TradingDaemon'"