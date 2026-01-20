$tickers = @("NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1")
foreach ($t in $tickers) {
    Write-Host "`nGenerated Reports for $t"
    Write-Host "--------------------------------"
    python scripts/analysis/analyze_overnight_probabilities.py $t
    python scripts/analysis/analyze_sequence_probabilities.py $t
}
