import prisma from '@/lib/prisma';
import { MacroSnapshotData, WhaleAnomaly, DominantNode } from '@/types/macro';
import { Waves, Activity, Clock, Database, Shield, Zap } from 'lucide-react';
import Link from 'next/link';

async function getAvailableTickers() {
  const snapshots = await prisma.macroSnapshot.findMany({
    select: { ticker: true },
    distinct: ['ticker'],
  });
  return snapshots.map(s => s.ticker).sort();
}

async function getMacroData(ticker: string = 'SPX') {
  const snapshot = await prisma.macroSnapshot.findFirst({
    where: { ticker },
    orderBy: { tradingDate: 'desc' },
  });

  if (!snapshot) return null;

  const parsedData: MacroSnapshotData = {
    ...snapshot,
    timestamp: snapshot.timestamp.toISOString(),
    tradingDate: snapshot.tradingDate.toISOString(),
    anomalies: snapshot.anomalies ? JSON.parse(snapshot.anomalies) : { structural: [], tactical: [] },
    dominantNodes: snapshot.dominantNodes ? JSON.parse(snapshot.dominantNodes) : [],
  };

  return parsedData;
}

// Ensure the page is always dynamic to show latest macro snapshots
export const dynamic = 'force-dynamic';

export default async function MacroDashboard(props: {
  searchParams: Promise<{ ticker?: string }>;
}) {
  const searchParams = await props.searchParams;
  const activeTicker = searchParams.ticker || 'SPX';
  const data = await getMacroData(activeTicker);
  const availableTickers = await getAvailableTickers();

  if (!data) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-400">
        <div className="text-center">
          <Activity className="mx-auto h-12 w-12 text-zinc-600 mb-4" />
          <h2 className="text-xl font-semibold text-zinc-200">No Macro Data Found</h2>
          <p>We couldn't find any macro data for ticker {activeTicker}.</p>
        </div>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(value);
  };

  const formatStrike = (strike: number) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
    }).format(strike);
  };

  const intl = new Intl.NumberFormat('en-US');

  // Group anomalies by tier from both structural and tactical buckets
  const allAnomalies = [
    ...(data.anomalies?.structural || []),
    ...(data.anomalies?.tactical || [])
  ];

  const tier1 = allAnomalies.filter((a) => a.tier === 1);
  const tier2 = allAnomalies.filter((a) => a.tier === 2);
  const tier3 = allAnomalies.filter((a) => a.tier === 3);
  const tier4 = allAnomalies.filter((a) => a.tier === 4);

  const renderTierTable = (title: string, subtitle: string, anomalies: WhaleAnomaly[]) => (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-zinc-100">{title}</h3>
        <p className="text-xs text-zinc-400">{subtitle}</p>
      </div>
      {anomalies.length === 0 ? (
        <div className="py-6 text-center text-sm text-zinc-500">No anomalies in this tier</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400">
                <th className="pb-3 pr-4 font-medium">Strike</th>
                <th className="pb-3 pr-4 font-medium">Type</th>
                <th className="pb-3 pr-4 font-medium">DTE</th>
                <th className="pb-3 pr-4 font-medium">Vol/OI</th>
                <th className="pb-3 font-medium text-right">Notional</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {anomalies.map((a, i) => (
                <tr key={i} className="group hover:bg-zinc-800/30 transition-colors">
                  <td className="py-3 pr-4 font-mono font-semibold text-zinc-200">{formatStrike(a.strike)}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={`inline-flex items-center rounded-sm px-2 py-[2px] text-xs font-bold tracking-wider ${
                        a.type === 'CALL'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {a.type}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-zinc-300">{a.dte_str}</td>
                  <td className="py-3 pr-4">
                    <span className={a.avg_vol_oi_ratio > 3 ? 'text-amber-400 font-medium' : 'text-zinc-400'}>
                      {a.avg_vol_oi_ratio.toFixed(2)}x
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono font-medium text-zinc-200">
                    {formatCurrency(a.notional)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50 selection:bg-indigo-500/30">
      {/* Header (Section 1) */}
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                <Waves className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  QUANT MACRO
                  <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-300">
                    {data.ticker}
                  </span>
                </h1>
                
                {/* Ticker Selector moved to left side under title */}
                <div className="flex space-x-2 overflow-x-auto py-2">
                  {availableTickers.map((t) => (
                    <a
                      key={t}
                      href={`/macro?ticker=${encodeURIComponent(t)}`}
                      className={`px-3 py-1 text-xs font-semibold rounded-full border transition-colors ${
                        t === activeTicker
                          ? 'bg-indigo-500 text-white border-indigo-500/50'
                          : 'bg-zinc-800/50 text-zinc-400 border-zinc-700 hover:bg-zinc-700 hover:text-white'
                      }`}
                    >
                      {t}
                    </a>
                  ))}
                </div>
                
                <div className="flex items-center text-xs text-zinc-400">
                  <Clock className="mr-1 h-3 w-3" />
                  Last Updated: {new Date(data.timestamp).toLocaleString()}
                </div>
              </div>
            </div>

            <div className="text-right">
              <p className="text-sm font-medium text-zinc-400">Spot Price</p>
              <p className="font-mono text-2xl font-bold text-white">
                {formatStrike(data.spotPrice)}
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Structural Mechanics (Section 2) */}
        <section className="mb-10">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-zinc-500">
            Structural Mechanics (Pillar 2)
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* Zero Gamma */}
            <div className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-sm">
              <div className="absolute right-0 top-0 -mr-4 -mt-4 h-24 w-24 rounded-full bg-amber-500/5 blur-2xl"></div>
              <p className="text-sm font-medium text-amber-500/80">Zero Gamma</p>
              <p className="mt-2 font-mono text-3xl font-bold text-amber-400">
                {data.zeroGamma ? formatStrike(data.zeroGamma) : 'N/A'}
              </p>
            </div>

            {/* Macro Call Wall */}
            <div className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-sm">
              <div className="absolute right-0 top-0 -mr-4 -mt-4 h-24 w-24 rounded-full bg-rose-500/5 blur-2xl"></div>
              <p className="text-sm font-medium text-rose-500/80">Macro Call Wall</p>
              <p className="mt-2 font-mono text-3xl font-bold text-rose-400 flex items-baseline gap-2">
                {data.macroCallWall ? formatStrike(data.macroCallWall) : 'N/A'}
                <span className="text-xs font-medium uppercase tracking-wider text-rose-500/60">Resistance</span>
              </p>
            </div>

            {/* Macro Put Wall */}
            <div className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-sm">
              <div className="absolute right-0 top-0 -mr-4 -mt-4 h-24 w-24 rounded-full bg-emerald-500/5 blur-2xl"></div>
              <p className="text-sm font-medium text-emerald-500/80">Macro Put Wall</p>
              <p className="mt-2 font-mono text-3xl font-bold text-emerald-400 flex items-baseline gap-2">
                {data.macroPutWall ? formatStrike(data.macroPutWall) : 'N/A'}
                <span className="text-xs font-medium uppercase tracking-wider text-emerald-500/60">Support</span>
              </p>
            </div>
          </div>
        </section>

        {/* The Map & The Whales (Section 3) */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Liquidity Map (Structural Nodes) */}
          <section className="lg:col-span-1">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-500">
                Liquidity Map (Pillar 2)
              </h2>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-sm">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                  <Database className="h-4 w-4 text-indigo-400" />
                  Structural Nodes
                </h3>
                <p className="text-xs text-zinc-400">Major resting Open Interest concentrations (The Map)</p>
              </div>
              {data.dominantNodes.length === 0 ? (
                <div className="py-6 text-center text-sm text-zinc-500">No major nodes detected</div>
              ) : (
                <div className="space-y-3">
                  {data.dominantNodes.map((node, i) => (
                    <div key={i} className="flex items-center justify-between rounded-lg border border-zinc-800/50 bg-zinc-800/30 p-3">
                      <div>
                        <p className="font-mono text-sm font-bold text-zinc-200">{formatStrike(node.strike)}</p>
                        <p className="text-[10px] uppercase tracking-wider text-zinc-500">{node.type} NODE</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-indigo-400">{node.dominance_pct}%</p>
                        <p className="text-[10px] text-zinc-500">{intl.format(node.oi)} contracts</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Whale Tracker Grid */}
          <section className="lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-500">
                The Whale Tracker (Pillar 1)
              </h2>
              <div className="flex space-x-2">
                <span className="inline-flex items-center rounded bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-300">
                  {allAnomalies.length} Total Anomalies
                </span>
              </div>
            </div>
            
            <div className="grid grid-cols-1 gap-6">
              {renderTierTable('0-30 Days', 'Immediate Expirations (Tier 1)', tier1)}
              {renderTierTable('31-90 Days', 'Medium Term (Tier 2)', tier2)}
              {renderTierTable('91-180 Days', 'Long Term (Tier 3)', tier3)}
              {renderTierTable('180+ Days', 'LEAPS & Extended (Tier 4)', tier4)}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
