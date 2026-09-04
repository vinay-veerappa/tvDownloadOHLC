<#
.SYNOPSIS
    Gate 1 (post-cutover): assert the live trading_daemon still honours the /api/data
    contract, and - when a shadow instance is supplied - assert real A/B parity.

.DESCRIPTION
    WHY THIS REPLACED gate1_parity.ps1
    The original gate fetched 8635 (labelled $node) and 8637 (labelled $rust) and
    compared them. That was correct for exactly one day. After the cutover 8635 IS the
    Rust daemon, so the script compared the daemon to ITSELF and passed unconditionally;
    and pnl_widget_server.js is archived, so the Node side can never be stood back up.
    It had become a green that cannot go red.

    TWO MODES
      * Contract mode (default): validate the live daemon on -LivePort against
        golden/api_data_contract.json. Catches the degradations an A/B test never
        could once there is only one implementation left - dropped keys, a poller that
        stopped updating, a truncated fleet, a copier block that stopped loading.
      * Parity mode (-ShadowPort N): genuine A/B against a second instance, e.g. a
        release candidate on 8637. Refuses to run if both ports resolve to the SAME
        process, which is the precise failure the old script shipped with.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File crates\gate1_contract.ps1
    powershell -ExecutionPolicy Bypass -File crates\gate1_contract.ps1 -ShadowPort 8637
#>
[CmdletBinding()]
param(
    [int]$LivePort = 8635,
    [int]$ShadowPort = 0,
    [string]$ContractPath = ""
)

$ErrorActionPreference = "Stop"

# $PSScriptRoot is empty when a param default is evaluated under some invocation paths,
# so resolve the script directory in the body instead of in the param block.
if ([string]::IsNullOrEmpty($ContractPath)) {
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $ContractPath = Join-Path $scriptDir "golden\api_data_contract.json"
}
$failures = New-Object System.Collections.Generic.List[string]
function Fail([string]$m) { $failures.Add($m) | Out-Null }

function Get-PortOwner([int]$Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
         Select-Object -First 1
    if ($null -eq $c) { return $null }
    return $c.OwningProcess
}

if (-not (Test-Path $ContractPath)) { throw "contract not found at $ContractPath" }
$contract = Get-Content $ContractPath -Raw | ConvertFrom-Json

Write-Host "GATE 1 - trading_daemon contract check (live port $LivePort)" -ForegroundColor Cyan

# --- Route surface -------------------------------------------------------------------
# A daemon that answers /api/data but 404s /api/guard/config is half-migrated, and the
# HUD would show that as "no lockouts" rather than as an error.
foreach ($route in $contract.requiredRoutes) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$LivePort$route" -TimeoutSec 10 | Out-Null
    } catch {
        Fail "route $route did not respond on $LivePort : $($_.Exception.Message)"
    }
}

# --- Payload contract ----------------------------------------------------------------
$live = $null
try {
    $live = Invoke-RestMethod -Uri "http://127.0.0.1:$LivePort/api/data" -TimeoutSec 10
} catch {
    Fail "GET /api/data failed on $LivePort : $($_.Exception.Message)"
}

