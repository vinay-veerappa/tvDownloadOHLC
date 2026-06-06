$tickers = "ES1", "NQ1", "RTY1", "YM1", "CL1", "GC1" 

foreach ($ticker in $tickers) {
    Write-Host "Running pipeline for $ticker..."
    & .\.venv\Scripts\python.exe -m scripts.edgeful.ib_pipeline --instruments $ticker --workers 1
}
