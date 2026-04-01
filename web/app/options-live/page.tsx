"use client"

import React, { useState, useEffect, useMemo } from 'react'
import { 
  Activity, 
  TrendingUp, 
  Zap, 
  Target, 
  ShieldCheck, 
  AlertTriangle,
  Info,
  Database,
  Timer,
  Crosshair,
  ArrowUpRight,
  ArrowDownRight,
  Maximize2,
  Minimize2,
  ChevronRight,
  ChevronLeft,
  LayoutGrid,
  ZapOff,
  Layers,
  History,
  TrendingDown
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  ResponsiveContainer, 
  ReferenceLine,
  Cell,
  ComposedChart,
  Line,
  Area,
  AreaChart,
  Legend
} from 'recharts'
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

// Modular Components
import { DashboardTopBar } from '@/components/options-live/DashboardTopBar'
import { ActiveMetricsHUD } from '@/components/options-live/ActiveMetricsHUD'
import { TacticalBriefingSidebar } from '@/components/options-live/TacticalBriefingSidebar'

/**
 * UTILITIES & FORMATTERS
 */
const fmtGex = (val: number | undefined) => {
  if (val === undefined || isNaN(val)) return '—'
  const abs = Math.abs(val)
  if (abs >= 1e9) return (val / 1e9).toFixed(2) + 'B'
  if (abs >= 1e6) return (val / 1e6).toFixed(1) + 'M'
  if (abs >= 1e3) return (val / 1e3).toFixed(1) + 'K'
  return val.toFixed(0)
}

const getHeatColor = (val: number | undefined, threshold: number = 0) => {
  if (val === undefined) return 'text-zinc-500'
  if (val > threshold) return 'text-emerald-400'
  if (val < -threshold) return 'text-rose-400'
  return 'text-zinc-400'
}

/**
 * MAIN PAGE COMPONENT
 */