if ($null -ne $live) {
    $topKeys = $live.PSObject.Properties.Name
    foreach ($k in $contract.requiredTopLevelKeys) {
        if ($topKeys -notcontains $k) { Fail "missing top-level key '$k'" }
    }
    foreach ($k in $contract.numericTopLevelKeys) {
        if ($topKeys -contains $k) {
            $v = $live.$k
            if ($null -eq $v -or -not ($v -is [double] -or $v -is [int] -or $v -is [long] -or $v -is [decimal])) {
                Fail "top-level key '$k' is not numeric (got '$v')"
            }
        }
    }

    $acctCount = @($live.accounts).Count
    if ($acctCount -lt $contract.minAccounts) {
        Fail ("accounts=$acctCount is below the floor $($contract.minAccounts) " +
              "(was $($contract.accountsCountAtCapture) at capture) - NT8 disconnected, " +
              "or the poller is serving a truncated fleet")
    }
    if ($acctCount -gt 0) {
        $a0 = $live.accounts[0]
        $aKeys = $a0.PSObject.Properties.Name
        foreach ($k in $contract.requiredAccountKeys) {
            if ($aKeys -notcontains $k) { Fail "account object missing key '$k'" }
        }
    }

    # copierRows must be an ARRAY, present even when empty. Its absence is what the
    # third poll leg (/api/copier/snapshot) going missing looks like from out here.
    if ($topKeys -contains "copierRows") {
        if ($null -eq $live.copierRows) { Fail "copierRows is null (expected an array)" }
    }
    if ($null -ne $live.copierSystem) {
        $csKeys = $live.copierSystem.PSObject.Properties.Name
        foreach ($k in $contract.requiredCopierSystemKeys) {
            if ($csKeys -notcontains $k) { Fail "copierSystem missing key '$k'" }
        }
    } else {
        Fail "copierSystem is null - the copier snapshot poll leg is not landing"
    }

    # Freshness. This is the one that catches a daemon that is UP and serving a frozen
    # cache - the failure mode with no visible symptom, because stale JSON looks fine.
    if ($topKeys -contains "timestamp") {
        $nowMs = [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
        $ageMs = $nowMs - [long]$live.timestamp
        if ($ageMs -gt [long]$contract.maxTimestampAgeMs) {
            Fail "payload is stale: ${ageMs}ms old (limit $($contract.maxTimestampAgeMs)ms) - poller stopped"
        } else {
            Write-Host "  freshness OK (${ageMs}ms)" -ForegroundColor DarkGray
        }
    }
    Write-Host "  accounts=$acctCount copierRows=$(@($live.copierRows).Count)" -ForegroundColor DarkGray
}

# --- Optional A/B parity -------------------------------------------------------------
if ($ShadowPort -gt 0) {
    Write-Host "Parity mode: comparing $LivePort against shadow $ShadowPort" -ForegroundColor Cyan

    $livePid   = Get-PortOwner $LivePort
    $shadowPid = Get-PortOwner $ShadowPort
    if ($null -eq $shadowPid) {
        Fail "no listener on shadow port $ShadowPort - start the candidate first"
    } elseif ($livePid -eq $shadowPid) {
        # The exact defect the retired script shipped with.
        Fail ("VACUOUS COMPARISON REFUSED: ports $LivePort and $ShadowPort are both served " +
              "by pid $livePid. Comparing a process to itself always passes and proves nothing.")
    } else {
        $shadow = Invoke-RestMethod -Uri "http://127.0.0.1:$ShadowPort/api/data" -TimeoutSec 10
        $lc = @($live.accounts).Count; $sc = @($shadow.accounts).Count
        if ($lc -ne $sc) { Fail "account count mismatch: live=$lc shadow=$sc" }
        else {
            for ($i = 0; $i -lt $lc; $i++) {
                $la = $live.accounts[$i]; $sa = $shadow.accounts[$i]
                if ($la.name -ne $sa.name) { Fail "account name mismatch at ${i}: $($la.name) vs $($sa.name)" }
                # Tolerance is not zero: the two payloads are fetched sequentially against
                # a moving market, so a live position drifts between the two reads. This
                # is the transient the original run hit; it is not a defect.
                if ([Math]::Abs($la.netLiquidation - $sa.netLiquidation) -gt 1.00) {
                    Fail "NetLiq mismatch on $($la.name): $($la.netLiquidation) vs $($sa.netLiquidation)"
                }
            }
        }
        if (@($live.copierRows).Count -ne @($shadow.copierRows).Count) {
            Fail "copier rows mismatch: live=$(@($live.copierRows).Count) shadow=$(@($shadow.copierRows).Count)"
        }
    }
}

# --- Verdict -------------------------------------------------------------------------
Write-Host ""
if ($failures.Count -gt 0) {
    foreach ($f in $failures) { Write-Host "  [FAIL] $f" -ForegroundColor Red }
    Write-Host "GATE 1 FAILED ($($failures.Count) problem(s))" -ForegroundColor Red
    exit 1
}
$mode = if ($ShadowPort -gt 0) { "contract + A/B parity" } else { "contract" }
Write-Host "GATE 1 PASSED ($mode)" -ForegroundColor Green
exit 0
