# Local CBM-MCP Installer
$ErrorActionPreference = "Stop"
$Repo = "DeusData/codebase-memory-mcp"
$BinaryName = "codebase-memory-mcp"
$InstallDir = "mcp/bin"

Write-Host "Fetching latest release..."
$releaseUrl = "https://api.github.com/repos/$Repo/releases/latest"
$release = Invoke-RestMethod -Uri $releaseUrl -Headers @{ "User-Agent" = "codebase-memory-mcp-setup" }
$tag = $release.tag_name
Write-Host "Latest release: $tag"

$asset = "codebase-memory-mcp-windows-amd64.zip"
$downloadUrl = "https://github.com/$Repo/releases/download/$tag/$asset"

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$tmpZip = "mcp/bin.zip"
Write-Host "Downloading $asset..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $tmpZip -UseBasicParsing

Write-Host "Extracting..."
Expand-Archive -Path $tmpZip -DestinationPath $InstallDir -Force
Remove-Item $tmpZip -Force

Write-Host "Installation Complete."
Get-ChildItem $InstallDir | Select-Object Name, Length
