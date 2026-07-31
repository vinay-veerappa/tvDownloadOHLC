#Requires -Version 5.1
<#
.SYNOPSIS
    Standalone rebuild of NinjaTrader.Custom.dll using the existing NT8 SDK-style csproj.
.DESCRIPTION
    Uses dotnet build on C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\NinjaTrader.Custom.csproj
    because the bundled .NET Framework csc.exe only supports C# 5, while many Custom files use C# 6+.
    LangVersion is pinned to 12.0 because the installed .NET 8 SDK compiler does not accept 13.0.
#>
param(
    [string]$CustomDir = 'C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom',
    [string]$Configuration = 'Debug',
    [string]$LangVersion = '12.0'
)

$ErrorActionPreference = 'Stop'
$csproj = Join-Path $CustomDir 'NinjaTrader.Custom.csproj'
$srcDll = Join-Path $CustomDir "bin\$Configuration\NinjaTrader.Custom.dll"
$dstDll = Join-Path $CustomDir 'NinjaTrader.Custom.dll'
$backupDll = Join-Path $CustomDir 'NinjaTrader.Custom.copy.dll'

if (-not (Test-Path $csproj)) { throw "Missing csproj: $csproj" }

$start = Get-Date
Write-Host "Building NinjaTrader.Custom.dll..." -ForegroundColor Cyan
Write-Host "  csproj: $csproj"
Write-Host "  config: $Configuration"
Write-Host "  lang:   $LangVersion"

$buildArgs = @(
    'build', $csproj
    '-c', $Configuration
    "-p:LangVersion=$LangVersion"
)
& dotnet @buildArgs
if ($LASTEXITCODE -ne 0) { throw "dotnet build failed with code $LASTEXITCODE" }

if (-not (Test-Path $srcDll)) { throw "Build output not found: $srcDll" }

if (Test-Path $dstDll) {
    Copy-Item $dstDll $backupDll -Force
    Write-Host "Backed up existing DLL to $backupDll"
}

Copy-Item $srcDll $dstDll -Force

$hash = (Get-FileHash $dstDll -Algorithm SHA256).Hash
$ts = (Get-Item $dstDll).LastWriteTime
Write-Host "`nDeployment complete:" -ForegroundColor Green
Write-Host "  DLL:    $dstDll"
Write-Host "  Time:   $ts"
Write-Host "  SHA256: $hash"
Write-Host "  Size:   $((Get-Item $dstDll).Length) bytes"
Write-Host "  Elapsed: $((Get-Date) - $start)"

Write-Host "`nNOTE: NinjaTrader (PID $((Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue | Select -ExpandProperty Id))) must be restarted to load the new assembly." -ForegroundColor Yellow
