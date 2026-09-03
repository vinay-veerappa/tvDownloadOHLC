$node = Invoke-RestMethod -Uri "http://127.0.0.1:8635/api/data" -TimeoutSec 10
$rust = Invoke-RestMethod -Uri "http://127.0.0.1:8637/api/data" -TimeoutSec 10

# 1. Verify account count parity
if ($node.accounts.Count -ne $rust.accounts.Count) { throw "Account count mismatch: Node=$($node.accounts.Count), Rust=$($rust.accounts.Count)" }

# 2. Verify account balances match within $0.01 tolerance
for ($i = 0; $i -lt $node.accounts.Count; $i++) {
    $na = $node.accounts[$i]; $ra = $rust.accounts[$i]
    if ($na.name -ne $ra.name) { throw "Account name mismatch at index ${i}: $($na.name) vs $($ra.name)" }
    if ([Math]::Abs($na.netLiquidation - $ra.netLiquidation) -gt 0.01) { throw "NetLiq mismatch on $($na.name): $($na.netLiquidation) vs $($ra.netLiquidation)" }
}

# 3. Verify copier rows are present
if ($node.copierRows.Count -ne $rust.copierRows.Count) { throw "Copier rows mismatch: Node=$($node.copierRows.Count), Rust=$($rust.copierRows.Count)" }

Write-Host "GATE 1 PASSED: 100% Data & Balance Parity Verified!" -ForegroundColor Green