"use client";

import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { 
  Radar, RefreshCcw, AlertTriangle, ArrowUpRight, ArrowDownRight, 
  Activity, Crosshair, Layers, Zap, X, BarChart2, Star, StarOff, 
  ChevronRight, Target, Shield, Gauge, TrendingUp, TrendingDown,
  Info, Table as TableIcon, Hash, Timer, Droplets, Flame, Search, ShieldCheck,
  AlertOctagon, LayoutDashboard, Database, ZapOff, Play, Save
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, 
  Tooltip as RechartsTooltip, ResponsiveContainer, 
  ReferenceLine, Cell, AreaChart, Area, CartesianGrid,
  Legend, ComposedChart
} from "recharts";
import {
  Tooltip as UiTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";

// ── UTILITIES ─────────────────────────────────────────────────────────────
const fmtGex = (v: number | undefined | null) => {
  if (v == null || isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
};

const fixText = (t: any, ticker: string = "", spot: number = 0) => {
  if (!t) return "";
  const str = Array.isArray(t) ? t.join(" ") : String(t);
  return str.replaceAll("{ticker}", ticker).replaceAll("{spot}", spot?.toLocaleString());
};

const getRegimeColor = (regime: string | undefined) => {
  if (!regime) return "bg-zinc-800 text-zinc-500 border-zinc-700/50";
  const str = String(regime).toUpperCase();
  if (str.includes("POSITIVE") || str === "1") return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  if (str.includes("NEGATIVE") || str === "-1") return "bg-rose-500/10 text-rose-400 border-rose-500/20";
  return "bg-amber-500/10 text-amber-400 border-amber-500/20";
};

// ── COMPONENTS ────────────────────────────────────────────────────────────
export default function OptionsTacticalDashboard() {
  const [liveData, setLiveData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<any>(null);
  const [priorityTickers, setPriorityTickers] = useState<string[]>(['/ES', '/NQ', 'SPX', 'QQQ', 'NVDA', 'TSLA']);
  const [refreshingTickers, setRefreshingTickers] = useState<Set<string>>(new Set());
  
  const [mainTab, setMainTab] = useState<'profile' | 'history' | 'heatmap'>('profile');
  const [profileOption, setProfileOption] = useState<'nodes' | 'net' | 'liquidity'>('nodes');
  const [rightTab, setRightTab] = useState<'ladder' | 'briefing' | 'nodes'>('ladder');
  const [strikeZoomRange, setStrikeZoomRange] = useState(5); // ±5%
  
  const [activeAlert, setActiveAlert] = useState<{message: string, type: 'success'|'error'|'warning', ticker: string} | null>(null);
  const previousRegimes = useRef<Record<string, string>>({});

  // ── CORE DATA FETCH ─────────────────────────────────────────────────────
  const fetchData = async () => {
    try {
      const res = await fetch("/api/options-live");
      const json = await res.json();
      if (json.success) {
        setLiveData(json.data);
        setLastFetch(new Date(json.lastUpdated));
        
        // Regime Shift Alerts
        const marketStructure = json.data?.dailyLevels?.market_structure || [];
        marketStructure.forEach((m: any) => {
           const ticker = m.cash_ticker || m.asset;
           if (ticker && m.regime_label && previousRegimes.current[ticker] && previousRegimes.current[ticker] !== m.regime_label) {
              setActiveAlert({
                 message: `Regime shift for ${ticker}: now ${m.regime_label}`,
                 type: m.gex_regime > 0 ? 'success' : 'error',
                 ticker
              });
           }
           previousRegimes.current[ticker] = m.regime_label;
        });
      }
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  // ── INDIVIDUAL TICKER REFRESH (Tier 1) ──────────────────────────────────
  const refreshTicker = async (symbol: string) => {
    setRefreshingTickers(prev => new Set(prev).add(symbol));
    try {
      const res = await fetch(`/api/options-live?ticker=${encodeURIComponent(symbol)}`);
      const json = await res.json();
      if (json.success && json.data) {
        setLiveData((prev: any) => {
          if (!prev) return json.data;
          const next = { ...prev };
          // Merge specific ticker into pipelineState
          if (json.data.pipelineState?.tickers?.[symbol]) {
             if (!next.pipelineState) next.pipelineState = { tickers: {} };
             next.pipelineState.tickers[symbol] = json.data.pipelineState.tickers[symbol];
          }
          return next;
        });
      }
    } catch (err) {
      console.error(`Failed to refresh ${symbol}:`, err);
    } finally {
      setTimeout(() => {
        setRefreshingTickers(prev => {
          const next = new Set(prev);
          next.delete(symbol);
          return next;
        });
      }, 500);
    }
  };

  useEffect(() => {
    fetchData();
    // Tier 2: Global Refresh
    const globalInv = setInterval(fetchData, 30000);
    // Tier 1: Priority Refresh
    const priorityInv = setInterval(() => {
       priorityTickers.forEach(refreshTicker);
    }, 10000);

    return () => {
       clearInterval(globalInv);
       clearInterval(priorityInv);
    };
  }, [priorityTickers]);
  
  const fixPrice = (val: number | null | undefined, ticker?: string) => {
    if (!val) return 0;
    const isFuture = ticker?.startsWith('/') || ['ES', 'NQ', 'YM', 'RTY'].includes(ticker || "");
    const tick = isFuture ? 0.25 : 0.01;
    return Math.round(val / tick) * tick;
  };

  // ── DATA ENGINE ──
  const pipelineState: any = liveData?.pipelineState || {};
  const tickersData = useMemo(() => pipelineState.tickers ? Object.values(pipelineState.tickers) : [], [pipelineState]);
  const activeDetail = selectedTicker || (tickersData.length > 0 ? tickersData[0] : null);
  
  const profilesMap: any = liveData?.gexProfiles?.profiles || {};
  const trendsMap: any = liveData?.liveTrend?.history || {};

  // Normalization logic for futures to underlying
  // Normalization logic for futures to underlying
  const lookupTicker = useMemo(() => {
     if (!activeDetail) return "";
     // Prioritize the actual ticker to keep futures and ETFs separate for profile mapping
     const raw = activeDetail.ticker || activeDetail.cash_ticker || "";
     return raw.replace(/^\//, '');
  }, [activeDetail]);
  
  const activeProfileRaw = useMemo(() => profilesMap[lookupTicker] || [], [lookupTicker, profilesMap]);
  const activeProfile = useMemo(() => activeProfileRaw.map((p: any) => ({ ...p, strike: fixPrice(p.strike, lookupTicker) })), [activeProfileRaw, lookupTicker]);
  const activeTrendData = useMemo(() => trendsMap[lookupTicker] || [], [lookupTicker, trendsMap]);
  const ms = useMemo(() => liveData?.dailyLevels?.market_structure?.find((m: any) => m.asset === lookupTicker || m.cash_ticker === lookupTicker) || {}, [liveData, lookupTicker]);
  const drillSpot = fixPrice(activeDetail?.spot, activeDetail?.ticker);

  const zoomedProfile = useMemo(() => {
    if (activeProfile.length === 0 || drillSpot === 0) return activeProfile;
    const factor = strikeZoomRange / 100;
    const lower = drillSpot * (1 - factor);
    const upper = drillSpot * (1 + factor);
    
    let filtered = activeProfile.filter((p: any) => p.strike >= lower && p.strike <= upper);
    
    if (filtered.length > 40) {
       filtered = [...filtered]
         .sort((a,b) => Math.abs(a.strike - drillSpot) - Math.abs(b.strike - drillSpot))
         .slice(0, 40)
         .sort((a,b) => a.strike - b.strike);
    }
    return filtered.length > 3 ? filtered : activeProfile;
  }, [activeProfile, drillSpot, strikeZoomRange]);

  const topNodes = useMemo(() => {
     if (!activeProfile.length) return { calls: [], puts: [] };
     // Pick top call walls
     const bestCalls = [...activeProfile].sort((a,b) => b.call_gex - a.call_gex).slice(0, 5);
     
     // Pick top put walls, but avoid those that are ridiculously far from spot (outliers)
     const putsNearSpot = activeProfile.filter((p: any) => p.strike > drillSpot * 0.7 && p.strike < drillSpot * 1.3);
     const bestPuts = [...(putsNearSpot.length > 5 ? putsNearSpot : activeProfile)]
        .sort((a,b) => a.put_gex - b.put_gex)
        .slice(0, 5);
        
     return { calls: bestCalls, puts: bestPuts };
  }, [activeProfile, drillSpot]);

  const priceLadder = useMemo(() => {
    if (!activeDetail) return [];
    
    const base = [
      { price: fixPrice(activeDetail.spot, activeDetail.ticker), label: "Live Price", type: "spot", note: "Current spot tracking" },
      { price: fixPrice(activeDetail.gamma_magnet, activeDetail.ticker), label: "Gamma Magnet", type: "magnet", note: "Attracts price, high liquidity grab" },
      { price: fixPrice(activeDetail.zero_gamma || activeDetail.gamma_flip_upper, activeDetail.ticker), label: "Gamma Flip", type: "regime", note: "Net gamma polarity shifts here" },
    ];
    
    // Add top 3 call walls
    topNodes.calls.slice(0, 3).forEach((n: any, idx: number) => {
        base.push({ price: n.strike, label: `Call Wall ${idx + 1}`, type: "resistance", note: "High call OI, resistance expected" });
    });
    
    // Add top 3 put walls
    topNodes.puts.slice(0, 3).forEach((n: any, idx: number) => {
        base.push({ price: n.strike, label: `Put Wall ${idx + 1}`, type: "support", note: "High put OI, support expected" });
    });

    return base.filter(l => l.price && l.price > 0).sort((a,b) => b.price - a.price);
  }, [activeDetail, topNodes]);

  if (loading) return (
     <div className="h-screen w-full bg-black flex flex-col items-center justify-center gap-6">
        <Activity className="text-emerald-500 animate-spin h-10 w-10" />
        <div className="text-[10px] font-black uppercase tracking-[0.4em] text-emerald-500/50">Tactical System Loading...</div>
     </div>
  );

  return (
    <TooltipProvider>
    <div className="h-screen w-full bg-black text-white selection:bg-emerald-500/30 overflow-hidden flex font-sans">
      
      {/* ── Sidebar ── */}
      <aside className="w-96 border-r border-white/5 flex flex-col bg-zinc-950/50 backdrop-blur-3xl shrink-0">
         <div className="p-8 border-b border-white/5 bg-black/40">
            <div className="flex items-center justify-between mb-8 group">
               <div className="flex items-center gap-4">
                  <div className="h-10 w-10 bg-emerald-500 rounded-2xl flex items-center justify-center shadow-[0_0_30px_rgba(16,185,129,0.3)] rotate-3 group-hover:rotate-0 transition-all">
                     <Radar className="text-black" size={20} />
                  </div>
                  <div>
                     <h1 className="text-sm font-black tracking-widest uppercase">Tactical.Live</h1>
                     <div className="flex items-center gap-2 mt-0.5">
                        <div className="h-1 w-1 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-[8px] font-bold text-zinc-500 uppercase tracking-widest">{lastFetch?.toLocaleTimeString()}</span>
                     </div>
                  </div>
               </div>
            </div>

            <div className="relative group">
               <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-600 group-focus-within:text-emerald-500 transition-colors" size={14} />
               <input 
                  placeholder="EXECUTIVE SEARCH..." 
                  className="w-full bg-zinc-900/50 border border-white/5 rounded-2xl py-4 pl-12 pr-6 text-[10px] font-black uppercase tracking-widest focus:outline-none focus:border-emerald-500/30 transition-all placeholder:text-zinc-700"
               />
            </div>
         </div>

         <ScrollArea className="flex-1 p-4 bg-gradient-to-b from-black/20 to-transparent">
            <div className="space-y-3">
               {tickersData.map((t: any) => {
                  const m = liveData?.dailyLevels?.market_structure?.find((ms: any) => (ms.cash_ticker || ms.asset) === (t.cash_ticker || t.ticker)?.replace(/^\//,'')) || {};
                  const active = activeDetail?.ticker === t.ticker;
                  const regimeColor = getRegimeColor(m.regime_label);
                  const isRefreshing = refreshingTickers.has(t.ticker);
                  
                  return (
                     <div 
                        key={t.ticker}
                        onClick={() => setSelectedTicker(t)}
                        className={`group cursor-pointer rounded-3xl p-5 border transition-all duration-300 relative overflow-hidden ${
                           active ? 'bg-zinc-900 border-white/10 shadow-2xl scale-[1.02]' : 'bg-transparent border-transparent hover:bg-white/5'
                        }`}
                     >
                        {active && <div className={`absolute inset-0 opacity-10 bg-gradient-to-br ${m.gex_regime > 0 ? 'from-emerald-500' : 'from-rose-500'} to-transparent`} />}
                        
                        <div className="flex items-center justify-between mb-2 relative z-10">
                           <div className="flex items-center gap-3">
                              <span className="text-lg font-black tracking-tighter">{t.ticker}</span>
                              <Badge className={`text-[8px] font-black px-1.5 py-0 rounded-sm border-0 ${regimeColor}`}>{m.regime_label || 'NEUTRAL'}</Badge>
                           </div>
                           <div className="flex items-center gap-2">
                              <Button 
                                 size="icon" 
                                 variant="ghost" 
                                 className="h-6 w-6 rounded-lg bg-white/5 opacity-0 group-hover:opacity-100 transition-all hover:bg-emerald-500/10 hover:text-emerald-400"
                                 onClick={(e) => { e.stopPropagation(); refreshTicker(t.ticker); }}
                              >
                                 <RefreshCcw size={10} className={isRefreshing ? 'animate-spin text-emerald-500' : ''} />
                              </Button>
                              <div className={`text-sm font-mono font-black ${t.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                 {t.price?.toLocaleString()}
                              </div>
                           </div>
                        </div>
                        
                        <div className="flex items-center justify-between relative z-10">
                           <div className="flex items-center gap-2">
                              <span className="text-[9px] font-black text-zinc-500 tracking-widest uppercase">GEX Exposure</span>
                           </div>
                           <div className="text-[10px] font-black text-zinc-300">{fmtGex(t.total_gex)}</div>
                        </div>
                        
                        <div className="mt-3 h-1 bg-white/5 rounded-full overflow-hidden relative z-10">
                           <div 
                              className={`h-full opacity-50 transition-all duration-1000 ${t.total_gex >= 0 ? 'bg-emerald-500' : 'bg-rose-500'}`}
                              style={{ width: `${Math.min(100, (Math.abs(t.total_gex) / 1e8) * 100)}%` }}
                           />
                        </div>
                     </div>
                  );
               })}
            </div>
         </ScrollArea>
      </aside>

      {/* ── Main Dashboard ── */}
      <div className="flex-1 flex flex-col relative bg-zinc-950 overflow-hidden">
         
         {/* Top Focus Bar */}
         <div className="h-28 border-b border-white/5 flex items-center justify-between px-10 bg-black/40 backdrop-blur-md shrink-0">
            <div className="flex items-center gap-10">
               <div>
                  <div className="flex items-center gap-2 text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-1.5">
                     <Crosshair className="text-emerald-500" size={10} /> Active Target
                  </div>
                  <h2 className="text-3xl font-black tracking-tighter">{activeDetail?.ticker} <span className="text-zinc-700 mx-2">/</span> <span className="text-emerald-400">{activeDetail?.price?.toLocaleString()}</span></h2>
               </div>
               
               <div className="h-10 w-[1px] bg-white/5" />
               
               <div className="flex items-center gap-8">
                  <div className="space-y-1">
                     <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Implied Vol</span>
                     <div className="text-xs font-mono font-black text-zinc-300">{activeDetail?.iv_current ? activeDetail.iv_current.toFixed(2) + "%" : "N/A"}</div>
                  </div>
                  <div className="space-y-1">
                     <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Vol Change</span>
                     <div className={`text-xs font-mono font-black ${activeDetail?.iv_change >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        {activeDetail?.iv_change ? (activeDetail.iv_change >= 0 ? "+" : "") + activeDetail.iv_change.toFixed(2) + "%" : "0.00%"}
                     </div>
                  </div>
               </div>
            </div>

            <div className="flex items-center gap-4">
               <Button size="sm" variant="outline" className="h-11 px-6 rounded-2xl border-white/5 bg-white/5 text-[10px] font-black uppercase tracking-widest hover:bg-white/10" onClick={fetchData}>
                  <RefreshCcw size={14} className={`mr-2 ${refreshingTickers.size > 0 ? 'animate-spin' : ''}`} /> Sync Nodes
               </Button>
            </div>
         </div>

         <ScrollArea className="flex-1">
            <div className="p-10 pb-32">
               
               {activeAlert && (
                  <div className={`mb-10 p-6 rounded-3xl border flex items-center justify-between border-white/5 animate-in fade-in slide-in-from-top-4 duration-500 ${activeAlert.type === 'success' ? 'bg-emerald-500/5' : 'bg-rose-500/5'}`}>
                     <div className="flex items-center gap-4">
                        <AlertOctagon className={activeAlert.type === 'success' ? 'text-emerald-500' : 'text-rose-500'} size={24} />
                        <div>
                           <p className="text-xs font-black uppercase tracking-widest opacity-50 mb-0.5">Critical System Sync</p>
                           <p className="text-sm font-black tracking-tight">{activeAlert.message}</p>
                        </div>
                     </div>
                     <X className="cursor-pointer opacity-20 hover:opacity-100 transition-opacity" size={18} onClick={() => setActiveAlert(null)} />
                  </div>
               )}

               <div className="grid grid-cols-12 gap-8">
                  
                  {/* Left Column: Intelligence */}
                  <div className="col-span-8 space-y-8">
                     
                     {/* Stats Hero */}
                     <div className="grid grid-cols-6 gap-4">
                        {[
                          { label: "Call Wall", val: activeDetail?.call_wall, icon: <ArrowUpRight className="text-emerald-500" />, sub: "Resistance", tip: "Highest concentration of Positive Gamma exposure.", isGex: false },
                          { label: "Put Wall", val: activeDetail?.put_wall, icon: <ArrowDownRight className="text-rose-500" />, sub: "Support", tip: "Highest concentration of Negative Gamma exposure.", isGex: false },
                          { label: "Gamma Flip", val: activeDetail?.zero_gamma || activeDetail?.gamma_flip_upper, icon: <Gauge className="text-amber-500" />, sub: "Regime Shift", tip: "Price level where net dealer gamma transitions from positive to negative.", isGex: false },
                          { label: "Gamma Magnet", val: activeDetail?.gamma_magnet, icon: <Target className="text-indigo-500" />, sub: "Liquidity Node", tip: "A significant strike point that acts as a focal point for price attraction.", isGex: false },
                          { label: "Net Vanna", val: activeDetail?.net_vanna_exposure, icon: <Layers className="text-blue-500" />, sub: "Delta Exposure", tip: "Dealer exposure relative to changes in implied volatility. Positive means dealers buy into rallies.", isGex: true },
                          { label: "Pin Strike", val: activeDetail?.pin_strike, icon: <Hash className="text-purple-500" />, sub: "Expiration Target", tip: `Highest probability strike for price to pin at expiration. Odds: ${(activeDetail?.pin_odds || 0).toFixed(1)}%`, isGex: false },
                        ].map((item, idx) => (
                          <UiTooltip key={idx}>
                             <TooltipTrigger asChild>
                               <Card className="bg-gradient-to-br from-zinc-900 to-black border-white/5 rounded-[2.5rem] p-5 hover:border-emerald-500/20 transition-all duration-500 cursor-help group border">
                                 <div className="flex justify-between items-start mb-4">
                                    <div className="p-3 bg-white/5 rounded-2xl group-hover:bg-emerald-500/10 transition-colors">
                                       {item.icon}
                                    </div>
                                    <span className="text-[9px] font-black text-zinc-700 uppercase tracking-widest text-right leading-none w-1/2">{item.sub}</span>
                                 </div>
                                 <div className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em] mb-1">{item.label}</div>
                                 <div className="text-xl font-mono font-black tracking-tighter">
                                    {item.val ? (item.isGex ? fmtGex(item.val) : item.val.toLocaleString(undefined, {minimumFractionDigits: 1})) : "—"}
                                 </div>
                               </Card>
                             </TooltipTrigger>
                             <TooltipContent className="bg-zinc-900 border-zinc-700 p-4 max-w-[250px] rounded-2xl">
                               <p className="text-xs font-semibold leading-relaxed tracking-tight text-white">{item.tip}</p>
                             </TooltipContent>
                          </UiTooltip>
                        ))}
                     </div>

                     {/* Main Chart Section */}
                     <Card className="bg-black/40 border-white/5 rounded-[3rem] overflow-hidden backdrop-blur-xl border flex flex-col min-h-[600px] basis-[600px]">
                        <div className="p-10 border-b border-white/5 flex items-center justify-between bg-black/40">
                           <Tabs value={mainTab} onValueChange={(v: any) => setMainTab(v)} className="bg-zinc-900/50 p-1.5 rounded-2xl">
                              <TabsList className="bg-transparent gap-2 h-auto p-0">
                                 <TabsTrigger value="profile" className="rounded-xl px-8 py-3 text-[10px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-emerald-400">GEX Profile</TabsTrigger>
                                 <TabsTrigger value="history" className="rounded-xl px-8 py-3 text-[10px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-emerald-400">GEX History</TabsTrigger>
                              </TabsList>
                           </Tabs>
                           <div className="flex items-center gap-6">
                              {mainTab === 'profile' && (
                                 <div className="flex bg-zinc-900/80 p-1 rounded-xl border border-white/5">
                                    <Button 
                                       variant="ghost" 
                                       size="sm" 
                                       className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'nodes' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
                                       onClick={() => setProfileOption('nodes')}
                                    >Nodes</Button>
                                    <Button 
                                       variant="ghost" 
                                       size="sm" 
                                       className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'net' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
                                       onClick={() => setProfileOption('net')}
                                    >Net</Button>
                                    <Button 
                                       variant="ghost" 
                                       size="sm" 
                                       className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === 'liquidity' ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
                                       onClick={() => setProfileOption('liquidity')}
                                    >Liquidity</Button>
                                 </div>
                              )}
                              <span className="text-[10px] font-black text-zinc-700 uppercase tracking-[0.3em]">Precision Render</span>
                           </div>
                        </div>

                        <div className="flex-1 min-h-[500px] flex flex-col p-10 relative">
                           {mainTab === 'profile' ? (
                              <div className="w-full flex-1 flex flex-col">
                                 {!zoomedProfile.length ? (
                                    <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                       <ZapOff size={48} />
                                       <span className="text-xs font-black uppercase tracking-widest">No exposure clusters found</span>
                                    </div>
                                 ) : (
                                 <div className="h-[450px] w-full relative">
                                    <ResponsiveContainer width="100%" height="100%">
                                       {profileOption === 'nodes' ? (
                                          <BarChart 
                                             data={zoomedProfile} 
                                             layout="vertical"
                                             margin={{ left: 30, right: 30, top: 0, bottom: 0 }}
                                             barGap={0}
                                          >
                                             <XAxis type="number" hide />
                                             <YAxis dataKey="strike" type="category" width={70} tick={{ fill: '#a1a1aa', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={3} />
                                             <RechartsTooltip 
                                                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                                content={({ active, payload }) => {
                                                   if (!active || !payload?.length) return null;
                                                   const data = payload[0].payload;
                                                   return (
                                                      <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl">
                                                         <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike Node {data.strike}</div>
                                                          <div className="grid grid-cols-2 gap-6">
                                                             <div>
                                                                <div className="text-[8px] font-black text-emerald-500/80 uppercase tracking-widest mb-1">Call GEX</div>
                                                                <div className="text-sm font-mono font-black text-emerald-400">{fmtGex(data.call_gex)}</div>
                                                             </div>
                                                             <div>
                                                                <div className="text-[8px] font-black text-rose-500/80 uppercase tracking-widest mb-1">Put GEX</div>
                                                                <div className="text-sm font-mono font-black text-rose-400">{fmtGex(data.put_gex)}</div>
                                                             </div>
                                                          </div>
                                                      </div>
                                                   );
                                                }}
                                             />
                                             <Bar dataKey="call_gex" fill="#10b981" radius={[0, 4, 4, 0]} opacity={0.6} />
                                             <Bar dataKey="put_gex" fill="#f43f5e" radius={[4, 0, 0, 4]} opacity={0.6} />
                                             
                                             {priceLadder.map((l: any, idx) => (
                                                <ReferenceLine 
                                                   key={idx} 
                                                   y={l.price} 
                                                   stroke={
                                                      l.type === 'spot' ? '#10b981' : 
                                                      l.type === 'magnet' ? '#6366f1' : 
                                                      l.type === 'resistance' ? '#f43f5e' : 
                                                      l.type === 'support' ? '#10b981' : '#71717a'
                                                   } 
                                                   strokeDasharray={l.type === 'spot' ? '0' : '4 4'}
                                                   strokeWidth={l.type === 'spot' ? 2 : 1}
                                                   label={{ 
                                                      position: 'right', 
                                                      value: l.label, 
                                                      fill: '#ffffff', 
                                                      fontSize: 11, 
                                                      fontWeight: '900',
                                                      dx: 10
                                                   }} 
                                                />
                                             ))}
                                          </BarChart>
                                       ) : profileOption === 'net' ? (
                                          <ComposedChart 
                                             data={zoomedProfile} 
                                             layout="vertical"
                                             margin={{ left: 30, right: 30, top: 0, bottom: 0 }}
                                          >
                                             <XAxis type="number" hide />
                                             <YAxis 
                                                dataKey="strike" 
                                                type="category" 
                                                width={80} 
                                                tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} 
                                                tickLine={false} 
                                                axisLine={false} 
                                                tickFormatter={(v) => Math.round(v).toLocaleString()}
                                             />
                                             <RechartsTooltip 
                                                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                                content={({ active, payload }) => {
                                                   if (!active || !payload?.length) return null;
                                                   const data = payload[0].payload;
                                                   return (
                                                      <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl">
                                                         <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {data.strike}</div>
                                                         <div className="text-[8px] font-black text-white/50 uppercase tracking-widest mb-1">Net Exposure</div>
                                                         <div className={`text-xl font-mono font-black ${data.net_gex >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                            {fmtGex(data.net_gex)}
                                                         </div>
                                                      </div>
                                                   );
                                                }}
                                             />
                                             <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                                             <Bar dataKey="net_gex" radius={[4, 4, 4, 4]}>
                                                {zoomedProfile.map((entry: any, index: number) => (
                                                   <Cell key={`cell-${index}`} fill={entry.net_gex >= 0 ? '#10b981' : '#f43f5e'} opacity={0.7} />
                                                ))}
                                             </Bar>
                                             {priceLadder.map((l: any, idx) => (
                                                <ReferenceLine 
                                                   key={idx} 
                                                   y={l.price} 
                                                   stroke={l.type === 'spot' ? '#10b981' : '#38bdf8'} 
                                                   strokeDasharray="4 4" 
                                                   label={{ position: 'right', value: l.label, fill: '#ffffff', fontSize: 10, fontWeight: '900', dx: 10 }}
                                                />
                                             ))}
                                          </ComposedChart>
                                       ) : (
                                          <BarChart 
                                             data={zoomedProfile} 
                                             layout="vertical"
                                             margin={{ left: 30, right: 30, top: 0, bottom: 0 }}
                                          >
                                             <XAxis type="number" hide />
                                             <YAxis 
                                                dataKey="strike" 
                                                type="category" 
                                                width={80} 
                                                tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} 
                                                tickLine={false} 
                                                axisLine={false} 
                                                tickFormatter={(v) => Math.round(v).toLocaleString()}
                                             />
                                             <RechartsTooltip 
                                                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                                content={({ active, payload }) => {
                                                   if (!active || !payload?.length) return null;
                                                   const data = payload[0].payload;
                                                   return (
                                                      <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl">
                                                         <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {data.strike} | Liquidity</div>
                                                         <div className="grid grid-cols-2 gap-4">
                                                            <div>
                                                               <div className="text-[8px] font-black text-zinc-400 uppercase mb-1">Volume</div>
                                                               <div className="text-sm font-mono font-black">{data.call_vol + data.put_vol}</div>
                                                            </div>
                                                            <div>
                                                               <div className="text-[8px] font-black text-zinc-400 uppercase mb-1">Open Int</div>
                                                               <div className="text-sm font-mono font-black">{data.call_oi + data.put_oi}</div>
                                                            </div>
                                                         </div>
                                                      </div>
                                                   );
                                                }}
                                             />
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
                           ) : mainTab === 'history' ? (
                              <div className="w-full flex-1 flex flex-col">
                                 {!activeTrendData.length ? (
                                    <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                       <Activity size={48} />
                                       <span className="text-xs font-black uppercase tracking-widest text-center">Trend intelligence unavailable.<br/>Awaiting market telemetry...</span>
                                    </div>
                                 ) : (
                                 <div className="h-[450px] w-full relative">
                                    <ResponsiveContainer width="100%" height="100%">
                                       <AreaChart data={activeTrendData}>
                                          <defs>
                                             <linearGradient id="trendGex" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                             </linearGradient>
                                          </defs>
                                          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                          <XAxis dataKey="timestamp" hide />
                                          <YAxis hide domain={['auto', 'auto']} />
                                          <RechartsTooltip 
                                             content={({ active, payload }) => {
                                                if (!active || !payload?.length) return null;
                                                return (
                                                   <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl">
                                                      <div className="text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-1">Total Net GEX</div>
                                                      <div className="text-xl font-mono font-black">{fmtGex(payload[0].value as number)}</div>
                                                      <div className="text-[8px] font-black text-zinc-500 uppercase tracking-widest mt-2">{new Date(payload[0].payload.timestamp).toLocaleTimeString()}</div>
                                                   </div>
                                                );
                                             }}
                                          />
                                          <Area type="monotone" dataKey="total_gex" stroke="#10b981" fillOpacity={1} fill="url(#trendGex)" strokeWidth={3} />
                                       </AreaChart>
                                    </ResponsiveContainer>
                                 </div>
                                 )}
                              </div>
                           ) : null}
                        </div>
                     </Card>

                     {/* Tactical Narrative Section */}
                     <Card className="bg-zinc-950 border-white/5 rounded-[2.5rem] overflow-hidden border p-10">
                        <div className="flex items-center justify-between mb-8">
                           <div className="flex items-center gap-3">
                              <div className="h-8 w-8 bg-emerald-500/10 rounded-xl flex items-center justify-center">
                                 <Info className="text-emerald-500" size={16} />
                              </div>
                              <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-400">Tactical Briefing</h3>
                           </div>
                           <Badge className="bg-emerald-500/10 text-emerald-500 border-zinc-800 text-[8px] font-black px-3 py-1 uppercase">Live Stream</Badge>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                           <div className="space-y-6">
                              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Macro Thesis</div>
                              <p className="text-lg font-bold text-zinc-100 leading-relaxed border-l-4 border-emerald-500 pl-8 py-2 bg-emerald-500/5 rounded-r-3xl pr-6 italic">
                                 {fixText(Array.isArray(ms.coach_note) ? ms.coach_note[0] : "Initializing narrative intelligence...", activeDetail?.ticker, activeDetail?.spot)}
                              </p>
                           </div>
                           
                           <div className="space-y-6">
                              <div className="flex items-center justify-between">
                                 <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Execution Directives</div>
                                 <ShieldCheck size={14} className="text-zinc-600" />
                              </div>
                              <div className="space-y-4">
                                 {(Array.isArray(ms.coach_note) ? ms.coach_note.slice(1, 4) : ["Awaiting high-confidence signals..."]).map((note: string, idx: number) => (
                                    <div key={idx} className="flex gap-4 p-5 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-emerald-500/20 transition-all group">
                                       <div className="text-emerald-500 font-black text-[10px] flex shrink-0 mt-0.5">{String(idx+1).padStart(2,'0')}</div>
                                       <p className="text-[11px] font-bold text-zinc-300 leading-relaxed group-hover:text-white transition-colors">{fixText(note, lookupTicker, drillSpot)}</p>
                                    </div>
                                 ))}
                              </div>
                           </div>
                        </div>
                     </Card>
                  </div>

                  {/* Right Column: Execution */}
                  <div className="col-span-4 h-full flex flex-col gap-8">
                     <Card className="bg-black/40 border-white/5 rounded-[3rem] overflow-hidden backdrop-blur-xl border flex flex-col flex-1">
                        <Tabs value={rightTab} onValueChange={(v: any) => setRightTab(v)} className="flex-1 flex flex-col">
                           <div className="p-2 border-b border-white/5">
                              <TabsList className="w-full bg-zinc-900/50 h-16 p-2 rounded-3xl gap-2">
                                 <TabsTrigger value="ladder" className="flex-1 text-[10px] font-black uppercase tracking-widest rounded-2xl data-[state=active]:bg-black">Price Map</TabsTrigger>
                                 <TabsTrigger value="briefing" className="flex-1 text-[10px] font-black uppercase tracking-widest rounded-2xl data-[state=active]:bg-black">Briefing</TabsTrigger>
                                 <TabsTrigger value="nodes" className="flex-1 text-[10px] font-black uppercase tracking-widest rounded-2xl data-[state=active]:bg-black">Nodes</TabsTrigger>
                              </TabsList>
                           </div>

                           <TabsContent value="ladder" className="flex-1 m-0">
                              <ScrollArea className="h-full px-8 py-6">
                                 <div className="space-y-4">
                                    {priceLadder.map((l, i) => (
                                       <div key={i} className={`p-6 rounded-[2rem] border relative overflow-hidden group transition-all duration-300 ${
                                          l.type === 'spot' ? 'bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.1)]' : 
                                          l.type === 'magnet' ? 'bg-indigo-500/10 border-indigo-500/20 shadow-[0_0_20px_rgba(99,102,241,0.1)]' :
                                          l.type === 'resistance' ? 'bg-rose-500/10 border-rose-500/20 shadow-[0_0_20px_rgba(244,63,94,0.1)]' :
                                          'bg-emerald-500/5 border-emerald-500/10'
                                       }`}>
                                          <div className="flex justify-between items-start relative z-10">
                                             <div className="space-y-2">
                                                <div className="flex items-center gap-2">
                                                   <div className={`w-1.5 h-1.5 rounded-full ${
                                                      l.type === 'spot' ? 'bg-emerald-500 animate-pulse' :
                                                      l.type === 'magnet' ? 'bg-indigo-500' :
                                                      l.type === 'resistance' ? 'bg-rose-500' : 'bg-emerald-400'
                                                   }`} />
                                                   <div className="text-[9px] font-black text-zinc-400 tracking-[0.2em] uppercase">{l.label}</div>
                                                </div>
                                                <div className="text-2xl font-mono font-black tracking-tighter text-white">
                                                   {l.price ? (Number.isInteger(l.price) ? l.price : l.price.toFixed(2)) : "—"}
                                                </div>
                                                <div className="text-[10px] font-bold text-zinc-500 leading-relaxed max-w-[200px]">
                                                   <span className="text-zinc-400 font-black uppercase text-[8px] tracking-widest block mb-1">Trade Action:</span>
                                                   {l.note}
                                                </div>
                                             </div>
                                             {l.type === 'spot' ? (
                                                <Crosshair className="text-emerald-500 animate-pulse" size={20} />
                                             ) : l.type === 'magnet' ? (
                                                <Target className="text-indigo-500" size={20} />
                                             ) : l.type === 'resistance' ? (
                                                <ArrowUpRight className="text-rose-500" size={20} />
                                             ) : (
                                                <ArrowDownRight className="text-emerald-500" size={20} />
                                             )}
                                          </div>
                                       </div>
                                    ))}
                                 </div>
                              </ScrollArea>
                           </TabsContent>

                           <TabsContent value="briefing" className="flex-1 m-0">
                              <ScrollArea className="h-full px-10 py-6">
                                 <div className="space-y-10">
                                    <div className="prose prose-invert prose-xs max-w-none">
                                       <div className="flex items-center gap-2 mb-4">
                                          <Info size={14} className="text-zinc-500" />
                                          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500">Tactical Focus</h3>
                                       </div>
                                       <p className="text-zinc-400 leading-relaxed text-sm italic border-l-2 border-emerald-500/40 pl-6 bg-emerald-500/5 py-6 rounded-r-3xl">
                                          {fixText(Array.isArray(ms.coach_note) ? ms.coach_note[0] : "System warming up. Monitoring cluster formation...", activeDetail?.ticker, activeDetail?.spot)}
                                       </p>
                                    </div>

                                    <div className="space-y-5">
                                       <div className="flex items-center gap-2 mb-2">
                                          <ShieldCheck size={14} className="text-zinc-500" />
                                          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500">Execution Directives</h3>
                                       </div>
                                       {(Array.isArray(ms.coach_note) ? ms.coach_note : ["No active narrative. Observation mode active."]).map((note: string, idx: number) => (
                                          <div key={idx} className="flex gap-5 p-6 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-emerald-500/20 transition-all group">
                                             <div className="text-emerald-500 font-black text-xs group-hover:scale-125 transition-transform">{String(idx+1).padStart(2,'0')}</div>
                                             <p className="text-xs font-bold text-zinc-300 leading-relaxed group-hover:text-white transition-colors">{fixText(note, lookupTicker, drillSpot)}</p>
                                          </div>
                                       ))}
                                    </div>
                                 </div>
                              </ScrollArea>
                           </TabsContent>

                           <TabsContent value="nodes" className="flex-1 m-0">
                              <ScrollArea className="h-full px-10 py-8">
                                 <div className="space-y-12">
                                    <div>
                                       <h3 className="text-xs font-black uppercase tracking-[0.3em] text-emerald-500/50 mb-6 px-4">Top Liquid Calls</h3>
                                       <div className="space-y-3">
                                          {topNodes.calls.map((n: any, i: number) => (
                                             <div key={i} className="flex items-center justify-between p-5 rounded-2xl bg-emerald-500/[0.03] border border-emerald-500/10">
                                                <div className="text-lg font-black font-mono">{n.strike}</div>
                                                <div className="text-right">
                                                   <div className="text-sm font-black text-emerald-400">{fmtGex(n.call_gex)}</div>
                                                   <div className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Dealer Long</div>
                                                </div>
                                             </div>
                                          ))}
                                       </div>
                                    </div>

                                    <div>
                                       <h3 className="text-xs font-black uppercase tracking-[0.3em] text-rose-500/50 mb-6 px-4">Top Liquid Puts</h3>
                                       <div className="space-y-3">
                                          {topNodes.puts.map((n: any, i: number) => (
                                             <div key={i} className="flex items-center justify-between p-5 rounded-2xl bg-rose-500/[0.03] border border-rose-500/10">
                                                <div className="text-lg font-black font-mono">{n.strike}</div>
                                                <div className="text-right">
                                                   <div className="text-sm font-black text-rose-400">{fmtGex(n.put_gex)}</div>
                                                   <div className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Dealer Short</div>
                                                </div>
                                             </div>
                                          ))}
                                       </div>
                                    </div>
                                 </div>
                              </ScrollArea>
                           </TabsContent>
                        </Tabs>
                     </Card>
                  </div>
               </div>
            </div>
         </ScrollArea>

         {/* Footer Status */}
         <div className="absolute bottom-0 left-0 right-0 h-14 bg-black/60 backdrop-blur-2xl border-t border-white/5 px-10 flex items-center justify-between z-20">
            <div className="flex items-center gap-6">
               <div className="flex items-center gap-2">
                  <Database size={12} className="text-zinc-600" />
                  <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Stream: Options-Live-v6</span>
               </div>
               <div className="flex items-center gap-2">
                  <Timer size={12} className="text-zinc-600" />
                  <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Frequency: 15s</span>
               </div>
            </div>
            <div className="flex items-center gap-4 bg-zinc-900 px-6 py-2.5 rounded-2xl border border-white/5">
                <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest">Strike Expansion:</span>
                <Slider 
                   value={[strikeZoomRange]} 
                   onValueChange={(v) => setStrikeZoomRange(v[0])} 
                   max={20} 
                   min={1} 
                   step={1} 
                   className="w-32" 
                />
                <span className="text-[10px] font-black w-8 text-right">{strikeZoomRange}%</span>
            </div>
         </div>
      </div>
    </div>
    </TooltipProvider>
  );
}
