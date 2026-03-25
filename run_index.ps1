$repoPath = "c:/Users/vinay/tvDownloadOHLC"
$json = '{"repo_path": "' + $repoPath + '"}'
Write-Host "Running: codebase-memory-mcp cli index_repository $json"
codebase-memory-mcp cli index_repository $json
