'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  RefreshCcw,
  Download,
  Filter,
  Search,
  CheckCircle2,
  AlertTriangle,
  Zap,
  TrendingUp,
  ShieldAlert,
  BarChart3,
  Layers,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type MarketRegime = {
  status: string;
  spy_close: number;
  is_macro_high_risk: boolean;
  evaluated_at: string;
};

type Candidate = {
  ticker: string;
  company: string;
  sector: string;
  industry: string;
  close: number;
  matched_strategies_count: number;
  matched_strategies_list: string;
  strategy_matches: Record<string, boolean>;
};

type ScreenerApiResponse = {
  success: boolean;
  market_regime: MarketRegime;
  strategies: string[];
  candidates: Candidate[];
  updated_at: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Constants & Color Mappings
// ─────────────────────────────────────────────────────────────────────────────

const STRATEGY_LABELS: Record<string, { label: string; desc: string; color: string }> = {
  all: { label: 'All Strategies (Common Subset)', desc: 'Highlight candidates matching multiple institutional setups', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  kell_ema_bounce: { label: 'Oliver Kell EMA Bounce', desc: 'Bounces off 10/20 EMA in strong uptrend', color: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30' },
  minervini_trend: { label: 'Minervini Trend Template', desc: '8-point trend template for market leaders', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  oneil_breakout: { label: 'O\'Neil CAN SLIM Breakout', desc: 'Base breakout near 52W high on volume', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30' },
  parabolic_short: { label: 'Parabolic Short (Qullamaggie)', desc: 'Extended runners far from 10/20 EMA', color: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  qullamaggie_hft: { label: 'High Tight Flag (HFT)', desc: '100%+ run-up with ATR & volume contraction', color: 'bg-violet-500/15 text-violet-300 border-violet-500/30' },
  rs_vs_spy: { label: 'Relative Strength vs SPY', desc: 'Outperforming SPY benchmark in top industry', color: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30' },
  stockbee_ep: { label: 'Stockbee Episodic Pivot (EP)', desc: '8%+ gap up on massive volume catalyst', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  stockbee_momentum: { label: 'Stockbee Momentum Burst', desc: '4%+ gainers in top sector industries', color: 'bg-orange-500/15 text-orange-300 border-orange-500/30' },
  stockbee_sss20: { label: 'Stockbee SSS 20% Study (maxv5)', desc: 'Stocks making a 20%+ move in 5 trading sessions', color: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30' },
  weinstein_stage2: { label: 'Stan Weinstein Stage 2', desc: '30-week SMA uptrend breakout on heavy volume', color: 'bg-teal-500/15 text-teal-300 border-teal-500/30' },
  wheel_income: { label: 'Wheel Strategy / Cash Put', desc: 'High IV, no earnings in 7d, cash-secured put setup', color: 'bg-lime-500/15 text-lime-300 border-lime-500/30' },
  zanger_volume_surge: { label: 'Dan Zanger Volume Surge', desc: 'High-beta explosive volume surge', color: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30' },
};

export default function StockScreenerPage() {
  const [data, setData] = useState<ScreenerApiResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [limit, setLimit] = useState<number>(100);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const fetchScreenerData = async (runScan = false) => {
    try {
      if (runScan) setScanning(true);
      else setLoading(true);

      const url = `/api/screener?limit=${limit}${runScan ? '&run=true' : ''}`;
      const res = await fetch(url);
      const json = await res.json();

      if (json.success) {
        setData(json);
        if (json.candidates && json.candidates.length > 0 && !selectedTicker) {
          setSelectedTicker(json.candidates[0].ticker);
        }
      }
    } catch (err) {
      console.error('Failed to load screener data:', err);
    } finally {
      setLoading(false);
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchScreenerData(false);
  }, []);

  const candidates = data?.candidates || [];
  const regime = data?.market_regime || { status: 'BULL_EXPLOSIVE', spy_close: 742.09, is_macro_high_risk: false };

  // Filter candidates based on selected strategy and search query
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      // Search filter
      const matchesSearch =
        searchQuery === '' ||
        c.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.industry.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      // Strategy filter
      if (selectedStrategy === 'all') return true;
      return c.strategy_matches[selectedStrategy] === true;
    });
  }, [candidates, selectedStrategy, searchQuery]);

  const activeCandidate = useMemo(() => {
    if (!selectedTicker) return filteredCandidates[0] || null;
    return candidates.find((c) => c.ticker === selectedTicker) || filteredCandidates[0] || null;
  }, [candidates, filteredCandidates, selectedTicker]);

  const handleExport = (type: 'tradingview' | 'thinkorswim' | 'matrix') => {
    window.open(`/api/screener/export?type=${type}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-6 space-y-6 font-sans">
      {/* ─────────────────────────────────────────────────────────────────────────────
          1. Header & Navigation
         ───────────────────────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <Link href="/research">
            <Button variant="outline" size="icon" className="h-9 w-9 bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-300">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl md:text-2xl font-bold tracking-tight text-zinc-100">
                Stock Screener Engine
              </h1>
              <span className="px-2 py-0.5 text-xs font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 rounded-md">
                trade_screener v1.1.0
              </span>
            </div>
            <p className="text-xs md:text-sm text-zinc-400">
              Systematic multi-framework momentum & income setup matrix across 11 institutional strategies
            </p>
          </div>
        </div>

        {/* Market Regime Badge */}
        <div className="flex items-center space-x-3 bg-zinc-900/90 border border-zinc-800 px-4 py-2 rounded-xl">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">Global Regime</span>
            <div className="flex items-center space-x-1.5 mt-0.5">
              <span className={`h-2.5 w-2.5 rounded-full animate-pulse ${
                regime.status === 'BEAR_PROTECTIVE' ? 'bg-rose-500' : regime.status === 'BULL_CHOPIER' ? 'bg-amber-500' : 'bg-emerald-500'
              }`} />
              <span className={`text-xs font-bold font-mono ${
                regime.status === 'BEAR_PROTECTIVE' ? 'text-rose-400' : regime.status === 'BULL_CHOPIER' ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {regime.status}
              </span>
            </div>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">SPY Benchmark</span>
            <span className="text-xs font-mono font-bold text-zinc-200">${regime.spy_close.toFixed(2)}</span>
          </div>
          {regime.is_macro_high_risk && (
            <>
              <div className="h-8 w-px bg-zinc-800" />
              <div className="flex items-center space-x-1 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs px-2 py-1 rounded-md">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Macro Event Today</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          2. Control Bar & Watchlist Export Toolbar
         ───────────────────────────────────────────────────────────────────────────── */}
      <Card className="bg-zinc-900/80 border-zinc-800/80 p-4 space-y-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
          {/* Strategy Selector Dropdown */}
          <div className="flex flex-1 flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex items-center space-x-2 bg-zinc-950 border border-zinc-800 px-3 py-1.5 rounded-lg flex-1">
              <Filter className="h-4 w-4 text-cyan-400" />
              <select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="bg-transparent text-sm text-zinc-200 focus:outline-none w-full cursor-pointer font-medium"
              >
                {Object.entries(STRATEGY_LABELS).map(([key, info]) => (
                  <option key={key} value={key} className="bg-zinc-900 text-zinc-200">
                    {info.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Search Input */}
            <div className="flex items-center space-x-2 bg-zinc-950 border border-zinc-800 px-3 py-1.5 rounded-lg w-full sm:w-64">
              <Search className="h-4 w-4 text-zinc-400" />
              <input
                type="text"
                placeholder="Search ticker, company..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none w-full"
              />
            </div>
          </div>

          {/* Action Buttons & Export Controls */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => fetchScreenerData(true)}
              disabled={scanning}
              className="bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs h-9 px-4 rounded-lg shadow-lg shadow-cyan-950/50"
            >
              <RefreshCcw className={`h-3.5 w-3.5 mr-2 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Scanning Market...' : 'Run Realtime Scan'}
            </Button>

            <div className="h-6 w-px bg-zinc-800 mx-1 hidden sm:block" />

            <Button
              onClick={() => handleExport('tradingview')}
              variant="outline"
              size="sm"
              className="bg-zinc-950 border-zinc-800 hover:bg-zinc-800 text-zinc-300 text-xs h-9"
            >
              <Download className="h-3.5 w-3.5 mr-1.5 text-emerald-400" />
              TradingView CSV
            </Button>

            <Button
              onClick={() => handleExport('thinkorswim')}
              variant="outline"
              size="sm"
              className="bg-zinc-950 border-zinc-800 hover:bg-zinc-800 text-zinc-300 text-xs h-9"
            >
              <Download className="h-3.5 w-3.5 mr-1.5 text-blue-400" />
              Thinkorswim CSV
            </Button>

            <Button
              onClick={() => handleExport('matrix')}
              variant="outline"
              size="sm"
              className="bg-zinc-950 border-zinc-800 hover:bg-zinc-800 text-zinc-300 text-xs h-9"
            >
              <Layers className="h-3.5 w-3.5 mr-1.5 text-purple-400" />
              Matrix CSV
            </Button>
          </div>
        </div>

        {/* Strategy Description Banner */}
        {selectedStrategy && STRATEGY_LABELS[selectedStrategy] && (
          <div className="text-xs text-zinc-400 bg-zinc-950/60 border border-zinc-800/60 p-2.5 rounded-lg flex items-center justify-between">
            <span className="flex items-center space-x-2">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span>{STRATEGY_LABELS[selectedStrategy].desc}</span>
            </span>
            <span className="text-[11px] font-mono text-zinc-500">
              Showing {filteredCandidates.length} of {candidates.length} candidate stocks
            </span>
          </div>
        )}
      </Card>

      {/* ─────────────────────────────────────────────────────────────────────────────
          3. Main Dashboard Split View Grid
         ───────────────────────────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <RefreshCcw className="h-8 w-8 text-cyan-400 animate-spin" />
          <p className="text-sm text-zinc-400 font-mono">Loading Screener Feature Matrix & Strategy Engine...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Panel: Common Subset Strategy Comparison Matrix (7/12 = ~60%) */}
          <div className="lg:col-span-7 space-y-4">
            <Card className="bg-zinc-900/80 border-zinc-800/80 p-0 overflow-hidden">
              <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-900">
                <div className="flex items-center space-x-2">
                  <BarChart3 className="h-4 w-4 text-emerald-400" />
                  <h2 className="text-sm font-bold text-zinc-100 uppercase tracking-wider">
                    Candidate Strategy Matrix
                  </h2>
                </div>
                <span className="text-xs text-zinc-400 font-mono">
                  Sorted by Common Subset Match Count
                </span>
              </div>

              <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800 sticky top-0 uppercase tracking-wider">
                    <tr>
                      <th className="p-3">Ticker</th>
                      <th className="p-3">Company</th>
                      <th className="p-3">Sector</th>
                      <th className="p-3 text-right">Close</th>
                      <th className="p-3 text-center">Matches</th>
                      <th className="p-3">Matched Strategies</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {filteredCandidates.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="p-8 text-center text-zinc-500">
                          No stocks matched the selected filters or strategy rules.
                        </td>
                      </tr>
                    ) : (
                      filteredCandidates.map((c) => {
                        const isSelected = activeCandidate?.ticker === c.ticker;
                        const isCommonSubset = c.matched_strategies_count >= 2;

                        return (
                          <tr
                            key={c.ticker}
                            onClick={() => setSelectedTicker(c.ticker)}
                            className={`cursor-pointer transition-colors ${
                              isSelected
                                ? 'bg-cyan-950/40 text-cyan-200 border-l-4 border-l-cyan-400'
                                : isCommonSubset
                                ? 'bg-emerald-950/20 hover:bg-emerald-900/30 text-zinc-200'
                                : 'hover:bg-zinc-800/40 text-zinc-300'
                            }`}
                          >
                            <td className="p-3 font-bold text-sm text-zinc-100 flex items-center space-x-1.5">
                              <span>{c.ticker}</span>
                              {isCommonSubset && (
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400" />
                              )}
                            </td>
                            <td className="p-3 text-zinc-400 max-w-[140px] truncate">{c.company}</td>
                            <td className="p-3 text-zinc-400 text-[11px] max-w-[120px] truncate">{c.sector}</td>
                            <td className="p-3 text-right font-bold text-zinc-100">${c.close.toFixed(2)}</td>
                            <td className="p-3 text-center">
                              <span
                                className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                                  isCommonSubset
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                    : 'bg-zinc-800 text-zinc-400'
                                }`}
                              >
                                {c.matched_strategies_count}
                              </span>
                            </td>
                            <td className="p-3">
                              <div className="flex flex-wrap gap-1">
                                {c.matched_strategies_list.split(',').map((sName) => {
                                  const trimmed = sName.trim();
                                  if (!trimmed || trimmed === 'None') return null;
                                  return (
                                    <span
                                      key={trimmed}
                                      className="px-1.5 py-0.5 text-[10px] rounded bg-zinc-800 text-zinc-300 border border-zinc-700"
                                    >
                                      {trimmed}
                                    </span>
                                  );
                                })}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>

          {/* Right Panel: Selected Candidate Inspector (5/12 = ~40%) */}
          <div className="lg:col-span-5 space-y-4">
            {activeCandidate ? (
              <Card className="bg-zinc-900/80 border-zinc-800/80 p-5 space-y-5">
                <div className="flex items-start justify-between border-b border-zinc-800 pb-4">
                  <div>
                    <div className="flex items-center space-x-2">
                      <h2 className="text-2xl font-bold font-mono text-zinc-100">{activeCandidate.ticker}</h2>
                      <span className="text-xs text-zinc-400 bg-zinc-950 px-2 py-0.5 rounded border border-zinc-800">
                        {activeCandidate.sector}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">{activeCandidate.company}</p>
                    <p className="text-[11px] text-zinc-500">{activeCandidate.industry}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold font-mono text-emerald-400">
                      ${activeCandidate.close.toFixed(2)}
                    </div>
                    <span className="text-[11px] text-zinc-400 font-mono">Daily Split Close</span>
                  </div>
                </div>

                {/* Strategy Confirmation Breakdown */}
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                    Institutional Strategy Alignments
                  </h3>
                  <div className="grid grid-cols-1 gap-2">
                    {Object.entries(activeCandidate.strategy_matches).map(([sKey, isMatch]) => {
                      const sMeta = STRATEGY_LABELS[sKey] || { label: sKey, color: '' };
                      return (
                        <div
                          key={sKey}
                          className={`p-2.5 rounded-lg border flex items-center justify-between text-xs font-mono transition-colors ${
                            isMatch
                              ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                              : 'bg-zinc-950/40 border-zinc-800/60 text-zinc-500'
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            {isMatch ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                            ) : (
                              <div className="h-4 w-4 rounded-full border border-zinc-700" />
                            )}
                            <span>{sMeta.label}</span>
                          </div>
                          <span className={`text-[10px] uppercase font-bold ${isMatch ? 'text-emerald-400' : 'text-zinc-600'}`}>
                            {isMatch ? 'MATCH' : 'PASSED'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* External Links */}
                <div className="pt-2 border-t border-zinc-800 flex items-center justify-between text-xs">
                  <a
                    href={`https://www.tradingview.com/chart/?symbol=${activeCandidate.ticker}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
                  >
                    <span>View on TradingView</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href={`https://finviz.com/quote.ashx?t=${activeCandidate.ticker}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-zinc-400 hover:text-zinc-300 flex items-center space-x-1"
                  >
                    <span>View on Finviz</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </Card>
            ) : (
              <Card className="bg-zinc-900/80 border-zinc-800/80 p-8 text-center text-zinc-500">
                Select a candidate ticker from the matrix to inspect strategy alignments and technical parameters.
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
