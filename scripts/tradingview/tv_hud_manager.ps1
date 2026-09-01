<#
.SYNOPSIS
    TradingView Desktop Modular HUD Manager (PowerShell CLI).

.DESCRIPTION
    Manages modular Heads-Up Display (HUD) overlays inside TradingView Desktop.
    Allows listing, injecting, toggling, and removing HUDs (e.g. FinancialJuice, NT8 Positions, Custom HUDs).

.PARAMETER Action
    The action to execute:
    - 'list': Show available HUD catalog and active overlays in TradingView.
    - 'inject': Inject or update a specific HUD.
    - 'remove': Remove a specific HUD from TradingView.
    - 'toggle': Toggle a specific HUD on/off.
    - 'clear' or 'remove-all': Remove ALL HUD overlays from TradingView.

.PARAMETER HUD
    The identifier of the HUD module (e.g. 'financialjuice', 'nt8_positions'). Default: 'financialjuice'.

.PARAMETER Width
    Custom width in pixels.

.PARAMETER Height
    Custom height in pixels.

.PARAMETER Opacity
    Custom opacity between 0.50 and 1.0 (default: 0.96).

.PARAMETER DefaultTab
    For FinancialJuice: 'headlines', 'ecocal', or 'tickstrike'.

.PARAMETER HideVoice
    For FinancialJuice: if set, hides the voice squawk bar by default.

.PARAMETER Port
    CDP port (default: 9222).

.EXAMPLE
    .\tv_hud_manager.ps1 -Action list
    # Lists available and active HUDs

.EXAMPLE
    .\tv_hud_manager.ps1 -HUD financialjuice
    # Injects FinancialJuice HUD

.EXAMPLE
    .\tv_hud_manager.ps1 -HUD financialjuice -Action toggle
    # Toggles FinancialJuice HUD on/off

.EXAMPLE
    .\tv_hud_manager.ps1 -Action clear
    # Removes all HUD overlays from TradingView
#>

[CmdletBinding()]
param(
    [ValidateSet("list", "inject", "remove", "toggle", "clear", "remove-all")]
    [string]$Action = "inject",

    [string]$HUD = "financialjuice",
    [int]$Width = 0,
    [int]$Height = 0,
    [double]$Opacity = 0.96,
    [string]$DefaultTab = "headlines",
    [switch]$HideVoice,
    [int]$Port = 9222,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$NodeEngine = Join-Path $ScriptDir "tv_hud_manager.js"

if (-not (Test-Path $NodeEngine)) {
    Write-Error "tv_hud_manager.js engine not found at $NodeEngine"
    exit 1
}

$env:TV_CDP_PORT = $Port.ToString()
$env:TV_CDP_HOST = $HostName

$cmdArgs = @($NodeEngine)

switch ($Action.ToLower()) {
    "list" {
        $cmdArgs += "list"
    }
    "clear" {
        $cmdArgs += "clear"
    }
    "remove-all" {
        $cmdArgs += "clear"
    }
    "inject" {
        $cmdArgs += @("inject", $HUD)
    }
    "remove" {
        $cmdArgs += @("remove", $HUD)
    }
    "toggle" {
        $cmdArgs += @("toggle", $HUD)
    }
}

& node $cmdArgs
