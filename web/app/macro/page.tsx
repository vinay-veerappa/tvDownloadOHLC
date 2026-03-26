import prisma from '@/lib/prisma';
import { MacroSnapshotData, WhaleAnomaly, DominantNode } from '@/types/macro';
import { Waves, Activity, Clock, Database, Shield, Zap } from 'lucide-react';
import Link from 'next/link';

async function getAvailableTickers() {
  const snapshots = await prisma.macroSnapshot.findMany({
    select: { ticker: true },
    distinct: ['ticker'],
  });
  
  const allTickers = snapshots.map(s => s.ticker);
  
  // Group by root (e.g. SPX, /ES)
  const groups: Record<string, string[]> = {};
  allTickers.forEach(t => {
    const root = t.replace(/\[[DM]\]$/, '');
    if (!groups[root]) groups[root] = [];
    groups[root].push(t);
  });
  
  return groups;
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
  const searchParamsValue = await props.searchParams;
  const initialTicker = searchParamsValue.ticker || 'SPX';
  const groups = await getAvailableTickers();
  const roots = Object.keys(groups).sort();
  
  // Determine root and variants
  const activeRoot = initialTicker.replace(/\[[DM]\]$/, '');
  const variants = groups[activeRoot] || [initialTicker];
  
  // We prioritize the [M] variant if user just selects root and it exists
  const activeTicker = (initialTicker === activeRoot && variants.includes(`${activeRoot}[M]`)) 
    ? `${activeRoot}[M]` 
    : initialTicker;
  
  const data = await getMacroData(activeTicker);

  if (!data) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-400 p-8">
        <div className="text-center max-w-md">
          <Activity className="mx-auto h-16 w-16 text-zinc-800 mb-6 animate-pulse" />
          <h2 className="text-2xl font-black text-white mb-2 tracking-tighter">LIQUIDITY GAP DETECTED</h2>
          <p className="text-sm text-zinc-500 mb-8 font-mono uppercase tracking-widest">No active snapshot found for marker {activeTicker}</p>
          <div className="flex flex-wrap gap-2 justify-center">
             {roots.map(r => (
               <a key={r} href={`/macro?ticker=${encodeURIComponent(r)}`} className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded text-xs font-bold hover:bg-zinc-800 transition-colors uppercase tracking-widest">
                 {r}
               </a>
             ))}
          </div>
        </div>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD', maximumFractionDigits: 0, notation: 'compact',
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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-sm overflow-hidden relative group">
      <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
        <Zap className="h-24 w-24 text-white" />
      </div>
      <div className="mb-4 relative z-10">
        <h3 className="text-lg font-black text-zinc-100 uppercase tracking-tighter">{title}</h3>
        <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">{subtitle}</p>
      </div>
      {anomalies.length === 0 ? (
        <div className="py-8 text-center text-xs font-mono uppercase tracking-widest text-zinc-600 border border-dashed border-zinc-800 rounded-lg">No Significant Orderflow</div>
      ) : (
        <div className="overflow-x-auto relative z-10">
          <table className="w-full text-left text-xs whitespace-nowrap">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 uppercase tracking-widest font-black">
                <th className="pb-3 pr-4">Strike</th>
                <th className="pb-3 pr-4">Type</th>
                <th className="pb-3 pr-4">DTE</th>
                <th className="pb-3 pr-4">Vol/OI</th>
                <th className="pb-3 text-right">Notional</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/10">
              {anomalies.map((a, i) => (
                <tr key={i} className="group/row hover:bg-white/[0.02] transition-colors">
                  <td className="py-3 pr-4 font-mono font-black text-zinc-100">{formatStrike(a.strike)}</td>
                  <td className="py-3 pr-4">
                    <span className={`inline-flex items-center rounded-sm px-1.5 py-[1px] text-[9px] font-black tracking-tighter border ${
                        a.type === 'CALL' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}>
                      {a.type}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-zinc-400 font-bold">{a.dte_str}</td>
                  <td className="py-3 pr-4">
                    <span className={a.avg_vol_oi_ratio > 3 ? 'text-amber-400 font-black underline decoration-amber-500/30 underline-offset-4' : 'text-zinc-500'}>
                      {a.avg_vol_oi_ratio.toFixed(2)}x
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono font-bold text-white">
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
    <div className="min-h-screen bg-zinc-950 text-zinc-50 selection:bg-indigo-500/40 selection:text-white pb-20">
      {/* Dynamic Background Noise */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]"></div>
      
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-zinc-950/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex flex-col gap-4">
              <div className="flex items-center space-x-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.03] border border-white/10 shadow-inner">
                  <Waves className="h-6 w-6 text-indigo-400" />
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-black tracking-tight text-white uppercase italic">
                      QUANT<span className="text-zinc-500 not-italic ml-1">MACRO</span>
                    </h1>
                    <div className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[10px] font-black text-indigo-400 uppercase tracking-tighter">
                      {data.ticker}
                    </div>
                  </div>
                </div>
              </div>
              
              <nav className="flex flex-col gap-4">
                {/* Global Markets Scroller */}
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide no-scrollbar -mx-4 px-4 mask-fade-right">
                  {roots.map((root) => (
                    <a
                      key={root}
                      href={`/macro?ticker=${encodeURIComponent(root)}`}
                      className={`px-4 py-2 text-[10px] font-black uppercase tracking-widest rounded-lg border transition-all whitespace-nowrap ${
                        root === activeRoot
                          ? 'bg-white text-zinc-950 border-white shadow-[0_0_20px_rgba(255,255,255,0.1)] scale-105 z-10'
                          : 'bg-zinc-900/50 text-zinc-500 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/50'
                      }`}
                    >
                      {root}
                    </a>
                  ))}
                </div>

                {/* Dual Mapping Switch (Comparison Task) */}
                {variants.length > 1 && (
                  <div className="flex items-center p-1 rounded-full bg-zinc-900/80 border border-white/5 w-fit">
                    {[...variants].sort().reverse().map((v) => {
                      // Ensure explicit markers for futures
                      const isDirect = v.includes('[D]') || (v === activeRoot && !v.includes('[M]'));
                      const isMapped = v.includes('[M]');
                      const targetTicker = isDirect ? (v.includes('[D]') ? v : `${v}[D]`) : (isMapped ? v : `${v}[M]`);
                      const isActive = activeTicker === v || (activeTicker === targetTicker);

                      return (
                        <a
                          key={v}
                          href={`/macro?ticker=${encodeURIComponent(targetTicker)}`}
                          className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-full transition-all ${
                            isActive
                              ? 'bg-indigo-600 text-white shadow-[0_0_15px_rgba(79,70,229,0.4)]'
                              : 'text-zinc-600 hover:text-zinc-400'
                          }`}
                        >
                          {isActive ? '● ' : ''}
                          {isDirect ? 'Direct Fut' : isMapped ? 'Mapped Idx' : 'Primary'}
                        </a>
                      );
                    })}
                  </div>
                )}
              </nav>
            </div>

            <div className="flex items-center gap-8 self-end md:self-center bg-zinc-900/30 p-4 rounded-2xl border border-white/5 backdrop-blur-sm">
                <div className="flex flex-col items-end">
                    <p className="text-[10px] font-black uppercase tracking-widest text-zinc-500 mb-1">Last Updated</p>
                    <p className="text-xs font-bold text-zinc-300 font-mono italic">
                        {new Date(data.timestamp).toLocaleTimeString()}
                    </p>
                </div>
                <div className="w-px h-10 bg-white/5"></div>
                <div className="flex flex-col items-end">
                    <p className="text-[10px] font-black uppercase tracking-widest text-indigo-500 mb-1">Spot Execution</p>
                    <p className="font-mono text-3xl font-black text-white tracking-tighter leading-none">
                        {formatStrike(data.spotPrice)}
                    </p>
                </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Structural Mechanics */}
        <section className="mb-16">
          <div className="flex items-center gap-4 mb-8">
            <h2 className="text-xs font-black uppercase tracking-[0.3em] text-zinc-500 border-l-2 border-indigo-500 pl-4">
              Structural Mechanics
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            {[
                { label: 'Zero Gamma', value: data.zeroGamma, color: 'text-amber-400', bg: 'bg-amber-400/5', border: 'border-amber-400/20' },
                { label: 'Macro Call Wall', value: data.macroCallWall, color: 'text-rose-400', bg: 'bg-rose-400/5', border: 'border-rose-400/20', note: 'Resistance' },
                { label: 'Macro Put Wall', value: data.macroPutWall, color: 'text-emerald-400', bg: 'bg-emerald-400/5', border: 'border-emerald-400/20', note: 'Support' }
            ].map((card, i) => (
                <div key={i} className={`relative overflow-hidden rounded-2xl border ${card.border} ${card.bg} p-8 transition-transform hover:scale-[1.02] duration-300`}>
                  <p className={`text-[10px] font-black uppercase tracking-[0.2em] ${card.color} mb-4`}>{card.label}</p>
                  <p className={`font-mono text-4xl font-black ${card.color} tracking-tighter`}>
                    {card.value ? formatStrike(card.value) : '---'}
                  </p>
                  {card.note && (
                      <span className={`mt-2 inline-block text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${card.border} ${card.color} bg-white/5`}>
                          {card.note}
                      </span>
                  )}
                </div>
            ))}
          </div>
        </section>

        {/* The Map & The Whales */}
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-3">
          {/* Liquidity Map */}
          <section className="lg:col-span-1">
            <div className="mb-8 pl-4 border-l-2 border-zinc-800">
              <h2 className="text-xs font-black uppercase tracking-[0.3em] text-zinc-500">The Map</h2>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-6 backdrop-blur-sm">
              <div className="mb-6">
                <h3 className="text-xl font-black text-white flex items-center gap-3 italic uppercase">
                  <Database className="h-5 w-5 text-indigo-400" />
                  OI Hubs
                </h3>
              </div>
              {(!data.dominantNodes || data.dominantNodes.length === 0) ? (
                <div className="py-12 text-center text-[10px] font-black uppercase tracking-widest text-zinc-700">Equilibrium / No Major Nodes</div>
              ) : (
                <div className="space-y-4">
                  {data.dominantNodes.map((node, i) => (
                    <div key={i} className="group flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] p-4 hover:border-indigo-500/30 transition-all">
                      <div>
                        <p className="font-mono text-lg font-black text-zinc-100">{formatStrike(node.strike)}</p>
                        <p className={`text-[9px] font-black uppercase tracking-[0.2em] ${node.type === 'CALL' ? 'text-emerald-500' : 'text-rose-500'}`}>
                            {node.type} CONCENTRATION
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-xl font-black text-indigo-400 italic">
                            {node.dominance_pct}%<span className="text-[10px] ml-1 opacity-50 not-italic">DOM</span>
                        </div>
                        <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">{intl.format(node.oi)} VOL</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Whale Tracker */}
          <section className="lg:col-span-2">
            <div className="mb-8 flex items-center justify-between px-4 border-l-2 border-zinc-800">
              <h2 className="text-xs font-black uppercase tracking-[0.3em] text-zinc-500">The Whale Tracker</h2>
              <span className="px-3 py-1 rounded bg-indigo-500/10 border border-indigo-500/20 text-[10px] font-black text-indigo-400 uppercase tracking-widest">
                {allAnomalies.length} BLOCKS DETECTED
              </span>
            </div>
            
            <div className="grid grid-cols-1 gap-8">
              {renderTierTable('Tactical Bucket', 'Immediate Gamma (Tier 1: 0-30 DTE)', tier1)}
              {renderTierTable('Standard Bucket', 'Positioning (Tier 2: 31-90 DTE)', tier2)}
              {renderTierTable('Structural Tier', 'Long Cycles (Tier 3: 91-180 DTE)', tier3)}
              {renderTierTable('Institutional LEAPS', 'Structural Walls (Tier 4: 180+ DTE)', tier4)}
            </div>
          </section>
        </div>
      </main>

      {/* Footer Branding */}
      <footer className="mt-20 border-t border-white/5 py-12">
          <div className="mx-auto max-w-7xl px-4 flex justify-between items-center opacity-20">
              <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  <span className="text-[10px] font-black uppercase tracking-[0.4em]">Proprietary Data Systems</span>
              </div>
              <p className="text-[10px] font-bold uppercase tracking-widest italic">Institutional Grade Intelligence</p>
          </div>
      </footer>
    </div>
  );
}
