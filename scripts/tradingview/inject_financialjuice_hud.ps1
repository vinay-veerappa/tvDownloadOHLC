<#
.SYNOPSIS
    1-Click FinancialJuice Live Squawk & News HUD Overlay for TradingView Desktop.

.DESCRIPTION
    Convenience shortcut to inject, toggle, or remove the FinancialJuice HUD.

.EXAMPLE
    .\inject_financialjuice_hud.ps1
    # Injects FinancialJuice HUD

.EXAMPLE
    .\inject_financialjuice_hud.ps1 -Action toggle
    # Toggles on/off

.EXAMPLE
    .\inject_financialjuice_hud.ps1 -Action remove
    # Removes HUD
#>

[CmdletBinding()]
param(
    [ValidateSet("inject", "remove", "toggle", "status")]
    [string]$Action = "inject",

    [ValidateSet("headlines", "ecocal", "tickstrike")]
    [string]$DefaultTab = "headlines",

    [switch]$HideVoice,
    [double]$Opacity = 0.96,
    [int]$Width = 440,
    [int]$Height = 620,
    [int]$Port = 9222
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ManagerPs = Join-Path $ScriptDir "tv_hud_manager.ps1"

& $ManagerPs -HUD "financialjuice" -Action $Action -Port $Port -Opacity $Opacity -DefaultTab $DefaultTab -HideVoice:$HideVoice
