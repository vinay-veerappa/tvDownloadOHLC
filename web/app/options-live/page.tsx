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
import { Maximize2, Minimize2, ExternalLink } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Dialog, DialogContent, DialogTrigger, DialogHeader, DialogTitle 
} from "@/components/ui/dialog";
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, 
  Tooltip as RechartsTooltip, ResponsiveContainer, 
  ReferenceLine, Cell, AreaChart, Area, CartesianGrid,
  Legend, ComposedChart, PieChart, Pie, RadarChart, Radar as RechartsRadar
} from "recharts";
import {
  Tooltip as UiTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";
import { VolatilitySkewChart } from "@/components/chart/VolatilitySkewChart";
import { L2Heatmap } from "@/components/chart/L2Heatmap";

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
  
  const [mainTab, setMainTab] = useState<'profile' | 'history' | 'dex' | 'skew' | 'cumulative' | 'volsummary' | 'fearpremium' | 'bookmap'>('profile');
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
  const profilesMap: any = liveData?.gexProfiles?.profiles || {};
  const trendsMap: any = liveData?.liveTrend?.history || {};
  const pipelineState: any = liveData?.pipelineState || {};
  const tickersData = useMemo(() => pipelineState.tickers ? Object.values(pipelineState.tickers) : [], [pipelineState]);
  const activeDetailRaw = selectedTicker || (tickersData.length > 0 ? tickersData[0] : null);

  const activeTrendData = useMemo(() => {
    if (!activeDetailRaw) return [];
    const ticker = (activeDetailRaw as any).ticker || "";
    const underlying = ticker.replace(/^\//, '');
    return trendsMap[underlying] || [];
  }, [activeDetailRaw, trendsMap]);

  const activeDetail = useMemo(() => {
     if (!activeDetailRaw) return null;
     const ticker = (activeDetailRaw as any).ticker || "";
     const underlying = ticker.replace(/^\//, '');

     // Initialize with raw values
     let maxPain = activeDetailRaw.max_pain;
     let callCentroid = activeDetailRaw.call_centroid;
     let putCentroid = activeDetailRaw.put_centroid;
     
     // 1. Fallback: Find max pain from dailyLevels if missing
     if (!maxPain && liveData?.dailyLevels?.levels) {
         const levels = liveData.dailyLevels.levels.filter((l: any) => l.asset === underlying || l.cash_ticker === underlying);
         maxPain = levels.find((l: any) => l.type === 'Max Pain')?.level;
     }

     // 2. Fallback: Compute Centroids from profiles if missing
     if ((!callCentroid || !putCentroid) && liveData?.gexProfiles?.profiles) {
         const profile = liveData.gexProfiles.profiles[underlying] || [];
         if (profile.length > 0) {
             let callGammaSum = 0, callGammaProd = 0;
             let putGammaSum = 0, putGammaProd = 0;
             profile.forEach((p: any) => {
                 if (p.call_gex > 0) {
                     callGammaSum += p.call_gex;
                     callGammaProd += p.strike * p.call_gex;
                 }
                 if (p.put_gex < 0) {
                     putGammaSum += Math.abs(p.put_gex);
                     putGammaProd += p.strike * Math.abs(p.put_gex);
                 }
             });
             if (!callCentroid && callGammaSum > 0) callCentroid = callGammaProd / callGammaSum;
             if (!putCentroid && putGammaSum > 0) putCentroid = putGammaProd / putGammaSum;
         }
     }

     // iv_current: atm_iv from backend is decimal (e.g. 0.20 = 20%)
     const ivCurrent = activeDetailRaw.atm_iv != null ? +(activeDetailRaw.atm_iv * 100).toFixed(2) : null;

     // Calculate Daily Shift (Cumulative) if history is available
     let dailyIvChange = (activeDetailRaw.iv_change || 0) * 100;
     if (activeTrendData && activeTrendData.length > 0) {
         const firstIv = activeTrendData.find((d: any) => d.atm_iv != null)?.atm_iv;
         if (firstIv != null && activeDetailRaw.atm_iv != null) {
             dailyIvChange = (activeDetailRaw.atm_iv - firstIv) * 100;
         }
     }

     return {
        ...(activeDetailRaw as any),
        spot: fixPrice((activeDetailRaw as any).spot, ticker),
        put_wall: fixPrice((activeDetailRaw as any).put_wall, ticker),
        call_wall: fixPrice((activeDetailRaw as any).call_wall, ticker),
        gamma_flip_upper: fixPrice((activeDetailRaw as any).zero_gamma || (activeDetailRaw as any).gamma_flip_upper, ticker),
        gamma_magnet: fixPrice((activeDetailRaw as any).gamma_magnet, ticker),
        pin_strike: fixPrice((activeDetailRaw as any).pin_strike, ticker),
        max_pain: fixPrice(maxPain, ticker),
        call_centroid: fixPrice(callCentroid, ticker),
        put_centroid: fixPrice(putCentroid, ticker),
        zero_gamma: fixPrice((activeDetailRaw as any).zero_gamma, ticker),
        iv_current: ivCurrent,
        iv_change: dailyIvChange,
     };
  }, [activeDetailRaw, liveData, trendsMap, activeTrendData]);
  
  const lookupTicker = useMemo(() => {
     if (!activeDetail) return "";
     // Prioritize the actual ticker to keep futures and ETFs separate for profile mapping
     const raw = activeDetail.ticker || activeDetail.cash_ticker || "";
     return raw.replace(/^\//, '');
  }, [activeDetail]);
  
  const activeProfileRaw = useMemo(() => profilesMap[lookupTicker] || [], [lookupTicker, profilesMap]);
  const activeProfile = useMemo(() => activeProfileRaw.map((p: any) => ({ ...p, strike: fixPrice(p.strike, lookupTicker) })), [activeProfileRaw, lookupTicker]);
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
     
     // Filter for meaningful strikes with non-zero GEX near current price (within 15%)
     const candidateCalls = activeProfile.filter((p: any) => p.call_gex > 0 && p.strike >= drillSpot * 0.85 && p.strike <= drillSpot * 1.15);
     const candidatePuts = activeProfile.filter((p: any) => Math.abs(p.put_gex) > 0 && p.strike >= drillSpot * 0.85 && p.strike <= drillSpot * 1.15);
     
     // Pick top 5 by magnitude — use DESCENDING sort for both (b - a)
     const bestCalls = [...(candidateCalls.length >= 3 ? candidateCalls : activeProfile.filter((p: any) => p.call_gex > 0))]
        .sort((a,b) => b.call_gex - a.call_gex)
        .slice(0, 5);
     
     const bestPuts = [...(candidatePuts.length >= 3 ? candidatePuts : activeProfile.filter((p: any) => Math.abs(p.put_gex) > 0))]
        .sort((a,b) => Math.abs(b.put_gex) - Math.abs(a.put_gex))
        .slice(0, 5);
        
     return { calls: bestCalls, puts: bestPuts };
  }, [activeProfile, drillSpot]);

  // ── DERIVED SERIES FOR NEW CHARTS ──
  const dexProfile = useMemo(() => {
    if (!zoomedProfile.length) return [];
    return zoomedProfile.map((p: any) => ({
      strike: p.strike,
      call_dex: p.call_dex ?? 0,
      put_dex: p.put_dex ?? 0,
      net_dex: (p.call_dex ?? 0) + (p.put_dex ?? 0),
    }));
  }, [zoomedProfile]);

  const skewProfile = useMemo(() => {
    if (!zoomedProfile.length) return [];
    return zoomedProfile
      .filter((p: any) => p.call_iv != null || p.put_iv != null)
      .map((p: any) => ({
        strike: p.strike,
        call_iv: p.call_iv != null ? +(p.call_iv * 100).toFixed(2) : null,
        put_iv:  p.put_iv  != null ? +(p.put_iv  * 100).toFixed(2) : null,
        skew: (p.put_iv != null && p.call_iv != null) ? +((p.put_iv - p.call_iv) * 100).toFixed(2) : null,
      }));
  }, [zoomedProfile]);

  const cumulativeGex = useMemo(() => {
    if (!activeProfile.length) return [];
    const sorted = [...activeProfile].sort((a: any, b: any) => a.strike - b.strike);
    let running = 0;
    return sorted.map((p: any) => {
      running += p.net_gex ?? (p.call_gex ?? 0) + (p.put_gex ?? 0);
      return { strike: p.strike, cumulative: running };
    });
  }, [activeProfile]);

  const volSummary = useMemo(() => {
    if (!activeProfile.length) return { totalCallVol: 0, totalPutVol: 0, totalCallOI: 0, totalPutOI: 0, callPrem: 0, putPrem: 0, near: [] };
    let tCV = 0, tPV = 0, tCOI = 0, tPOI = 0, tCP = 0, tPP = 0;
    activeProfile.forEach((p: any) => {
      tCV  += p.call_vol ?? 0;
      tPV  += p.put_vol  ?? 0;
      tCOI += p.call_oi  ?? 0;
      tPOI += p.put_oi   ?? 0;
      tCP  += p.call_premium ?? 0;
      tPP  += p.put_premium  ?? 0;
    });
    const near = zoomedProfile.slice(0, 20).map((p: any) => ({
      strike: p.strike,
      call_vol: p.call_vol ?? 0,
      put_vol:  p.put_vol  ?? 0,
      call_oi:  p.call_oi  ?? 0,
      put_oi:   p.put_oi   ?? 0,
    }));
    return { totalCallVol: tCV, totalPutVol: tPV, totalCallOI: tCOI, totalPutOI: tPOI, callPrem: tCP, putPrem: tPP, near };
  }, [activeProfile, zoomedProfile]);

  const priceLadder = useMemo(() => {
    if (!activeDetail) return [];
    
    const base = [
      { price: fixPrice(activeDetail.spot, activeDetail.ticker), label: "Live Price", type: "spot", note: "Current spot tracking" },
      { price: fixPrice(activeDetail.gamma_magnet, activeDetail.ticker), label: "Gamma Magnet", type: "magnet", note: "Attracts price, high liquidity grab" },
      { price: fixPrice(activeDetail.zero_gamma || activeDetail.gamma_flip_upper, activeDetail.ticker), label: "Gamma Flip", type: "regime", note: "Net gamma polarity shifts here" },
      { price: fixPrice(activeDetail.call_wall, activeDetail.ticker), label: "Primary Call Wall", type: "resistance", note: "Absolute highest Call GEX concentration" },
      { price: fixPrice(activeDetail.put_wall, activeDetail.ticker), label: "Primary Put Wall", type: "support", note: "Absolute highest Put GEX concentration" },
      { price: fixPrice(activeDetail.call_centroid, activeDetail.ticker), label: "Call Center", type: "center", note: "Call-driven gamma gravity point" },
      { price: fixPrice(activeDetail.put_centroid, activeDetail.ticker), label: "Put Center", type: "center", note: "Put-driven liquidity floor" },
    ];
    
    // Add top 3 call walls
    topNodes.calls.slice(0, 3).forEach((n: any, idx: number) => {
        base.push({ price: n.strike, label: `Call Wall ${idx + 1}`, type: "resistance", note: "High call OI, resistance expected" });
    });
    
    // Add top 3 put walls
    topNodes.puts.slice(0, 3).forEach((n: any, idx: number) => {
        base.push({ price: n.strike, label: `Put Wall ${idx + 1}`, type: "support", note: "High put OI, support expected" });
    });

    // ── Multi-Expiry Expected Moves ──
    if (ms.expected_moves && Array.isArray(ms.expected_moves)) {
        ms.expected_moves.forEach((em: any) => {
            const label = em.dte === 0 ? "0DTE" : (em.dte === 1 ? "1DTE" : `${em.expiry}`);
            base.push({ 
                price: fixPrice(em.em_upper, activeDetail.ticker), 
                label: `${label} Upper EM`, 
                type: "em", 
                note: `±${em.em_value} Expected Move` 
            });
            base.push({ 
                price: fixPrice(em.em_lower, activeDetail.ticker), 
                label: `${label} Lower EM`, 
                type: "em", 
                note: `±${em.em_value} Expected Move` 
            });
        });
    }

    // Unique levels by price to avoid clutter if primary wall matches top node
    const unique = Array.from(new Map(base.map(item => [item.price, item])).values());
    return unique.filter(l => l.price && l.price > 0).sort((a,b) => b.price - a.price);
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
                     
                     {/* Tactical Narrative Section — above charts so context flows downward */}
                     <Card className="bg-zinc-950 border-white/5 rounded-[2.5rem] overflow-hidden border p-10 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.5)]">
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
                              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest mt-8">Volatility Outlook</div>
                               <div className={`p-6 rounded-3xl border ${activeDetail?.total_gex < -1e9 ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : (activeDetail?.total_gex > 0 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-zinc-900 border-white/5 text-zinc-400')} animate-pulse-slow shadow-lg`}>
                                  <div className="flex items-center gap-3 mb-2">
                                     {activeDetail?.total_gex < -1e9 ? <AlertTriangle size={16} /> : (activeDetail?.total_gex > 0 ? <ShieldCheck size={16} /> : <Activity size={16} />)}
                                     <span className="font-black text-[10px] uppercase tracking-widest whitespace-nowrap">
                                        {activeDetail?.total_gex < -1e9 ? 'High Move Probability' : (activeDetail?.total_gex > 0 ? 'Compression Expected' : 'Neutral Position')}
                                     </span>
                                  </div>
                                  <p className="text-sm font-bold tracking-tight leading-snug">
                                     {activeDetail?.total_gex < -1e9 
                                        ? "Total GEX below -1B warns of market moves > ±1.0% today." 
                                        : (activeDetail?.total_gex > 0 
                                           ? "Positive GEX indicates increased probability of market moves < ±0.5%." 
                                           : "Standard volatility environment.")}
                                  </p>
                               </div>
                            </div>
                            
                            <div className="space-y-6 md:col-span-2">
                               <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Tactical Directives</div>
                               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  {(Array.isArray(ms.coach_note) ? ms.coach_note.slice(1, 10) : ["Maintain discipline"]).map((note: string, idx: number) => (
                                     <div key={idx} className="flex gap-4 p-5 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-emerald-500/20 transition-all group shadow-sm hover:shadow-emerald-500/5 hover:-translate-y-1 duration-300">
                                        <div className="text-emerald-500 font-black text-[10px] flex shrink-0 mt-0.5">{String(idx+1).padStart(2,'0')}</div>
                                        <p className="text-[11px] font-bold text-zinc-300 leading-relaxed group-hover:text-white transition-colors">{fixText(note, activeDetail?.ticker, activeDetail?.spot)}</p>
                                     </div>
                                  ))}
                               </div>
                           </div>
                        </div>
                     </Card>

                     {/* Stats Hero */}
                     <div className="grid grid-cols-4 gap-4">
                        {[
                          { label: "Total GEX", val: activeDetail?.total_gex, icon: <ShieldCheck className={activeDetail?.total_gex < -1e9 ? "text-rose-500 animate-pulse" : "text-emerald-500"} />, sub: activeDetail?.total_gex < -1e9 ? "High Vol Risk" : "Stable Regime", tip: activeDetail?.total_gex < -1e9 ? "GEX < -1B warns of > ±1.0% price swings. Defensive positioning recommended." : (activeDetail?.total_gex > 0 ? "GEX > 0 indicates < ±0.5% stability expected." : "Dealer Net Gamma Exposure across all strikes."), isGex: true },
                          { label: "Net Vanna", val: activeDetail?.net_vanna_exposure, icon: <Layers className="text-blue-500" />, sub: "Delta/Vol Sensitivity", tip: "Exposure to changes in implied volatility. Positive means dealers buy into rallies.", isGex: true },
                          { label: "ATM IV", val: activeDetail?.iv_current ? activeDetail.iv_current + "%" : "—", icon: <TrendingUp className="text-amber-400" />, sub: "Implied Vol", tip: "ATM Implied Volatility from the central option chain. Indicates market-priced expected move.", isRaw: true },
                          { label: "Vol Change", val: activeDetail?.iv_change != null ? (activeDetail.iv_change >= 0 ? "+" : "") + activeDetail.iv_change.toFixed(2) + "%" : "—", icon: <Activity className={(activeDetail?.iv_change || 0) > 0 ? "text-rose-400" : "text-emerald-400"} />, sub: "Daily Shift", tip: "Cumulative change in ATM IV since the session start. Positive = Vol Expansion.", isRaw: true },
                          
                          { label: "Call Wall", val: activeDetail?.call_wall, icon: <ArrowUpRight className="text-emerald-500" />, sub: "Resistance", tip: "Highest concentration of Positive Gamma exposure.", isGex: false },
                          { label: "Put Wall", val: activeDetail?.put_wall, icon: <ArrowDownRight className="text-rose-500" />, sub: "Support", tip: "Highest concentration of Negative Gamma exposure.", isGex: false },
                          { label: "Call Center", val: activeDetail?.call_centroid, icon: <TrendingUp className="text-emerald-400" />, sub: "Gamma Bulk", tip: "Concentration point of call-driven gamma. Acts as a price pivot.", isGex: false },
                          { label: "Put Center", val: activeDetail?.put_centroid, icon: <TrendingDown className="text-rose-400" />, sub: "Delta Bulk", tip: "Concentration point of put-driven gamma. Core downside liquidity floor.", isGex: false },
                          
                          { label: "Gamma Flip", val: activeDetail?.zero_gamma || activeDetail?.gamma_flip_upper, icon: <Gauge className="text-amber-500" />, sub: "Regime Shift", tip: "Price level where net dealer gamma transitions from positive to negative.", isGex: false },
                          { label: "Gamma Magnet", val: activeDetail?.gamma_magnet, icon: <Target className="text-indigo-500" />, sub: "Liquidity Node", tip: "A significant strike point that acts as a focal point for price attraction.", isGex: false },
                          { label: "Max Pain", val: activeDetail?.max_pain, icon: <Zap className="text-rose-400" />, sub: "Market Anchor", tip: "Strike price that would cause the most financial loss for option buyers upon expiration.", isGex: false },
                          { label: "Pin Strike", val: activeDetail?.pin_strike, icon: <Hash className="text-purple-500" />, sub: "Expiration Goal", tip: `Highest probability strike for price to pin. Odds: ${(activeDetail?.pin_odds || 0).toFixed(1)}%`, isGex: false },
                        ].map((item, idx) => (
                          <UiTooltip key={idx}>
                             <TooltipTrigger asChild>
                               <Card className="bg-gradient-to-br from-zinc-900 to-black border-white/5 rounded-[2rem] p-5 hover:border-emerald-500/20 transition-all duration-500 cursor-help group border shadow-2xl">
                                 <div className="flex justify-between items-start mb-4">
                                    <div className="p-3 bg-white/5 rounded-2xl group-hover:bg-emerald-500/10 transition-colors">
                                       {item.icon}
                                    </div>
                                    <span className="text-[9px] font-black text-zinc-700 uppercase tracking-widest text-right leading-none w-1/2">{item.sub}</span>
                                 </div>
                                 <div className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em] mb-1">{item.label}</div>
                                 <div className={`text-xl font-mono font-black tracking-tighter ${item.label === 'Total GEX' && item.val < -1e9 ? 'text-rose-500' : ''}`}>
                                    {item.val ? (item.isRaw ? item.val : (item.isGex ? fmtGex(item.val as any) : (item.val as any).toLocaleString(undefined, {minimumFractionDigits: 1}))) : "—"}
                                 </div>
                               </Card>
                             </TooltipTrigger>
                             <TooltipContent className="bg-zinc-900 border-zinc-700 p-4 max-w-[250px] rounded-2xl shadow-emerald-500/10 shadow-2xl">
                               <p className="text-xs font-semibold leading-relaxed tracking-tight text-white">{item.tip}</p>
                             </TooltipContent>
                          </UiTooltip>
                        ))}
                     </div>


                     {/* Main Chart Section */}
                     <Card className="bg-black/40 border-white/5 rounded-[3rem] overflow-hidden backdrop-blur-xl border flex flex-col min-h-[600px] basis-[600px]">
                        <div className="p-10 border-b border-white/5 flex items-center justify-between bg-black/40">
                           <Tabs value={mainTab} onValueChange={(v: any) => setMainTab(v)} className="bg-zinc-900/50 p-1.5 rounded-2xl">
                              <TabsList className="bg-transparent gap-1.5 h-auto p-0 flex-wrap">
                                 <TabsTrigger value="profile"    className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-emerald-400">GEX Profile</TabsTrigger>
                                 <TabsTrigger value="history"    className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-emerald-400">GEX History</TabsTrigger>
                                 <TabsTrigger value="dex"        className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-blue-400">DEX</TabsTrigger>
                                 <TabsTrigger value="skew"       className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-purple-400">IV Skew</TabsTrigger>
                                 <TabsTrigger value="fearpremium" className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-indigo-500/20 data-[state=active]:text-indigo-400">Fear/Premium</TabsTrigger>
                                 <TabsTrigger value="cumulative" className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-amber-400">Cumul GEX</TabsTrigger>
                                 <TabsTrigger value="volsummary" className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-black data-[state=active]:text-cyan-400">Vol / OI</TabsTrigger>
                                 <TabsTrigger value="bookmap" className="rounded-xl px-5 py-3 text-[9px] font-black uppercase tracking-widest data-[state=active]:bg-orange-500/20 data-[state=active]:text-orange-400">
                                    <Layers className="w-3.5 h-3.5 mr-1.5" />
                                    Bookmap
                                 </TabsTrigger>
                              </TabsList>
                           </Tabs>
                           <div className="flex items-center gap-6">
                              {true && (
                                 <div className="flex items-center gap-3">
                                    <Dialog>
                                       <DialogTrigger asChild>
                                          <Button variant="outline" size="sm" className="bg-black/40 border-white/5 rounded-2xl text-[9px] font-black uppercase tracking-widest flex items-center gap-2 hover:bg-white/5">
                                             <Maximize2 size={12} />
                                             Maximize
                                          </Button>
                                       </DialogTrigger>
                                       <DialogContent className="max-w-none w-screen h-screen bg-zinc-950/98 border-0 p-0 rounded-none flex flex-col overflow-hidden">
                                           {/* Fullscreen header */}
                                           <DialogHeader className="flex-shrink-0 flex flex-row items-center justify-between px-10 py-6 border-b border-white/5">
                                              <div>
                                                 <DialogTitle className="text-2xl font-black tracking-tighter text-white uppercase">
                                                    {activeDetail?.ticker}&nbsp;&mdash;&nbsp;
                                                    {mainTab === 'profile'    ? 'High Fidelity GEX Analysis'
                                                     : mainTab === 'history'  ? 'Historical GEX Trend'
                                                     : mainTab === 'dex'      ? 'Delta Exposure by Strike'
                                                     : mainTab === 'skew'     ? 'Implied Volatility Skew'
                                                     : mainTab === 'fearpremium' ? 'Institutional Fear Premium'
                                                     : mainTab === 'cumulative' ? 'Cumulative Net GEX'
                                                     : 'Volume & Open Interest'}
                                                 </DialogTitle>
                                                 <p className="text-zinc-600 font-bold uppercase tracking-[0.2em] text-[9px] mt-1">Fullscreen Terminal View</p>
                                              </div>
                                              {mainTab === 'profile' && (
                                                 <div className="flex bg-zinc-900/80 p-1 rounded-xl border border-white/5">
                                                    {(['nodes','net','liquidity'] as const).map(opt => (
                                                       <button key={opt} onClick={() => setProfileOption(opt)}
                                                          className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all ${profileOption === opt ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}>
                                                          {opt}
                                                       </button>
                                                    ))}
                                                 </div>
                                              )}
                                           </DialogHeader>

                                           {/* Main chart area */}
                                           <div className="flex-1 min-h-0 flex flex-col p-8">

                                           {mainTab === 'profile' ? (
                                              <div className="w-full h-full">
                                                 {!zoomedProfile.length ? (
                                                    <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                                       <ZapOff size={64} /><span className="text-sm font-black uppercase tracking-widest">No exposure clusters found</span>
                                                    </div>
                                                 ) : (
                                                 <ResponsiveContainer width="100%" height="100%">
                                                    {profileOption === 'nodes' ? (
                                                       <BarChart data={zoomedProfile} layout="vertical" margin={{ left: 30, right: 80, top: 10, bottom: 10 }} barGap={0}>
                                                          <XAxis type="number" hide />
                                                          <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#a1a1aa', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={3} />
                                                          <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => { if (!active || !payload?.length) return null; const data = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {data.strike}</div><div className="grid grid-cols-2 gap-6"><div><div className="text-[8px] font-black text-emerald-500/80 uppercase tracking-widest mb-1">Call GEX</div><div className="text-sm font-mono font-black text-emerald-400">{fmtGex(data.call_gex)}</div></div><div><div className="text-[8px] font-black text-rose-500/80 uppercase tracking-widest mb-1">Put GEX</div><div className="text-sm font-mono font-black text-rose-400">{fmtGex(data.put_gex)}</div></div></div></div>); }} />
                                                          <Bar dataKey="call_gex" fill="#10b981" radius={[0, 4, 4, 0]} opacity={0.6} />
                                                          <Bar dataKey="put_gex"  fill="#f43f5e" radius={[4, 0, 0, 4]} opacity={0.6} />
                                                          {priceLadder.map((l: any, idx) => (<ReferenceLine key={idx} y={l.price} stroke={l.type === 'spot' ? '#10b981' : l.type === 'magnet' ? '#6366f1' : l.type === 'resistance' ? '#f43f5e' : l.type === 'support' ? '#10b981' : '#71717a'} strokeDasharray={l.type === 'spot' ? '0' : '4 4'} strokeWidth={l.type === 'spot' ? 2 : 1} label={{ position: 'right', value: l.label, fill: '#ffffff', fontSize: 12, fontWeight: '900', dx: 10 }} />))}
                                                       </BarChart>
                                                    ) : profileOption === 'net' ? (
                                                       <ComposedChart data={zoomedProfile} layout="vertical" margin={{ left: 30, right: 80, top: 10, bottom: 10 }}>
                                                          <XAxis type="number" hide />
                                                          <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                                          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                                                          <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => { if (!active || !payload?.length) return null; const data = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {data.strike}</div><div className="text-[8px] font-black text-white/50 uppercase tracking-widest mb-1">Net Exposure</div><div className={`text-xl font-mono font-black ${data.net_gex >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtGex(data.net_gex)}</div></div>); }} />
                                                          <Bar dataKey="net_gex" radius={[4,4,4,4]}>{zoomedProfile.map((entry: any, index: number) => (<Cell key={`cell-${index}`} fill={entry.net_gex >= 0 ? '#10b981' : '#f43f5e'} opacity={0.7} />))}</Bar>
                                                          {priceLadder.map((l: any, idx) => (<ReferenceLine key={idx} y={l.price} stroke={l.type === 'spot' ? '#10b981' : '#38bdf8'} strokeDasharray="4 4" label={{ position: 'right', value: l.label, fill: '#ffffff', fontSize: 12, fontWeight: '900', dx: 10 }} />))}
                                                       </ComposedChart>
                                                    ) : (
                                                       <BarChart data={zoomedProfile} layout="vertical" margin={{ left: 30, right: 80, top: 10, bottom: 10 }}>
                                                          <XAxis type="number" hide />
                                                          <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#d4d4d8', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                                          <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => { if (!active || !payload?.length) return null; const data = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {data.strike} | Liquidity</div><div className="grid grid-cols-2 gap-4"><div><div className="text-[8px] font-black text-zinc-400 uppercase mb-1">Volume</div><div className="text-sm font-mono font-black">{data.call_vol + data.put_vol}</div></div><div><div className="text-[8px] font-black text-zinc-400 uppercase mb-1">Open Int</div><div className="text-sm font-mono font-black">{data.call_oi + data.put_oi}</div></div></div></div>); }} />
                                                          <Bar dataKey="call_vol" stackId="vol" fill="#10b981" opacity={0.4} />
                                                          <Bar dataKey="put_vol"  stackId="vol" fill="#f43f5e" opacity={0.4} />
                                                          <Bar dataKey="call_oi"  stackId="oi"  fill="#10b981" opacity={0.8} />
                                                          <Bar dataKey="put_oi"   stackId="oi"  fill="#f43f5e" opacity={0.8} />
                                                       </BarChart>
                                                    )}
                                                 </ResponsiveContainer>
                                                 )}
                                              </div>

                                           ) : mainTab === 'history' ? (
                                              <div className="w-full h-full">
                                                 {!activeTrendData.length ? (
                                                    <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                                       <Activity size={64} /><span className="text-sm font-black uppercase tracking-widest text-center">Trend intelligence unavailable.<br/>Awaiting market telemetry...</span>
                                                    </div>
                                                 ) : (
                                                 <ResponsiveContainer width="100%" height="100%">
                                                    <AreaChart data={activeTrendData} margin={{top: 20, right: 40, left: 20, bottom: 20}}>
                                                       <defs><linearGradient id="trendGexFull" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/><stop offset="95%" stopColor="#10b981" stopOpacity={0}/></linearGradient></defs>
                                                       <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                                       <XAxis dataKey="timestamp" stroke="#ffffff15" fontSize={11} tickFormatter={(v) => new Date(v).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} />
                                                       <YAxis stroke="#ffffff15" fontSize={11} tickFormatter={(v) => fmtGex(v)} width={80} />
                                                       <RechartsTooltip content={({ active, payload }) => { if (!active || !payload?.length) return null; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl"><div className="text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-1">Total Net GEX</div><div className="text-2xl font-mono font-black">{fmtGex(payload[0].value as number)}</div><div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mt-2">{new Date(payload[0].payload.timestamp).toLocaleTimeString()}</div></div>); }} />
                                                       <Area type="monotone" dataKey="total_gex" stroke="#10b981" fillOpacity={1} fill="url(#trendGexFull)" strokeWidth={3} />
                                                    </AreaChart>
                                                 </ResponsiveContainer>
                                                 )}
                                              </div>

                                           ) : mainTab === 'dex' ? (
                                              <div className="w-full h-full">
                                                 {!dexProfile.length ? (
                                                    <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                                       <Layers size={64} /><span className="text-sm font-black uppercase tracking-widest">DEX data unavailable</span>
                                                    </div>
                                                 ) : (
                                                 <ResponsiveContainer width="100%" height="100%">
                                                    <ComposedChart data={dexProfile} layout="vertical" margin={{ left: 30, right: 80, top: 10, bottom: 10 }}>
                                                       <XAxis type="number" hide />
                                                       <YAxis dataKey="strike" type="category" width={80} tick={{ fill: '#a1a1aa', fontSize: 13, fontWeight: 900 }} tickLine={false} axisLine={false} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                                       <CartesianGrid strokeDasharray="3 3" stroke="#ffffff04" horizontal={false} />
                                                       <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => { if (!active || !payload?.length) return null; const d = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl min-w-[180px]"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {d.strike}</div><div className="space-y-2"><div className="flex justify-between gap-6"><span className="text-[9px] font-black text-blue-400 uppercase">Call DEX</span><span className="font-mono font-black text-blue-400">{fmtGex(d.call_dex)}</span></div><div className="flex justify-between gap-6"><span className="text-[9px] font-black text-rose-400 uppercase">Put DEX</span><span className="font-mono font-black text-rose-400">{fmtGex(d.put_dex)}</span></div><div className="flex justify-between gap-6 pt-2 border-t border-white/5"><span className="text-[9px] font-black text-zinc-400 uppercase">Net DEX</span><span className={`font-mono font-black ${d.net_dex >= 0 ? 'text-blue-300' : 'text-rose-300'}`}>{fmtGex(d.net_dex)}</span></div></div></div>); }} />
                                                       <Bar dataKey="call_dex" fill="#3b82f6" radius={[0, 4, 4, 0]} opacity={0.65} />
                                                       <Bar dataKey="put_dex"  fill="#f43f5e" radius={[4, 0, 0, 4]} opacity={0.65} />
                                                       <Line type="monotone" dataKey="net_dex" stroke="#a78bfa" strokeWidth={2} dot={false} />
                                                       <ReferenceLine y={drillSpot} stroke="#10b981" strokeWidth={2} label={{ position: 'right', value: 'Spot', fill: '#10b981', fontSize: 12, fontWeight: '900', dx: 8 }} />
                                                    </ComposedChart>
                                                 </ResponsiveContainer>
                                                 )}
                                              </div>

                                           ) : mainTab === 'skew' ? (
                                              <div className="w-full h-full">
                                                 {!skewProfile.length ? (
                                                    <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                                       <Activity size={64} /><span className="text-sm font-black uppercase tracking-widest text-center">IV Skew data unavailable.<br/>Populates during live RTH session.</span>
                                                    </div>
                                                 ) : (
                                                 <ResponsiveContainer width="100%" height="100%">
                                                    <ComposedChart data={skewProfile} margin={{ left: 20, right: 40, top: 20, bottom: 40 }}>
                                                       <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                                       <XAxis dataKey="strike" stroke="#ffffff10" fontSize={11} tickFormatter={(v) => Math.round(v).toLocaleString()} label={{ value: 'Strike', position: 'insideBottom', offset: -10, fill: '#52525b', fontSize: 11 }} />
                                                       <YAxis stroke="#ffffff10" fontSize={11} tickFormatter={(v) => v.toFixed(1) + '%'} />
                                                       <RechartsTooltip content={({ active, payload }) => { if (!active || !payload?.length) return null; const d = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl min-w-[180px]"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {d.strike}</div><div className="space-y-2"><div className="flex justify-between gap-6"><span className="text-[9px] font-black text-emerald-400 uppercase">Call IV</span><span className="font-mono font-black text-emerald-400">{d.call_iv?.toFixed(1)}%</span></div><div className="flex justify-between gap-6"><span className="text-[9px] font-black text-rose-400 uppercase">Put IV</span><span className="font-mono font-black text-rose-400">{d.put_iv?.toFixed(1)}%</span></div><div className="flex justify-between gap-6 pt-2 border-t border-white/5"><span className="text-[9px] font-black text-purple-400 uppercase">Skew</span><span className={`font-mono font-black ${(d.skew ?? 0) >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{(d.skew ?? 0) >= 0 ? '+' : ''}{d.skew?.toFixed(1)}%</span></div></div></div>); }} />
                                                       <Area type="monotone" dataKey="call_iv" stroke="#10b981" fill="#10b981" fillOpacity={0.08} strokeWidth={1.5} dot={false} />
                                                       <Area type="monotone" dataKey="put_iv"  stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.08} strokeWidth={1.5} dot={false} />
                                                       <Line type="monotone" dataKey="skew" stroke="#a855f7" strokeWidth={2.5} dot={false} />
                                                       <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" label={{ value: 'Spot', fill: '#10b981', fontSize: 11, fontWeight: '900' }} />
                                                       <ReferenceLine y={0} stroke="#ffffff20" strokeWidth={1} />
                                                       <Legend iconType="line" iconSize={14} wrapperStyle={{ fontSize: '10px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em', paddingTop: '8px' }} />
                                                    </ComposedChart>
                                                 </ResponsiveContainer>
                                                 )}
                                              </div>

                                            ) : mainTab === 'bookmap' ? (
                                               <div className="w-full h-full p-10 flex flex-col items-center justify-center bg-transparent rounded-[2rem]">
                                                  <Layers size={64} className="text-amber-500 opacity-50 mb-6" />
                                                  <h2 className="text-2xl font-black uppercase tracking-widest text-zinc-300 mb-2">Bookmap Workspace</h2>
                                                  <p className="text-sm text-zinc-500 font-medium max-w-md text-center mb-8">
                                                    The Level 2 Heatmap has been upgraded to a dedicated, full-screen professional workspace with granular zoom, size filtering, and DOM controls.
                                                  </p>
                                                  <a href="/bookmap" className="px-8 py-4 flex items-center gap-3 bg-amber-500 text-black font-black uppercase tracking-widest text-sm rounded-xl hover:bg-amber-400 transition-colors shadow-[0_0_30px_rgba(245,158,11,0.3)] hover:scale-105 active:scale-95 duration-200">
                                                    Launch Full Workspace
                                                  </a>
                                               </div>
                                            ) : mainTab === 'fearpremium' ? (
                                              <div className="w-full h-full p-4">
                                                 <VolatilitySkewChart ticker={lookupTicker} data={activeTrendData} />
                                              </div>
                                           ) : mainTab === 'cumulative' ? (
                                              <div className="w-full h-full">
                                                 {!cumulativeGex.length ? (
                                                    <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4">
                                                       <TrendingUp size={64} /><span className="text-sm font-black uppercase tracking-widest">No cumulative data</span>
                                                    </div>
                                                 ) : (
                                                 <ResponsiveContainer width="100%" height="100%">
                                                    <ComposedChart data={cumulativeGex} margin={{ left: 20, right: 40, top: 20, bottom: 40 }}>
                                                       <defs><linearGradient id="cumulPosFull" x1="0" y1="0" x2="0" y2="1"><stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.25}/><stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/></linearGradient></defs>
                                                       <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                                       <XAxis dataKey="strike" stroke="#ffffff10" fontSize={11} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                                       <YAxis stroke="#ffffff10" fontSize={11} tickFormatter={(v) => fmtGex(v)} width={80} />
                                                       <RechartsTooltip content={({ active, payload }) => { if (!active || !payload?.length) return null; const d = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl"><div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Strike {d.strike}</div><div className={`text-lg font-mono font-black ${d.cumulative >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtGex(d.cumulative)}</div><div className="text-[9px] font-black text-zinc-600 mt-1">{d.cumulative >= 0 ? 'Dealers absorbing moves' : 'Dealers amplifying moves'}</div></div>); }} />
                                                       <Area type="monotone" dataKey="cumulative" stroke="#f59e0b" strokeWidth={2.5} fill="url(#cumulPosFull)" dot={false} />
                                                       <ReferenceLine y={0} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="6 3" label={{ value: 'Gamma Flip', position: 'insideTopRight', fill: '#f59e0b', fontSize: 11, fontWeight: '900' }} />
                                                       <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" label={{ value: 'Spot', fill: '#10b981', fontSize: 11, fontWeight: '900' }} />
                                                    </ComposedChart>
                                                 </ResponsiveContainer>
                                                 )}
                                              </div>

                                           ) : (
                                              /* Vol / OI fullscreen */
                                              <div className="w-full h-full flex flex-col gap-6">
                                                 <div className="grid grid-cols-6 gap-4 flex-shrink-0">
                                                    {([
                                                      { label: 'Call Volume', val: volSummary.totalCallVol, color: 'text-emerald-400', fmt: 'vol' },
                                                      { label: 'Put Volume',  val: volSummary.totalPutVol,  color: 'text-rose-400',    fmt: 'vol' },
                                                      { label: 'P/C Vol',     val: volSummary.totalCallVol > 0 ? +(volSummary.totalPutVol/volSummary.totalCallVol).toFixed(2) : 0, color: (volSummary.totalPutVol/Math.max(volSummary.totalCallVol,1)) > 1.1 ? 'text-rose-400' : 'text-emerald-400', fmt: 'raw' },
                                                      { label: 'Call OI',     val: volSummary.totalCallOI,  color: 'text-emerald-400', fmt: 'vol' },
                                                      { label: 'Put OI',      val: volSummary.totalPutOI,   color: 'text-rose-400',    fmt: 'vol' },
                                                      { label: 'P/C OI',      val: volSummary.totalCallOI > 0 ? +(volSummary.totalPutOI/volSummary.totalCallOI).toFixed(2) : 0, color: (volSummary.totalPutOI/Math.max(volSummary.totalCallOI,1)) > 1.1 ? 'text-rose-400' : 'text-emerald-400', fmt: 'raw' },
                                                    ] as const).map((item, i) => (
                                                      <div key={i} className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
                                                         <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-2">{item.label}</div>
                                                         <div className={`text-xl font-mono font-black ${item.color}`}>{item.fmt === 'raw' ? item.val : item.val > 1e6 ? (item.val/1e6).toFixed(1)+'M' : item.val > 1e3 ? (item.val/1e3).toFixed(1)+'K' : item.val}</div>
                                                      </div>
                                                    ))}
                                                 </div>
                                                 <div className="flex-1 min-h-0">
                                                    <ResponsiveContainer width="100%" height="100%">
                                                       <BarChart data={volSummary.near} margin={{ left: 20, right: 20, top: 10, bottom: 50 }}>
                                                          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                                          <XAxis dataKey="strike" fontSize={11} tick={{ fill: '#52525b', fontWeight: 900 }} tickFormatter={(v) => Math.round(v).toLocaleString()} angle={-45} textAnchor="end" />
                                                          <YAxis hide />
                                                          <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={({ active, payload }) => { if (!active || !payload?.length) return null; const d = payload[0].payload; return (<div className="bg-black/90 border border-white/10 p-4 rounded-2xl backdrop-blur-3xl shadow-2xl"><div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-2">Strike {d.strike}</div><div className="space-y-1"><div className="flex justify-between gap-4"><span className="text-[8px] text-emerald-400 font-black uppercase">C Vol</span><span className="font-mono text-emerald-400 text-xs">{d.call_vol?.toLocaleString()}</span></div><div className="flex justify-between gap-4"><span className="text-[8px] text-rose-400 font-black uppercase">P Vol</span><span className="font-mono text-rose-400 text-xs">{d.put_vol?.toLocaleString()}</span></div><div className="flex justify-between gap-4"><span className="text-[8px] text-emerald-300 font-black uppercase">C OI</span><span className="font-mono text-emerald-300 text-xs">{d.call_oi?.toLocaleString()}</span></div><div className="flex justify-between gap-4"><span className="text-[8px] text-rose-300 font-black uppercase">P OI</span><span className="font-mono text-rose-300 text-xs">{d.put_oi?.toLocaleString()}</span></div></div></div>); }} />
                                                          <Bar dataKey="call_vol" stackId="vol" fill="#10b981" opacity={0.5} />
                                                          <Bar dataKey="put_vol"  stackId="vol" fill="#f43f5e" opacity={0.5} />
                                                          <Bar dataKey="call_oi"  stackId="oi"  fill="#10b981" opacity={0.9} />
                                                          <Bar dataKey="put_oi"   stackId="oi"  fill="#f43f5e" opacity={0.9} />
                                                          <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={1.5} strokeDasharray="4 4" />
                                                          <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: '9px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                                                       </BarChart>
                                                    </ResponsiveContainer>
                                                 </div>
                                              </div>
                                           )}

                                           </div>
                                        </DialogContent>
                                    </Dialog>
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

                           ) : mainTab === 'dex' ? (
                        <div className="w-full flex-1 flex flex-col">
                           {!dexProfile.length ? (
                              <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                 <Layers size={48} />
                                 <span className="text-xs font-black uppercase tracking-widest">DEX data unavailable</span>
                              </div>
                           ) : (
                           <div className="h-[450px] w-full">
                              <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-3">Delta Exposure — Positive = Dealer Long Delta (buys into rally, suppresses moves)</div>
                              <ResponsiveContainer width="100%" height="100%">
                                 <ComposedChart data={dexProfile} layout="vertical" margin={{ left: 30, right: 40, top: 0, bottom: 0 }}>
                                    <XAxis type="number" hide />
                                    <YAxis dataKey="strike" type="category" width={75} tick={{ fill: '#a1a1aa', fontSize: 12, fontWeight: 900 }} tickLine={false} axisLine={false} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff04" horizontal={false} />
                                    <RechartsTooltip
                                       cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                       content={({ active, payload }) => {
                                          if (!active || !payload?.length) return null;
                                          const d = payload[0].payload;
                                          return (
                                             <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl min-w-[180px]">
                                                <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {d.strike}</div>
                                                <div className="space-y-2">
                                                   <div className="flex justify-between gap-6"><span className="text-[9px] font-black text-blue-400 uppercase">Call DEX</span><span className="font-mono font-black text-blue-400">{fmtGex(d.call_dex)}</span></div>
                                                   <div className="flex justify-between gap-6"><span className="text-[9px] font-black text-rose-400 uppercase">Put DEX</span><span className="font-mono font-black text-rose-400">{fmtGex(d.put_dex)}</span></div>
                                                   <div className="flex justify-between gap-6 pt-2 border-t border-white/5"><span className="text-[9px] font-black text-zinc-400 uppercase">Net DEX</span><span className={`font-mono font-black ${d.net_dex >= 0 ? 'text-blue-300' : 'text-rose-300'}`}>{fmtGex(d.net_dex)}</span></div>
                                                </div>
                                             </div>
                                          );
                                       }}
                                    />
                                    <Bar dataKey="call_dex" fill="#3b82f6" radius={[0, 4, 4, 0]} opacity={0.65} />
                                    <Bar dataKey="put_dex"  fill="#f43f5e" radius={[4, 0, 0, 4]} opacity={0.65} />
                                    <Line type="monotone" dataKey="net_dex" stroke="#a78bfa" strokeWidth={2} dot={false} />
                                    <ReferenceLine y={drillSpot} stroke="#10b981" strokeWidth={2} label={{ position: 'right', value: 'Spot', fill: '#10b981', fontSize: 10, fontWeight: '900', dx: 8 }} />
                                 </ComposedChart>
                              </ResponsiveContainer>
                           </div>
                           )}
                        </div>

                           ) : mainTab === 'skew' ? (
                        <div className="w-full flex-1 flex flex-col">
                           {!skewProfile.length ? (
                              <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                 <Activity size={48} />
                                 <span className="text-xs font-black uppercase tracking-widest text-center">IV Skew data unavailable.<br/>Populates during live RTH session.</span>
                              </div>
                           ) : (
                           <div className="h-[450px] w-full">
                              <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-3">IV Skew — Put IV minus Call IV. Positive = Put demand premium (bearish skew)</div>
                              <ResponsiveContainer width="100%" height="100%">
                                 <ComposedChart data={skewProfile} margin={{ left: 10, right: 20, top: 10, bottom: 30 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                    <XAxis dataKey="strike" stroke="#ffffff10" fontSize={10} tickFormatter={(v) => Math.round(v).toLocaleString()} label={{ value: 'Strike', position: 'insideBottom', offset: -10, fill: '#52525b', fontSize: 10 }} />
                                    <YAxis stroke="#ffffff10" fontSize={10} tickFormatter={(v) => v.toFixed(1) + '%'} />
                                    <RechartsTooltip
                                       content={({ active, payload }) => {
                                          if (!active || !payload?.length) return null;
                                          const d = payload[0].payload;
                                          return (
                                             <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl min-w-[180px]">
                                                <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-3">Strike {d.strike}</div>
                                                <div className="space-y-2">
                                                   <div className="flex justify-between gap-6"><span className="text-[9px] font-black text-emerald-400 uppercase">Call IV</span><span className="font-mono font-black text-emerald-400">{d.call_iv?.toFixed(1)}%</span></div>
                                                   <div className="flex justify-between gap-6"><span className="text-[9px] font-black text-rose-400 uppercase">Put IV</span><span className="font-mono font-black text-rose-400">{d.put_iv?.toFixed(1)}%</span></div>
                                                   <div className="flex justify-between gap-6 pt-2 border-t border-white/5"><span className="text-[9px] font-black text-purple-400 uppercase">Skew</span><span className={`font-mono font-black ${(d.skew ?? 0) >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{(d.skew ?? 0) >= 0 ? '+' : ''}{d.skew?.toFixed(1)}%</span></div>
                                                </div>
                                             </div>
                                          );
                                       }}
                                    />
                                    <Area type="monotone" dataKey="call_iv" stroke="#10b981" fill="#10b981" fillOpacity={0.08} strokeWidth={1.5} dot={false} />
                                    <Area type="monotone" dataKey="put_iv"  stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.08} strokeWidth={1.5} dot={false} />
                                    <Line type="monotone" dataKey="skew" stroke="#a855f7" strokeWidth={2.5} dot={false} />
                                    <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" label={{ value: 'Spot', fill: '#10b981', fontSize: 10, fontWeight: '900' }} />
                                    <ReferenceLine y={0} stroke="#ffffff20" strokeWidth={1} />
                                    <Legend iconType="line" iconSize={12} wrapperStyle={{ fontSize: '9px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em', paddingTop: '8px' }} />
                                 </ComposedChart>
                              </ResponsiveContainer>
                           </div>
                           )}
                        </div>

                           ) : mainTab === 'fearpremium' ? (
                              <div className="w-full h-full p-4">
                                 <VolatilitySkewChart ticker={lookupTicker} data={activeTrendData} />
                              </div>
                           ) : mainTab === 'cumulative' ? (
                        <div className="w-full flex-1 flex flex-col">
                           {!cumulativeGex.length ? (
                              <div className="flex-1 flex flex-col items-center justify-center opacity-20 gap-4">
                                 <TrendingUp size={48} />
                                 <span className="text-xs font-black uppercase tracking-widest">No cumulative data</span>
                              </div>
                           ) : (
                           <div className="h-[450px] w-full">
                              <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-3">Cumulative Net GEX — Zero-crossing from below = actual Gamma Flip price</div>
                              <ResponsiveContainer width="100%" height="100%">
                                 <ComposedChart data={cumulativeGex} margin={{ left: 10, right: 20, top: 10, bottom: 30 }}>
                                    <defs>
                                       <linearGradient id="cumulPos" x1="0" y1="0" x2="0" y2="1">
                                          <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.25}/>
                                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                                       </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                    <XAxis dataKey="strike" stroke="#ffffff10" fontSize={10} tickFormatter={(v) => Math.round(v).toLocaleString()} />
                                    <YAxis stroke="#ffffff10" fontSize={10} tickFormatter={(v) => fmtGex(v)} />
                                    <RechartsTooltip
                                       content={({ active, payload }) => {
                                          if (!active || !payload?.length) return null;
                                          const d = payload[0].payload;
                                          return (
                                             <div className="bg-black/90 border border-white/10 p-5 rounded-2xl backdrop-blur-3xl shadow-2xl">
                                                <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Strike {d.strike}</div>
                                                <div className={`text-lg font-mono font-black ${d.cumulative >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtGex(d.cumulative)}</div>
                                                <div className="text-[9px] font-black text-zinc-600 mt-1">{d.cumulative >= 0 ? 'Dealers absorbing moves' : 'Dealers amplifying moves'}</div>
                                             </div>
                                          );
                                       }}
                                    />
                                    <Area type="monotone" dataKey="cumulative" stroke="#f59e0b" strokeWidth={2.5} fill="url(#cumulPos)" dot={false} />
                                    <ReferenceLine y={0} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="6 3" label={{ value: 'Gamma Flip', position: 'insideTopRight', fill: '#f59e0b', fontSize: 10, fontWeight: '900' }} />
                                    <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" label={{ value: 'Spot', fill: '#10b981', fontSize: 10, fontWeight: '900' }} />
                                 </ComposedChart>
                              </ResponsiveContainer>
                           </div>
                           )}
                        </div>

                           ) : mainTab === 'bookmap' ? (
                              <div className="w-full flex-1 flex flex-col min-h-[500px] overflow-hidden rounded-3xl">
                                 <L2Heatmap ticker={lookupTicker} />
                              </div>
                           ) : mainTab === 'volsummary' ? (
                        <div className="w-full flex-1 flex flex-col gap-6">
                           <div className="grid grid-cols-3 gap-4">
                              {([
                                 { label: 'Call Volume',   val: volSummary.totalCallVol, color: 'text-emerald-400', fmt: 'vol' },
                                 { label: 'Put Volume',    val: volSummary.totalPutVol,  color: 'text-rose-400',    fmt: 'vol' },
                                 { label: 'P/C Vol Ratio', val: volSummary.totalCallVol > 0 ? +(volSummary.totalPutVol / volSummary.totalCallVol).toFixed(2) : 0, color: ((volSummary.totalPutVol / Math.max(volSummary.totalCallVol, 1)) > 1.1) ? 'text-rose-400' : 'text-emerald-400', fmt: 'raw' },
                                 { label: 'Call OI',       val: volSummary.totalCallOI,  color: 'text-emerald-400', fmt: 'vol' },
                                 { label: 'Put OI',        val: volSummary.totalPutOI,   color: 'text-rose-400',    fmt: 'vol' },
                                 { label: 'P/C OI Ratio',  val: volSummary.totalCallOI > 0 ? +(volSummary.totalPutOI / volSummary.totalCallOI).toFixed(2) : 0, color: ((volSummary.totalPutOI / Math.max(volSummary.totalCallOI, 1)) > 1.1) ? 'text-rose-400' : 'text-emerald-400', fmt: 'raw' },
                              ] as const).map((item, i) => (
                                 <div key={i} className="bg-white/[0.02] border border-white/5 rounded-2xl p-4">
                                    <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-1">{item.label}</div>
                                    <div className={`text-base font-mono font-black ${item.color}`}>
                                       {item.fmt === 'raw' ? item.val : item.val > 1e6 ? (item.val / 1e6).toFixed(1) + 'M' : item.val > 1e3 ? (item.val / 1e3).toFixed(1) + 'K' : item.val}
                                    </div>
                                 </div>
                              ))}
                           </div>
                           <div className="grid grid-cols-2 gap-4">
                              <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-2xl p-4">
                                 <div className="text-[9px] font-black text-emerald-600 uppercase tracking-widest mb-1">Total Call Premium</div>
                                 <div className="text-base font-mono font-black text-emerald-400">{fmtGex(volSummary.callPrem)}</div>
                              </div>
                              <div className="bg-rose-500/5 border border-rose-500/10 rounded-2xl p-4">
                                 <div className="text-[9px] font-black text-rose-600 uppercase tracking-widest mb-1">Total Put Premium</div>
                                 <div className="text-base font-mono font-black text-rose-400">{fmtGex(volSummary.putPrem)}</div>
                              </div>
                           </div>
                           <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Near-ATM Volume &amp; Open Interest</div>
                           <div className="h-56 w-full">
                              <ResponsiveContainer width="100%" height="100%">
                                 <BarChart data={volSummary.near} margin={{ left: 0, right: 10, top: 0, bottom: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                    <XAxis dataKey="strike" fontSize={9} tick={{ fill: '#52525b', fontWeight: 900 }} tickFormatter={(v) => Math.round(v).toLocaleString()} angle={-45} textAnchor="end" />
                                    <YAxis hide />
                                    <RechartsTooltip
                                       cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                       content={({ active, payload }) => {
                                          if (!active || !payload?.length) return null;
                                          const d = payload[0].payload;
                                          return (
                                             <div className="bg-black/90 border border-white/10 p-4 rounded-2xl backdrop-blur-3xl shadow-2xl">
                                                <div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-2">Strike {d.strike}</div>
                                                <div className="space-y-1">
                                                   <div className="flex justify-between gap-4"><span className="text-[8px] text-emerald-400 font-black uppercase">C Vol</span><span className="font-mono text-emerald-400 text-xs">{d.call_vol?.toLocaleString()}</span></div>
                                                   <div className="flex justify-between gap-4"><span className="text-[8px] text-rose-400 font-black uppercase">P Vol</span><span className="font-mono text-rose-400 text-xs">{d.put_vol?.toLocaleString()}</span></div>
                                                   <div className="flex justify-between gap-4"><span className="text-[8px] text-emerald-300 font-black uppercase">C OI</span><span className="font-mono text-emerald-300 text-xs">{d.call_oi?.toLocaleString()}</span></div>
                                                   <div className="flex justify-between gap-4"><span className="text-[8px] text-rose-300 font-black uppercase">P OI</span><span className="font-mono text-rose-300 text-xs">{d.put_oi?.toLocaleString()}</span></div>
                                                </div>
                                             </div>
                                          );
                                       }}
                                    />
                                    <Bar dataKey="call_vol" stackId="vol" fill="#10b981" opacity={0.5} />
                                    <Bar dataKey="put_vol"  stackId="vol" fill="#f43f5e" opacity={0.5} />
                                    <Bar dataKey="call_oi"  stackId="oi"  fill="#10b981" opacity={0.9} />
                                    <Bar dataKey="put_oi"   stackId="oi"  fill="#f43f5e" opacity={0.9} />
                                    <ReferenceLine x={drillSpot} stroke="#10b981" strokeWidth={1.5} strokeDasharray="4 4" />
                                    <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: '8px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                                 </BarChart>
                              </ResponsiveContainer>
                           </div>
                        </div>

                           ) : null}
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
                                          l.type === 'em' ? 'bg-amber-500/10 border-amber-500/20 shadow-[0_0_20px_rgba(245,158,11,0.1)]' :
                                          'bg-emerald-500/5 border-emerald-500/10'
                                       }`}>
                                          <div className="flex justify-between items-start relative z-10">
                                             <div className="space-y-2">
                                                <div className="flex items-center gap-2">
                                                   <div className={`w-1.5 h-1.5 rounded-full ${
                                                      l.type === 'spot' ? 'bg-emerald-500 animate-pulse' :
                                                      l.type === 'magnet' ? 'bg-indigo-500' :
                                                      l.type === 'resistance' ? 'bg-rose-500' : 
                                                      l.type === 'em' ? 'bg-amber-500' : 'bg-emerald-400'
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
                                             ) : l.type === 'em' ? (
                                                <Zap className="text-amber-500" size={20} />
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
