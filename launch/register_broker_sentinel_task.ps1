<#
.SYNOPSIS
    Register (or remove) the broker_sentinel NT8 deadlock watchdog as a Scheduled Task
    that starts at logon.

.DESCRIPTION
    Track 3 shipped broker_sentinel, passed its simulated gate, and then got no launcher
    and no task - so the playbook's "the sentinel runs observe/dry-run only" described
    something that was not running at all. Every other Track 1 component got a .bat plus
    a registered task; this closes that gap.

    WHAT THIS DOES AND DOES NOT BUY YOU
    With arm_live_flatten=false and no Tradovate/Rithmic credentials, the sentinel
    detects an NT8 deadlock with open positions and LOGS the broker call it would have
    made. It does not place an order. That is worth running - it produces the timestamped
    evidence that the detection half works, which is the half you cannot test later
    during an actual incident - but it is observation, not protection. Do not treat a
    registered task as a killswitch.

    WHY NOT A WINDOWS SERVICE
    Same reasoning as TradingDaemon and RiskGuardAlertRelay: no elevation needed, and
    there is nothing to watch while the operator is logged out and NT8 is closed.

.PARAMETER Remove
    Unregister the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File launch\register_broker_sentinel_task.ps1
    powershell -ExecutionPolicy Bypass -File launch\register_broker_sentinel_task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$TaskName = "BrokerSentinel"
$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptDir)) { $ScriptDir = Split-Path -Parent $PSCommandPath }
$RepoRoot = Split-Path -Parent $ScriptDir
$BatPath = Join-Path $ScriptDir "start_broker_sentinel.bat"

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        Write-Host "Task '$TaskName' is not registered; nothing to remove."
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    Write-Host ""
    Write-Host "WARNING: nothing is now watching NT8 for a deadlock with open positions." -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $BatPath)) {
    Write-Error "launcher not found at $BatPath"
}

# Refuse to register a task that cannot possibly work. Task Scheduler reports
# "last run: success" for a process that exited 2 immediately, so an unbuildable task
# is indistinguishable from a healthy one from the Task Scheduler UI.
$SentinelExe = Join-Path $RepoRoot "crates\target\release\broker_sentinel.exe"
if (-not (Test-Path $SentinelExe)) {
    Write-Error "broker_sentinel.exe not found at $SentinelExe -- build first: cd crates && cargo build --release -p broker_sentinel"
}

$action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $RepoRoot

# TWO triggers. The repeating one is not redundant: RestartCount is a BUDGET, not a
# policy, and on a box that stays logged in for days "until the next logon" is "never" -
# the measured seven-hour silent-outage pattern. The 15-minute repetition re-arms it;
# the .bat's own process guard makes each firing a quiet no-op while healthy.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# -RepetitionDuration is OMITTED, not set large. [TimeSpan]::MaxValue serialises to
# P99999999DT23H59M59S and Task Scheduler refuses the whole registration.
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
    -Settings $settings -Description "NT8 deadlock watchdog (Rust, observe-only): 500ms /api/positions poll, >3s dead-port trip" `
    -Force | Out-Null

# READ THE TASK BACK. Assert the repeating trigger actually got stored - registration
# succeeding is not the same as the trigger being persisted.
$registered = Get-ScheduledTask -TaskName $TaskName
$repeating = @($registered.Triggers | Where-Object { $_.Repetition.Interval })
if ($repeating.Count -eq 0) {
    Write-Error ("the repeating trigger was NOT stored. Without it the task recovers only " +
                 "3 times and then waits for the next LOGON.")
}
Write-Host "Registered '$TaskName' -> $BatPath"
Write-Host "  triggers: at logon ($env:USERNAME) + every 15 minutes (restart budget re-arm)"
Write-Host "  binary:   $SentinelExe"
Write-Host "  log:      logs\broker_sentinel.log"
Write-Host ""
Write-Host "MODE: OBSERVE-ONLY. It logs the broker flatten it would have made; it places" -ForegroundColor Yellow
Write-Host "      no order. This is not an active killswitch." -ForegroundColor Yellow
Write-Host ""
Write-Host "Start it now: Start-ScheduledTask -TaskName 'BrokerSentinel'"