export default function OptionsLivePage() {
  // ── UI State ──
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)
  const [activeTicker, setActiveTicker] = useState('SPY')
  const [refreshInterval, setRefreshInterval] = useState(15000)
  const [mainTab, setMainTab] = useState('profile')
  const [profileOption, setProfileOption] = useState<'nodes' | 'net' | 'liquidity'>('nodes')
  const [strikeZoomRange, setStrikeZoomRange] = useState(5) // % around ATM

  // ── Data State ──
  const [ms, setMs] = useState<any>({ 
    pipelineState: { tickers: {} }, 
    gexProfiles: { profiles: {} }, 
    liveTrend: { history: {} } 
  })
  const [lastSync, setLastSync] = useState<Date | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // ── Data Fetching ──
  const fetchData = async () => {
    try {
      const res = await fetch('/api/options-live');
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const json = await res.json();
      if (json.success) {
        setMs(json.data);
        setLastSync(new Date());
      }
      setIsLoading(false);
    } catch (e) {
      console.error('Fetch Error:', e);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, refreshInterval);
    return () => clearInterval(timer);
  }, [refreshInterval]);

  // ── Memoized Analytics ──
  const activeDetail = useMemo(() => {
    if (!ms.pipelineState?.tickers) return null;
    const key = activeTicker.startsWith('/') ? activeTicker : (ms.pipelineState.tickers[activeTicker] ? activeTicker : `/${activeTicker}`);
    return ms.pipelineState.tickers[key] || ms.pipelineState.tickers[activeTicker] || Object.values(ms.pipelineState.tickers)[0];
  }, [ms, activeTicker]);

  const activeTrendData = useMemo(() => {
    if (!ms.gexProfiles?.profiles) return [];
    const key = activeTicker.startsWith('/') ? activeTicker.slice(1) : activeTicker;
    return ms.gexProfiles.profiles[key] || ms.gexProfiles.profiles[activeTicker] || [];
  }, [ms, activeTicker]);

  const historicalTrend = useMemo(() => {
    if (!ms.liveTrend?.history) return [];
    const key = activeTicker.startsWith('/') ? activeTicker.slice(1) : activeTicker;
    return ms.liveTrend.history[key] || ms.liveTrend.history[activeTicker] || [];
  }, [ms, activeTicker]);

  const zoomedProfile = useMemo(() => {
    if (!activeTrendData.length || !activeDetail) return [];
    const spot = activeDetail.spot;
    const range = spot * (strikeZoomRange / 100);
    return activeTrendData.filter((p: any) => p.strike >= spot - range && p.strike <= spot + range);
  }, [activeTrendData, activeDetail, strikeZoomRange]);

  const cumulativeGex = useMemo(() => {
    if (!activeTrendData.length) return [];
    let sum = 0;
    return [...activeTrendData].sort((a, b) => a.strike - b.strike).map((p: any) => {
      sum += (p.net_gex || 0);
      return { ...p, cumulative: sum };
    });
  }, [activeTrendData]);

  const volSummary = useMemo(() => {
    if (!activeTrendData.length || !activeDetail) return { near: [] };
    const near = activeTrendData.filter((p: any) => Math.abs(p.strike - activeDetail.spot) / activeDetail.spot < 0.03);
    return { near };
  }, [activeTrendData, activeDetail]);

  const dexProfile = useMemo(() => {
    if (!activeTrendData.length || !activeDetail) return [];
    const spot = activeDetail.spot;
    const range = spot * 0.05;
    return activeTrendData
      .filter((p: any) => p.strike >= spot - range && p.strike <= spot + range)
      .map((p: any) => ({
        ...p,
        net_dex: (p.call_dex || 0) + (p.put_dex || 0)
      }));
  }, [activeTrendData, activeDetail]);

  const skewProfile = useMemo(() => {
    if (!activeTrendData.length || !activeDetail) return [];
    const spot = activeDetail.spot;
    const range = spot * 0.05;
    return activeTrendData
      .filter((p: any) => p.strike >= spot - range && p.strike <= spot + range)
      .map((p: any) => ({
        ...p,
        skew: (p.put_iv || 0) - (p.call_iv || 0)
      }));
  }, [activeTrendData, activeDetail]);

  const priceLadder = useMemo(() => {
    if (!activeDetail) return [];
    const spot = activeDetail.spot || 0;
    const items = [
      { label: 'Spot Price', price: spot, type: 'spot', note: 'Current Telemetry' },
      { label: 'Zero Gamma', price: activeDetail.zero_gamma || 0, type: 'magnet', note: 'Volatility Flip Point' },
      { label: 'Call Wall', price: activeDetail.call_wall || 0, type: 'resistance', note: 'Top Cap Barrier' },
      { label: 'Put Wall', price: activeDetail.put_wall || 0, type: 'resistance', note: 'Liquidity Support' }
    ];
    return items.sort((a, b) => b.price - a.price);
  }, [activeDetail]);

  const drillSpot = activeDetail?.spot || 0;

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-black gap-6">
        <Activity size={48} className="text-emerald-500 animate-pulse" />
        <div className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.5em] animate-pulse">Initializing Terminal Architecture...</div>
      </div>
    );
  }

  return (
    <TooltipProvider>
    <div className="h-screen w-screen bg-black text-zinc-100 flex flex-col overflow-hidden selection:bg-emerald-500/30">
      
      <DashboardTopBar 
        activeTicker={activeTicker} 
        setActiveTicker={setActiveTicker}
        lastSync={lastSync}
        refreshInterval={refreshInterval}
        setRefreshInterval={setRefreshInterval}
        strikeZoomRange={strikeZoomRange}
        setStrikeZoomRange={setStrikeZoomRange}
      />

      <div className="flex flex-1 overflow-hidden bg-zinc-950 relative">
         {/* ── Sidebar (Left): Watchlist & Tickers ── */}
         <aside className={`border-r border-white/5 bg-zinc-950/50 flex flex-col transition-all duration-500 ease-in-out z-40 relative ${sidebarOpen ? 'w-80' : 'w-0 opacity-0 pointer-events-none'}`}>
            <ScrollArea className="flex-1">
               <div className="p-6 space-y-4">
                  <div className="flex items-center justify-between mb-4 px-2">
                     <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Active Telemetry</span>
                     <button 
                        onClick={() => setSidebarOpen(false)}
                        className="h-7 w-7 rounded-lg bg-zinc-900 border border-white/5 flex items-center justify-center text-zinc-500 hover:text-emerald-500 hover:border-emerald-500/20 transition-all group"
                        title="Collapse Watchlist (<<)"
                     >
                        <ChevronLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
                     </button>
                  </div>
                  {Object.values(ms.pipelineState?.tickers || {}).map((p: any) => (
                     <button
                        key={p.ticker}
                        onClick={() => setActiveTicker(p.ticker)}
                        className={`w-full group relative p-5 rounded-2xl border transition-all duration-300 flex items-center justify-between ${
                           activeTicker === p.ticker 
                              ? 'bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.05)]' 
                              : 'bg-zinc-900/20 border-white/5 hover:border-white/10 hover:bg-zinc-900/40'
                        }`}
                     >
                        <div className="flex flex-col items-start gap-1">
                           <span className={`text-sm font-black tracking-tight ${activeTicker === p.ticker ? 'text-emerald-400' : 'text-zinc-200'}`}>{p.ticker}</span>
                           <span className="text-xl font-mono font-black tracking-tighter text-white">${p.spot?.toFixed(2)}</span>
                        </div>
                        <div className="text-right flex flex-col gap-1 items-end">
                           <div className={`text-[10px] font-black ${getHeatColor(p.total_gex, 1e9)}`}>{fmtGex(p.total_gex)}</div>
                           <div className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Total GEX</div>
                        </div>
                     </button>
                  ))}
               </div>
            </ScrollArea>
         </aside>

         {!sidebarOpen && (
            <button 
               onClick={() => setSidebarOpen(true)}
               className="absolute left-6 top-10 z-50 p-3 bg-zinc-900 border border-white/10 rounded-xl text-emerald-500 hover:scale-110 transition-all shadow-2xl group"
               title="Expand Watchlist (>>)"
            >
               <ChevronRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
         )}

         {/* ── Main Content Area (Center) ── */}
         <main className="flex-1 min-w-0 flex flex-col relative overflow-hidden bg-zinc-950">
            <ActiveMetricsHUD activeDetail={activeDetail} />

            <ScrollArea className="flex-1 h-full">
               <div className="p-8 pb-32">
                  <div className="grid grid-cols-12 gap-8 h-full min-h-[1400px]">
                     <div className="col-span-12 h-full flex flex-col gap-8">
                        <Card className="bg-zinc-900/30 border-white/5 rounded-[3rem] overflow-hidden backdrop-blur-xl border flex flex-col">
                           <div className="p-8 border-b border-white/5 flex items-center justify-between bg-zinc-900/20">
                              <Tabs value={mainTab} onValueChange={(v) => setMainTab(v)} className="w-[60%]">
                                 <TabsList className="bg-zinc-950/50 p-1.5 rounded-2xl border border-white/5 h-12">
                                    <TabsTrigger value="profile" className="rounded-xl text-[10px] font-black uppercase tracking-widest px-6 data-[state=active]:bg-zinc-800 data-[state=active]:text-emerald-400">GEX Profile</TabsTrigger>
                                    <TabsTrigger value="cumulative" className="rounded-xl text-[10px] font-black uppercase tracking-widest px-6 data-[state=active]:bg-zinc-800 data-[state=active]:text-emerald-400">Cumulative</TabsTrigger>
                                    <TabsTrigger value="dex" className="rounded-xl text-[10px] font-black uppercase tracking-widest px-6 data-[state=active]:bg-zinc-800 data-[state=active]:text-emerald-400">DEX Mapping</TabsTrigger>
                                    <TabsTrigger value="skew" className="rounded-xl text-[10px] font-black uppercase tracking-widest px-6 data-[state=active]:bg-zinc-800 data-[state=active]:text-emerald-400">IV Skew</TabsTrigger>
                                    <TabsTrigger value="history" className="rounded-xl text-[10px] font-black uppercase tracking-widest px-6 data-[state=active]:bg-zinc-800 data-[state=active]:text-emerald-400">Trend History</TabsTrigger>
                                 </TabsList>
                              </Tabs>
                              
                              <div className="flex items-center gap-4">
                                 {mainTab === 'profile' && (
                                    <div className="flex bg-zinc-950/50 p-1 rounded-xl border border-white/5">
                                       <Button variant="ghost" size="sm" className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'nodes' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`} onClick={() => setProfileOption('nodes')}>Nodes</Button>
                                       <Button variant="ghost" size="sm" className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'net' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`} onClick={() => setProfileOption('net')}>Net</Button>
                                       <Button variant="ghost" size="sm" className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'liquidity' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`} onClick={() => setProfileOption('liquidity')}>Liquidity</Button>
                                    </div>
                                 )}
                                 <span className="text-[10px] font-black text-zinc-700 uppercase tracking-[0.3em]">Precision Render</span>
                              </div>
                           </div>

                           <div className="flex-1 min-h-[600px] flex flex-col p-10 relative">
                              {mainTab === 'profile' && (
                                 <div className="w-full flex-1 flex flex-col">
                                    {!zoomedProfile.length ? (
                                       <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                          <ZapOff size={48} />
                                          <span className="text-xs font-black uppercase tracking-widest">No exposure clusters found</span>
                                       </div>
                                    ) : (
                                       <div className="h-[550px] w-full relative">
                                          <ResponsiveContainer width="100%" height="100%">
                                             {profileOption === 'nodes' ? (
                                                <BarChart data={zoomedProfile} layout="vertical" margin={{ left: 30, right: 30 }} barGap={0}>
                                                   <XAxis type="number" hide />
                                                   <YAxis dataKey="strike" type="category" width={70} tick={{ fill: '#a1a1aa', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} />
                                                   <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => {
                                                      if (!active || !payload?.length) return null;
                                                      const data = payload[0].payload;
                                                      return (
                                                         <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl">
                                                            <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike Node {data.strike}</div>
                                                            <div className="grid grid-cols-2 gap-6">
                                                               <div><div className="text-[8px] font-black text-emerald-500/80 uppercase tracking-widest mb-1">Call GEX</div><div className="text-sm font-mono font-black text-emerald-400">{fmtGex(data.call_gex)}</div></div>
                                                               <div><div className="text-[8px] font-black text-rose-500/80 uppercase tracking-widest mb-1">Put GEX</div><div className="text-sm font-mono font-black text-rose-400">{fmtGex(data.put_gex)}</div></div>
                                                            </div>
                                                         </div>
                                                      );
                                                   }} />
                                                   <Bar dataKey="call_gex" fill="#10b981" radius={[0, 4, 4, 0]} opacity={0.6} />
                                                   <Bar dataKey="put_gex" fill="#f43f5e" radius={[4, 0, 0, 4]} opacity={0.6} />
                                                   {priceLadder.map((l: any, idx) => (
                                                      <ReferenceLine key={idx} y={l.price} stroke={l.type === 'spot' ? '#10b981' : '#71717a'} strokeDasharray={l.type === 'spot' ? '0' : '4 4'} strokeWidth={l.type === 'spot' ? 2 : 1} />
                                                   ))}
                                                </BarChart>
                                             ) : profileOption === 'net' ? (
                                                <ComposedChart data={zoomedProfile} layout="vertical">
                                                   <XAxis type="number" hide />
                                                   <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} axisLine={false} />
                                                   <RechartsTooltip content={({ active, payload }) => { if (!active || !payload?.length) return null; const d = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {d.strike}</div><div className={`text-xl font-mono font-black ${d.net_gex >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtGex(d.net_gex)}</div></div>); }} />
                                                   <Bar dataKey="net_gex" radius={[4, 4, 4, 4]}>
                                                      {zoomedProfile.map((entry: any, index: number) => (
                                                         <Cell key={`cell-${index}`} fill={entry.net_gex >= 0 ? '#10b981' : '#f43f5e'} opacity={0.7} />
                                                      ))}
                                                   </Bar>
                                                </ComposedChart>
                                             ) : (
                                                <BarChart data={zoomedProfile} layout="vertical">
                                                   <XAxis type="number" hide />
                                                   <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} axisLine={false} />
                                                   <Bar dataKey="call_vol" stackId="vol" fill="#10b981" opacity={0.4} />
                                                   <Bar dataKey="put_vol" stackId="vol" fill="#f43f5e" opacity={0.4} />
                                                   <Bar dataKey="call_oi" stackId="oi" fill="#10b981" opacity={0.8} />
                                                   <Bar dataKey="put_oi" stackId="oi" fill="#f43f5e" opacity={0.8} />
                                                </BarChart>
                                             )}
                                          </ResponsiveContainer>
                                       </div>
                                    )}
                                 </div>
                              )}

                              {mainTab === 'cumulative' && (
                                 <div className="w-full flex-1 flex flex-col">
                                    <div className="h-[550px] w-full">
                                       <ResponsiveContainer width="100%" height="100%">
                                          <AreaChart data={cumulativeGex}>
                                             <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                             <XAxis dataKey="strike" stroke="#ffffff10" fontSize={11} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                             <YAxis stroke="#ffffff10" fontSize={11} tickFormatter={(v) => fmtGex(v)} width={80} />
                                             <Area type="monotone" dataKey="cumulative" stroke="#f59e0b" strokeWidth={2.5} fill="#f59e0b20" dot={false} />
                                             <ReferenceLine y={0} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="6 3" />
                                             <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" />
                                          </AreaChart>
                                       </ResponsiveContainer>
                                    </div>
                                 </div>
                              )}

                              {mainTab === 'dex' && (
                                 <div className="w-full flex-1 flex flex-col">
                                    <div className="h-[550px] w-full">
                                       <ResponsiveContainer width="100%" height="100%">
                                          <ComposedChart data={dexProfile} layout="vertical" margin={{ left: 30, right: 40 }}>
                                             <XAxis type="number" hide />
                                             <YAxis dataKey="strike" type="category" width={75} tick={{ fill: '#a1a1aa', fontSize: 12, fontWeight: 900 }} axisLine={false} />
                                             <Bar dataKey="call_dex" fill="#3b82f6" opacity={0.65} />
                                             <Bar dataKey="put_dex"  fill="#f43f5e" opacity={0.65} />
                                             <Line type="monotone" dataKey="net_dex" stroke="#a78bfa" strokeWidth={2} dot={false} />
                                             <ReferenceLine y={drillSpot} stroke="#10b981" strokeWidth={2} />
                                          </ComposedChart>
                                       </ResponsiveContainer>
                                    </div>
                                 </div>
                              )}

                              {mainTab === 'skew' && (
                                 <div className="w-full flex-1 flex flex-col">
                                    <div className="h-[550px] w-full">
                                       <ResponsiveContainer width="100%" height="100%">
                                          <ComposedChart data={skewProfile}>
                                             <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                             <XAxis dataKey="strike" stroke="#ffffff10" fontSize={10} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                             <YAxis stroke="#ffffff10" fontSize={10} tickFormatter={(v) => v.toFixed(1) + '%'} />
                                             <Area type="monotone" dataKey="call_iv" stroke="#10b981" fill="#10b98110" strokeWidth={1.5} dot={false} />
                                             <Area type="monotone" dataKey="put_iv"  stroke="#f43f5e" fill="#f43f5e10" strokeWidth={1.5} dot={false} />
                                             <Line type="monotone" dataKey="skew" stroke="#a855f7" strokeWidth={2.5} dot={false} />
                                             <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" />
                                          </ComposedChart>
                                       </ResponsiveContainer>
                                    </div>
                                 </div>
                              )}

                              {mainTab === 'history' && (
                                 <div className="w-full flex-1 flex flex-col">
                                    <div className="h-[550px] w-full relative">
                                       {!historicalTrend.length ? (
                                          <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                             <Activity size={48} />
                                             <span className="text-xs font-black uppercase tracking-widest text-center">Trend intelligence unavailable.</span>
                                          </div>
                                       ) : (
                                          <ResponsiveContainer width="100%" height="100%">
                                             <AreaChart data={historicalTrend}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                                <XAxis 
                                                  dataKey="timestamp" 
                                                  stroke="#ffffff10" 
                                                  fontSize={10} 
                                                  tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} 
                                                />
                                                <YAxis 
                                                  stroke="#ffffff10" 
                                                  fontSize={10} 
                                                  tickFormatter={(v) => fmtGex(v)} 
                                                  width={70} 
                                                />
                                                <RechartsTooltip 
                                                  content={({ active, payload }) => {
                                                    if (!active || !payload?.length) return null;
                                                    const d = payload[0].payload;
                                                    return (
                                                      <div className="bg-black/90 border border-white/10 p-4 rounded-xl backdrop-blur-3xl shadow-xl">
                                                        <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">{new Date(d.timestamp).toLocaleTimeString()}</div>
                                                        <div className="text-lg font-mono font-black text-emerald-400">{fmtGex(d.total_gex)}</div>
                                                        <div className="text-[8px] font-bold text-zinc-400 uppercase tracking-widest mt-1">Total Gamma Exposure</div>
                                                      </div>
                                                    );
                                                  }}
                                                />
                                                <Area type="monotone" dataKey="total_gex" stroke="#10b981" fill="#10b98120" strokeWidth={3} dot={false} />
                                             </AreaChart>
                                          </ResponsiveContainer>
                                       )}
                                    </div>
                                 </div>
                              )}
                           </div>
                        </Card>
                     </div>
                     
                     <div className="col-span-12 grid grid-cols-12 gap-8">
                        <div className="col-span-12 lg:col-span-5">
                           <Card className="bg-zinc-900/30 border-white/5 rounded-[3rem] p-8 h-full">
                              <div className="flex items-center gap-3 mb-8">
                                 <Target size={18} className="text-indigo-500" />
                                 <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-400">Institutional Price Map</h3>
                              </div>
                              <div className="space-y-4">
                                 {priceLadder.map((l, i) => (
                                    <div key={i} className={`p-6 rounded-[2rem] border relative overflow-hidden group transition-all duration-300 ${
                                       l.type === 'spot' ? 'bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.1)]' : 'bg-black/20 border-white/5'
                                    }`}>
                                       <div className="flex justify-between items-start relative z-10">
                                          <div className="space-y-1">
                                             <div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest">{l.label}</div>
                                             <div className="text-2xl font-mono font-black text-white">{l.price?.toFixed(2)}</div>
                                             <div className="text-[9px] font-bold text-zinc-600">{l.note}</div>
                                          </div>
                                          {l.type === 'spot' && <Crosshair className="text-emerald-500 animate-pulse" size={20} />}
                                       </div>
                                    </div>
                                 ))}
                              </div>
                           </Card>
                        </div>
                        
                        <div className="col-span-12 lg:col-span-7">
                           <Card className="bg-zinc-900/30 border-white/5 rounded-[3rem] p-10 h-full">
                              <div className="flex items-center justify-between mb-8">
                                 <div className="flex items-center gap-3">
                                    <Activity size={18} className="text-emerald-500" />
                                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-400">Liquidity Telemetry</h3>
                                 </div>
                                 <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">3% ATM Focus</div>
                              </div>
                              <div className="h-64 w-full">
                                 <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={volSummary.near}>
                                       <XAxis dataKey="strike" fontSize={9} tick={{ fill: '#52525b', fontWeight: 900 }} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                       <Bar dataKey="call_vol" fill="#10b981" opacity={0.6} />
                                       <Bar dataKey="put_vol" fill="#f43f5e" opacity={0.6} />
                                    </BarChart>
                                 </ResponsiveContainer>
                              </div>
                           </Card>
                        </div>
                     </div>
                  </div>
               </div>
            </ScrollArea>

            <div className="h-14 bg-zinc-950/80 backdrop-blur-2xl border-t border-white/5 px-8 flex items-center justify-between shrink-0 z-50">
               <div className="flex items-center gap-8">
                  <div className="flex items-center gap-3">
                     <Database size={14} className="text-emerald-500/50" />
                     <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em]">Stream: Options-Live-V6</span>
                  </div>
                  <div className="flex items-center gap-3">
                     <Timer size={14} className="text-zinc-500" />
                     <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em]">Frequency: {(refreshInterval / 1000).toFixed(0)}s</span>
                  </div>
               </div>
               <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-[8px] font-black text-zinc-600 border-white/5 uppercase">Terminal Active</Badge>
               </div>
            </div>
         </main>

         <TacticalBriefingSidebar 
           activeDetail={activeDetail} 
           ms={ms} 
           isOpen={rightSidebarOpen} 
           onToggle={() => setRightSidebarOpen(false)}
         />

         {!rightSidebarOpen && (
            <button 
               onClick={() => setRightSidebarOpen(true)}
               className="absolute right-6 top-10 z-50 p-3 bg-zinc-900 border border-white/10 rounded-xl text-emerald-500 hover:scale-110 transition-all shadow-2xl group"
               title="Expand Briefing (<<)"
            >
               <ChevronLeft size={18} className="group-hover:-translate-x-0.5 transition-transform" />
            </button>
         )}
      </div>
      
    </div>
    </TooltipProvider>
  )
}
