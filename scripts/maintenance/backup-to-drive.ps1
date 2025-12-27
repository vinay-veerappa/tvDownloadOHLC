
param(
    [string]$DestinationPath = "G:\My Drive\Backups\tvDownloadOHLC"
)

if (-not (Test-Path $DestinationPath)) {
    Write-Host "Creating destination: $DestinationPath"
    New-Item -ItemType Directory -Force -Path $DestinationPath
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmm"
$backupDir = "$DestinationPath\$timestamp"

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
Write-Host "Backing up to: $backupDir"

# 1. Backup Database
$dbSource = "web\prisma\dev.db"
if (Test-Path $dbSource) {
    Write-Host "Copying Database..."
    Copy-Item $dbSource -Destination "$backupDir\dev.db"
} else {
    Write-Warning "Database not found at $dbSource"
}

# 2. Backup Data Folder (Parquet, CSVs)
# Exclude huge raw dumps if needed, but user asked for "all".
$dataSource = "data"
if (Test-Path $dataSource) {
    Write-Host "Copying Data Directory (this may take a while)..."
    Copy-Item $dataSource -Destination "$backupDir\data" -Recurse
}

Write-Host "Backup Complete!"
Write-Host "Checked $backupDir"
