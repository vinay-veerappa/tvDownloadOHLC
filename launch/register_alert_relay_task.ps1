<#
.SYNOPSIS
    Register (or remove) the RiskGuard alert relay as a Scheduled Task that starts at logon.

.DESCRIPTION
    F-6's relay delivers NT8 RiskGuard alerts to Discord. The feature is INERT unless the
    relay is running, so "it works when I start it by hand" is not the same as delivered --
    that is the dead-safety-machinery shape the nt8-riskguard repo has a CI gate for.

    This registers `start_alert_relay.bat` to run at logon, which is the right trigger:
    NinjaTrader is a desktop application the operator logs in and starts, so a task tied to
    the logon session matches the lifetime of the thing being guarded. A service running
    with no desktop session would be watching an outbox nobody is writing to.

    .\ WHY NOT A WINDOWS SERVICE
    The relay reads a file under the user profile and writes to a webhook. It needs no
    elevation, no machine-wide lifetime, and nothing to guard while the operator is logged
    out and NT8 is closed. A service would add privilege and complexity for no coverage.

.PARAMETER Channel
    Key in discord_webhooks.json. Defaults to test_channel.

.PARAMETER Remove
    Unregister the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File launch\register_alert_relay_task.ps1
    powershell -ExecutionPolicy Bypass -File launch\register_alert_relay_task.ps1 -Channel alerts
    powershell -ExecutionPolicy Bypass -File launch\register_alert_relay_task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$Channel = "test_channel",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$TaskName = "RiskGuardAlertRelay"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $PSScriptRoot "start_alert_relay.bat"

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        Write-Host "Task '$TaskName' is not registered; nothing to remove."
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    Write-Host ""
    Write-Host "WARNING: the alert channel is now dead. The guard will keep DECIDING alerts" -ForegroundColor Yellow
    Write-Host "         and writing them to alerts_outbox.jsonl, and nothing will deliver" -ForegroundColor Yellow
    Write-Host "         them. You will not be told that you are not being told." -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $BatPath)) {
    Write-Error "launcher not found at $BatPath"
}

# Refuse to register a task that cannot possibly work. A scheduled task that starts, fails
# and disappears is worse than no task: Task Scheduler will report "last run: success"
# for a process that exited 2 immediately.
$webhooksFile = Join-Path $RepoRoot "discord_webhooks.json"
if (-not (Test-Path $webhooksFile)) {
    Write-Error "no discord_webhooks.json at $webhooksFile -- the relay would refuse to start."
}
$webhooks = Get-Content $webhooksFile -Raw | ConvertFrom-Json
if ($null -eq $webhooks.$Channel) {
    $known = ($webhooks.PSObject.Properties.Name) -join ", "
    Write-Error "channel '$Channel' is not in discord_webhooks.json. Known: $known"
}

$action = New-ScheduledTaskAction -Execute $BatPath -Argument $Channel -WorkingDirectory $RepoRoot

# TWO triggers, and the second one is not redundant -- it is the fix for a MEASURED
# seven-hour outage.
#
# On 2026-08-16 the task read State=Ready, LastTaskResult=255, and no relay process
# existed. The relay had died the previous afternoon at 16:28 and stayed dead. Cause:
# RestartCount 3 is the ONLY recovery, and it is a BUDGET, not a policy. Three attempts a
# minute apart, then Task Scheduler gives up -- permanently, until the next LOGON. On a box
# that stays logged in for days, "until the next logon" is "never", and the alert channel
# was silently dead through a whole session.
#
# The logon trigger is still right for the reason in the DESCRIPTION above. What was missing
# is anything that asks again LATER. A repeating trigger is safe here specifically because
# MultipleInstances defaults to IgnoreNew: if the relay is already running, each firing is
# discarded. So this costs nothing while healthy and re-arms the whole restart budget every
# 15 minutes while broken.
#
# ⚠️ 15 minutes is the WORST-CASE dead window, so read it as the number it is: up to a
# quarter hour of undelivered alerts after a crash. The outbox is a file and the relay
# resumes from its cursor, so nothing is LOST -- it is late, not gone. That is the trade for
# not hammering a webhook.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# ⚠️ -RepetitionDuration is OMITTED, not set to a large value. The obvious
# `([TimeSpan]::MaxValue)` serialises to P99999999DT23H59M59S and Task Scheduler REFUSES the
# whole registration: "a value which is incorrectly formatted or out of range". Omitting it
# is how "indefinitely" is expressed, and the read-back below is what proves which of the
# two actually got stored.
$retryTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

# RestartCount/RestartInterval are the INNER supervisor: the .bat already restarts the
# python process, so this only matters if the .bat itself dies (a closed window, a logoff).
# StartWhenAvailable catches a logon where the network was not up yet.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($logonTrigger, $retryTrigger) `
    -Settings $settings -Description "F-6: delivers NT8 RiskGuard alerts to Discord ($Channel)" `
    -Force | Out-Null

# READ THE TASK BACK. Register-ScheduledTask accepts a repetition that Task Scheduler then
# stores differently from what was asked for -- an indefinite duration is the usual casualty,
# and a trigger that silently expires after a day looks identical to one that never does
# until the day it matters. Assert rather than trust, and say what was actually stored.
$registered = Get-ScheduledTask -TaskName $TaskName
$repeating = @($registered.Triggers | Where-Object { $_.Repetition.Interval })
if ($repeating.Count -eq 0) {
    Write-Error ("the repeating trigger was NOT stored. Without it the task recovers only " +
                 "3 times and then waits for the next LOGON, which is the seven-hour outage " +
                 "this trigger exists to prevent.")
}
Write-Host "Registered '$TaskName' -> $BatPath $Channel"
foreach ($t in $registered.Triggers) {
    $rep = if ($t.Repetition.Interval) {
        "repeats every $($t.Repetition.Interval), duration '$($t.Repetition.Duration)'"
    } else { "no repetition" }
    Write-Host "  trigger: $($t.CimClass.CimClassName) -- $rep"
}
Write-Host ""
Write-Host "Start it now with:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Check it with:      Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host ""
Write-Host "VERIFY BY THE HEARTBEAT, NOT BY THE TASK STATE." -ForegroundColor Cyan
Write-Host "Task Scheduler reporting 'Ready' tells you it is registered, not that alerts are"
Write-Host "arriving. The relay posts a heartbeat to the '$Channel' channel; that message"
Write-Host "landing is the only evidence the path works end to end."
