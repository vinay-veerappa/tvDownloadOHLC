$ErrorActionPreference = 'SilentlyContinue'

Write-Host ""
$checks = @(
    @{ Name = 'NT8 bridge (RiskGuard+copier+MCP)'; Url = 'http://localhost:7890/api/health'; Auth = $true },
    @{ Name = 'NinjaTrader process             '; Url = '' },
    @{ Name = 'TradingView CDP (9222)         '; Url = 'http://127.0.0.1:9222/json/version' },
    @{ Name = 'Fleet P&L widget (8635)        '; Url = 'http://127.0.0.1:8635/health' },
    @{ Name = 'FinancialJuice widget (8636)   '; Url = 'http://127.0.0.1:8636/health' },
    @{ Name = 'API backend (8000)             '; Url = 'http://localhost:8000/health' },
    @{ Name = 'Web dashboard (3000)           '; Url = 'http://localhost:3000' },
    @{ Name = 'KB bridge RAG (8900)           '; Url = 'http://localhost:8900/health' }
)

foreach ($c in $checks) {
    if ([string]::IsNullOrEmpty($c.Url)) {
        $p = Get-Process -Name 'NinjaTrader'
        if ($p) { Write-Host "  [UP]   $($c.Name)" } else { Write-Host "  [--]   $($c.Name)  (not running)" }
        continue
    }
    try {
        $hdr = @{}
        if ($c.Auth) { $hdr = @{ Authorization = 'Bearer d0b837223cab4653' } }
        $r = Invoke-RestMethod -Uri $c.Url -Headers $hdr -TimeoutSec 2
        $extra = ''
        if ($null -ne $r.accountsCount) { $extra = "  accounts=$($r.accountsCount)" }
        elseif ($null -ne $r.accounts) { $extra = "  accounts=$($r.accounts.Count)" }
        Write-Host "  [UP]   $($c.Name)$extra"
    } catch {
        Write-Host "  [--]   $($c.Name)  (not running)"
    }
}