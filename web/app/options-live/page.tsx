"use client";

import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { 
  Radar, RefreshCcw, AlertTriangle, ArrowUpRight, ArrowDownRight, 
  Activity, Crosshair, Layers, Zap, X, BarChart2, Star, StarOff, 
  ChevronRight, Target, Shield, Gauge, TrendingUp, TrendingDown,
  Info, Table as TableIcon, Hash, Timer, Droplets, Flame
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

// ── Display Helpers ──────────────────────────────────────────────────────────
const fmtGex = (v: number | undefined | null) => {
  if (v == null || isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1000000000) return `${(v / 1000000000).toFixed(1)}B`;
  if (abs >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
  if (abs >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return v.toFixed(0);
};

const getRegimeColor = (regime: string | undefined) => {
  if (!regime) return "bg-zinc-800 text-zinc-500 border-zinc-700/50";
  const str = String(regime).toUpperCase();
  if (str.includes("POSITIVE") || str === "1") return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  if (str.includes("NEGATIVE") || str === "-1") return "bg-rose-500/10 text-rose-400 border-rose-500/20";
  return "bg-amber-500/10 text-amber-400 border-amber-500/20";
};

export default function OptionsTacticalCommand() {
  const [liveData, setLiveData] = useState<{ dailyLevels: any, pipelineState: any, gexProfiles: any, liveTrend?: any } | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<any>(null);
  const [priorityTickers, setPriorityTickers] = useState<string[]>([]);
  const [refreshingTickers, setRefreshingTickers] = useState<Set<string>>(new Set());
  
  const [mainTab, setMainTab] = useState<'exposure' | 'activity' | 'trend'>('exposure');
  const [exposureMode, setExposureMode] = useState<'callsPuts' | 'net' | 'absolute'>('callsPuts');
  const [activityMode, setActivityMode] = useState<'volume' | 'oi'>('volume');
  const [rightTab, setRightTab] = useState<'ladder' | 'briefing' | 'nodes'>('ladder');
  const [strikeZoomRange, setStrikeZoomRange] = useState(5); // ±5%
  
  const [activeAlert, setActiveAlert] = useState<{message: string, type: 'success'|'error'|'warning', ticker: string} | null>(null);
  
  const previousRegimes = useRef<Record<string, string>>({});
  const pulsingTickers = useRef<Record<string, number>>({});

  // ── Telemetry Fetch Logic ───────────────────────────────────────────────
  const fetchData = async () => {
    try {
      const res = await fetch("/api/options-live");
      const json = await res.json();
      if (json.success) {
        setLiveData(json.data);
        setLastFetch(new Date(json.lastUpdated));
        
        // Regime Shift Detection
        const marketStructure = json.data?.dailyLevels?.market_structure || [];
        marketStructure.forEach((m: any) => {
          const ticker = m.cash_ticker || m.asset;
          const currentRegime = m.regime_label;
          if (ticker && currentRegime) {
             const prev = previousRegimes.current[ticker];
             if (prev && prev !== currentRegime) {
                const type = currentRegime.includes('BULL') || currentRegime.includes('POS') ? 'success' : currentRegime.includes('BEAR') || currentRegime.includes('NEG') ? 'error' : 'warning';
                playChime(type);
                setActiveAlert({
                  message: `Regime Shift Detected: ${ticker} transitioned from ${prev} to ${currentRegime}`,
                  type: type as any,
                  ticker
                });
                pulsingTickers.current[ticker] = Date.now() + 30000;
             }
             previousRegimes.current[ticker] = currentRegime;
          }
        });
      }
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const playChime = useCallback((type: 'success'|'error'|'warning') => {
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      oscillator.type = type === 'error' ? 'sawtooth' : 'sine';
      oscillator.frequency.setValueAtTime(type === 'error' ? 220 : type === 'success' ? 880 : 440, audioCtx.currentTime); 
      gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.5);
      oscillator.start(); oscillator.stop(audioCtx.currentTime + 0.5);
    } catch(e) {}
  }, []);

  useEffect(() => {
    fetchData();
    const inv = setInterval(fetchData, 15000);
    return () => clearInterval(inv);
  }, []);

  // ── Data Processing ──
  const dataObject: any = useMemo(() => liveData?.dailyLevels || {}, [liveData]);
  const pipelineState: any = useMemo(() => liveData?.pipelineState || {}, [liveData]);
  const tickersData = useMemo(() => pipelineState.tickers ? Object.values(pipelineState.tickers) : [], [pipelineState]);
  const rawLevels = useMemo(() => dataObject.levels || [], [dataObject]);
  const activeDetail = selectedTicker || (tickersData.length > 0 ? tickersData[0] : null);
  const profilesMap: any = useMemo(() => liveData?.gexProfiles?.profiles || {}, [liveData]);

  // Profile Mapping (Index Match)
  let lookupTicker = activeDetail?.cash_ticker || activeDetail?.ticker;
  if (lookupTicker?.startsWith('/') || !profilesMap[lookupTicker]) {
    const fnMap: Record<string, string> = { '/ES': 'SPX', '/NQ': 'QQQ', '/YM': 'DIA', '/RTY': 'IWM', 'ES': 'SPX', 'NQ': 'QQQ', 'YM': 'DIA', 'RTY': 'IWM' };
    const mapped = fnMap[lookupTicker];
    if (mapped && profilesMap[mapped]) lookupTicker = mapped;
  }
  
  let activeProfile = useMemo(() => lookupTicker ? profilesMap[lookupTicker] || [] : [], [lookupTicker, profilesMap]);
  const cashDetail = pipelineState.tickers?.[lookupTicker] || activeDetail;
  const drillSpot = cashDetail?.spot || activeDetail?.spot || 0;

  // Zoom to Spot
  const zoomedProfile = useMemo(() => {
    if (activeProfile.length === 0 || drillSpot === 0) return activeProfile;
    const factor = strikeZoomRange / 100;
    const lower = drillSpot * (1 - factor);
    const upper = drillSpot * (1 + factor);
    const filtered = activeProfile.filter((p: any) => p.strike >= lower && p.strike <= upper);
    return filtered.length > 5 ? filtered : activeProfile;
  }, [activeProfile, drillSpot, strikeZoomRange]);

  const liveTrendHistory = liveData?.liveTrend?.history || {};
  let activeTrendData = useMemo(() => {
    const raw = lookupTicker ? liveTrendHistory[lookupTicker] || [] : [];
    return [...raw].sort((a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [lookupTicker, liveTrendHistory]);

  // ── Normalization Helpers ──
  const getLevelValue = (tickerName: string, typeName: string) => {
    if (!rawLevels || rawLevels.length === 0) return 0;
    const lookupAsset = tickerName?.replace("/", "");
    const cashTicker = activeDetail?.cash_ticker;

    let lvl = rawLevels.find((l: any) => l.asset === lookupAsset && l.type === typeName);
    if (!lvl && cashTicker) lvl = rawLevels.find((l: any) => (l.asset === cashTicker || l.cash_ticker === cashTicker) && l.type === typeName);
    if (!lvl) lvl = rawLevels.find((l: any) => l.type === typeName && (String(l.asset).includes(lookupAsset) || l.cash_ticker === lookupAsset));
    if (!lvl) return 0;

    let val = Number(lvl.level);
    const spot = activeDetail?.spot || 0;
    if (spot > 0 && val > spot * 5) {
        const ratio = Number(lvl.basis_ratio) || 10;
        if (ratio > 5 && ratio < 15) val /= 10;
    }
    return val;
  };

  const fixText = (text: string, ticker: string, spot: number) => {
    if (!text || !ticker?.startsWith('/') || !spot) return text;
    return text.replace(/(\d{4,}(?:\.\d+)?)/g, (match) => {
      const v = parseFloat(match);
      if (v > spot * 5 && v < spot * 15) return (v / 10).toFixed(1);
      return match;
    });
  };

  const generateLadder = () => {
    if (!activeDetail) return [];
    const spot = activeDetail.spot || 0;
    const named = [
      { price: getLevelValue(activeDetail.ticker, "Upper EM"), label: "Expected Move Upper", type: "resistance" },
      { price: activeDetail.call_wall, label: "Call Wall", type: "resistance" },
      { price: activeDetail.secondary_call_wall, label: "Sec. Call Wall", type: "resistance" },
      { price: activeDetail.gamma_flip_upper, label: "Gamma Flip (U)", type: "resistance" },
      { price: activeDetail.zero_gamma, label: "Zero Gamma", type: "neutral" },
      { price: activeDetail.gamma_magnet, label: "Gamma Magnet", type: "neutral" },
      { price: spot, label: "Current Spot", type: "spot" },
      { price: activeDetail.put_wall, label: "Put Wall", type: "support" },
      { price: activeDetail.secondary_put_wall, label: "Sec. Put Wall", type: "support" },
      { price: activeDetail.hedge_wall, label: "Hedge Wall", type: "support" },
      { price: getLevelValue(activeDetail.ticker, "Lower EM"), label: "Expected Move Lower", type: "support" },
    ];
    
    const map = new Map();
    named.forEach(l => {
      let p = Number(l.price);
      if (p <= 0 || isNaN(p)) return;
      if (spot > 0 && p > spot * 5) p /= 10;

      const k = p.toFixed(2);
      if (!map.has(k)) map.set(k, { price: p, labels: [l.label], type: l.type });
      else {
        const ex = map.get(k);
        if (l.type === "spot") ex.type = "spot";
        if (!ex.labels.includes(l.label)) ex.labels.push(l.label);
      }
    });
    return Array.from(map.values()).sort((a: any, b: any) => b.price - a.price);
  };

  const priceLadder = useMemo(generateLadder, [activeDetail, rawLevels]);

  const topStrikes = useMemo(() => {
    if (!activeProfile.length) return [];
    return [...activeProfile]
        .sort((a,b) => Math.abs(b.net_gex) - Math.abs(a.net_gex))
        .slice(0, 15);
  }, [activeProfile]);

  const rankedWalls = useMemo(() => {
    if (!activeProfile.length) return { calls: [], puts: [] };
    const sortedCalls = [...activeProfile].sort((a,b) => b.call_gex - a.call_gex).slice(0, 3);
    const sortedPuts = [...activeProfile].sort((a,b) => a.put_gex - b.put_gex).slice(0, 3);
    return { calls: sortedCalls, puts: sortedPuts };
  }, [activeProfile]);

  if (loading && !liveData) {
    return (
      <div className="flex flex-col h-screen items-center justify-center bg-zinc-950 text-emerald-500 font-mono">
        <div className="relative">
          <Radar className="h-16 w-16 animate-spin opacity-20" />
          <Activity className="h-8 w-8 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse text-emerald-400" />
        </div>
        <div className="mt-6 tracking-widest uppercase text-xs font-black animate-pulse">Initializing Tactical Engine...</div>
      </div>
    );
  }

  const ms = dataObject.market_structure?.find((m: any) => m.cash_ticker === lookupTicker || m.asset === activeDetail?.ticker) || {};

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100 overflow-hidden font-sans select-none">
      
      {/* ── IMMERSIVE HEADER ────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-white/5 bg-zinc-900/40 backdrop-blur-3xl z-40 relative overflow-hidden">
        {/* Animated background glow */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-rose-500/5 rounded-full blur-[100px] pointer-events-none" />

        <div className="flex items-center gap-6 relative">
          <div className="relative">
            <div className="absolute inset-0 bg-emerald-500/20 blur-xl animate-pulse rounded-full" />
            <div className="p-4 bg-zinc-900 rounded-2xl border border-emerald-500/20 shadow-2xl relative">
              <Radar className="h-7 w-7 text-emerald-400" />
            </div>
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tighter uppercase italic leading-none mb-1">Options Tactical Command</h1>
            <div className="flex items-center gap-2">
               <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[9px] font-black tracking-widest px-2 py-0">LIVE TELEMETRY</Badge>
               <span className="text-[10px] font-bold text-zinc-500 tracking-[0.2em] uppercase">V-2.4.9 DEALER ANALYTICS</span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-8">
          <div className="grid grid-cols-2 gap-x-8 gap-y-1">
             <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Update Pulse</div>
             <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest text-right">Data Stability</div>
             <div className="text-xs font-mono text-emerald-400 truncate whitespace-nowrap">{(15000/1000).toFixed(0)} SEC POLLING</div>
             <div className="text-xs font-mono text-emerald-400 text-right uppercase">Optimum</div>
          </div>
          <div className="h-12 w-px bg-white/5" />
          <Button onClick={fetchData} variant="outline" className="h-12 border-white/10 hover:bg-white/5 rounded-2xl font-black text-xs uppercase tracking-widest gap-2 px-6 shadow-xl transition-all active:scale-95 group">
            <RefreshCcw className="h-4 w-4 group-hover:rotate-180 transition-transform duration-500 text-emerald-400" /> Refresh
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        
        {/* ── TACTICAL SCANNER (SIDEBAR) ────────────────────────────────────────── */}
        <div className="w-80 flex flex-col border-r border-white/5 bg-zinc-900/10 backdrop-blur-xl z-30">
           <div className="p-5 border-b border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Gauge size={14} className="text-emerald-500" />
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-400">Tactical Scanner</span>
              </div>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
           </div>
           <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                {tickersData.map((lvl: any) => {
                  const isActive = activeDetail?.ticker === lvl.ticker;
                  const isPulsing = (pulsingTickers.current[lvl.ticker] && pulsingTickers.current[lvl.ticker] > Date.now());
                  const gexSign = lvl.total_gex >= 0;
                  return (
                    <div 
                      key={lvl.ticker}
                      onClick={() => setSelectedTicker(lvl)}
                      className={`group p-4 rounded-2xl border cursor-pointer transition-all duration-300 relative overflow-hidden ${
                        isActive ? 'border-emerald-500/40 bg-emerald-500/10 shadow-[0_0_30px_rgba(16,185,129,0.1)] scale-[0.98]' : 
                        'border-white/5 hover:border-white/20 hover:bg-white/5'
                      }`}
                    >
                      {isActive && <div className="absolute top-0 right-0 p-2"><ChevronRight size={14} className="text-emerald-500" /></div>}
                      <div className="flex justify-between items-start mb-4 relative z-10">
                        <div className="flex flex-col">
                          <span className={`text-xl font-black tracking-tighter uppercase transition-colors ${isActive ? 'text-white' : 'text-zinc-400 group-hover:text-emerald-400'}`}>{lvl.ticker}</span>
                          <span className="text-xs font-mono font-bold text-zinc-500/80">{lvl.spot?.toFixed(2)}</span>
                        </div>
                        <div className="text-right">
                           <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-1">REGIME</div>
                           <Badge className={`${getRegimeColor(lvl.gex_regime)} text-[9px] font-black uppercase rounded-lg px-2`}>{lvl.regime_label || "NEUTRAL"}</Badge>
                        </div>
                      </div>
                      <div className="h-1 bg-white/5 rounded-full overflow-hidden mb-3">
                         <div className={`h-full ${gexSign ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{width: `${Math.min(100, (Math.abs(lvl.total_gex)/1000000)*10)}%`}} />
                      </div>
                      <div className="flex justify-between items-end relative z-10">
                        <div className="space-y-0.5">
                          <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest leading-none">Net GEX</div>
                          <div className={`text-sm font-mono font-black ${gexSign ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtGex(lvl.total_gex)}</div>
                        </div>
                        <div className="text-right space-y-0.5">
                           <div className="text-[9px] font-black text-zinc-600 uppercase tracking-widest leading-none">IV ATM</div>
                           <div className="text-sm font-mono font-black text-zinc-300">{(lvl.atm_iv * 100).toFixed(1)}%</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
           </ScrollArea>
           <div className="p-4 border-t border-white/5 bg-black/20">
              <div className="flex items-center justify-between text-[9px] font-black text-zinc-600 uppercase tracking-tighter">
                <span>Scanner Capacity</span>
                <span>Active 24/7</span>
              </div>
           </div>
        </div>

        {/* ── TACTICAL INTELLIGENCE (MAIN AREA) ────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 bg-gradient-to-br from-zinc-950 via-zinc-950 to-zinc-900 relative z-20">
           
           {/* Alert Overlay */}
           {activeAlert && (
             <div className={`absolute top-8 left-8 right-8 z-50 p-5 rounded-3xl border flex items-center justify-between shadow-2xl backdrop-blur-2xl animate-in slide-in-from-top-12 duration-700 ${
               activeAlert.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-100' :
               activeAlert.type === 'error' ? 'bg-rose-500/10 border-rose-500/40 text-rose-100' : 'bg-zinc-800/50 border-white/10 text-zinc-200'
             }`}>
                <div className="flex items-center gap-5 text-base font-black uppercase italic tracking-tight">
                  <div className={`p-2 rounded-xl ${activeAlert.type === 'success' ? 'bg-emerald-500/20' : 'bg-rose-500/20'}`}>
                    <AlertTriangle className="h-6 w-6" />
                  </div>
                  {activeAlert.message}
                </div>
                <Button variant="ghost" size="icon" className="rounded-full hover:bg-white/10 h-10 w-10" onClick={() => setActiveAlert(null)}><X size={20} /></Button>
             </div>
           )}

           <ScrollArea className="flex-1">
             <div className="p-10 space-y-10 max-w-[1700px] mx-auto animate-in fade-in duration-1000">
                
                {/* ── SECTOR OVERVIEW HEADER ── */}
                <div className="flex justify-between items-end pb-10 border-b border-white/5">
                  <div className="space-y-6">
                    <div className="flex items-center gap-4">
                       <h2 className="text-8xl font-black tracking-tighter uppercase italic text-white flex items-end gap-3 leading-none">
                          {activeDetail?.ticker}
                          <span className="text-2xl font-normal opacity-20 h-14 border-l border-white/20 pl-4 mb-2 not-italic">SECTOR ALPHA</span>
                       </h2>
                    </div>
                    <div className="flex items-center gap-12">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> <span className="text-[11px] font-black text-zinc-500 uppercase tracking-[0.2em]">MARK PRICE</span></div>
                        <div className="text-4xl font-mono font-black text-white">{activeDetail?.spot?.toFixed(2)}</div>
                      </div>
                      <div className="h-14 w-px bg-white/5" />
                      <div className="space-y-2">
                        <div className="flex items-center gap-2"><Droplets size={12} className="text-emerald-500" /> <span className="text-[11px] font-black text-zinc-600 uppercase tracking-[0.2em]">IMPLIED VOL</span></div>
                        <div className="text-4xl font-mono font-black text-zinc-400">{(activeDetail?.atm_iv * 100).toFixed(1)}<span className="text-xl opacity-30">%</span></div>
                      </div>
                      <div className="h-14 w-px bg-white/5" />
                      <div className="space-y-2">
                        <div className="flex items-center gap-2"><Gauge size={12} className="text-emerald-500" /> <span className="text-[11px] font-black text-zinc-600 uppercase tracking-[0.2em]">NET GEX DELTA</span></div>
                        <div className={`text-4xl font-mono font-black ${activeDetail?.total_gex >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>{fmtGex(activeDetail?.total_gex)}</div>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-4">
                    <div className={`px-10 py-6 rounded-[2.5rem] border-2 flex flex-col items-center gap-1 shadow-2xl backdrop-blur-xl ${getRegimeColor(activeDetail?.gex_regime)}`}>
                      <span className="text-[10px] font-black uppercase tracking-[0.3em] opacity-50 mb-1">Strategic Regime</span>
                      <span className="text-4xl font-black uppercase italic tracking-tighter">{activeDetail?.regime_label || "NEUTRAL"}</span>
                    </div>
                    {ms.directional_bias && (
                      <Badge className={`rounded-xl px-4 py-1 text-[10px] uppercase font-black tracking-widest ${ms.directional_bias === 'BULLISH' ? 'bg-emerald-500/20 text-emerald-400' : ms.directional_bias === 'BEARISH' ? 'bg-rose-500/20 text-rose-400' : 'bg-zinc-800 text-zinc-400'}`}>
                        {ms.directional_bias} BIAS
                      </Badge>
                    )}
                  </div>
                </div>

                {/* ── TACTICAL TILES ── */}
                 <TooltipProvider>
                 <div className="grid grid-cols-4 gap-6">
                  {[
                    { label: "Call Wall", val: activeDetail?.call_wall, icon: <ArrowUpRight className="h-5 w-5 text-emerald-400" />, sub: "Primary Resistance", color: "border-emerald-500/20 bg-emerald-500/5 text-emerald-200", tip: "The strike with the largest positive dealer gamma. Acts as a price ceiling because dealers sell futures as price rises toward it." },
                    { label: "Put Wall", val: activeDetail?.put_wall, icon: <ArrowDownRight className="h-5 w-5 text-rose-400" />, sub: "Primary Support", color: "border-rose-500/20 bg-rose-500/5 text-rose-200", tip: "The strike with the largest negative dealer gamma. Acts as a floor because dealers must sell more futures as price falls toward it to stay delta-neutral." },
                    { label: "Gamma Magnet", val: activeDetail?.gamma_magnet, icon: <Target className="h-5 w-5 text-sky-400" />, sub: "Gravity Point", color: "border-sky-500/20 bg-sky-500/5 text-sky-200", tip: "A level where Gamma flips or clusters significantly. Price is often 'pulled' toward these levels as dealers rehedge their positions." },
                    { label: "Zero Gamma", val: activeDetail?.zero_gamma, icon: <Zap className="h-5 w-5 text-amber-400" />, sub: "Volatility Flip", color: "border-amber-500/20 bg-amber-500/5 text-amber-200", tip: "The 'Gamma Flip' level. Below this, dealers are short gamma (hedge aggressively with the trend), leading to higher volatility. Above this, they are long gamma (hedge against the trend), suppressing volatility." },
                  ].map((item, i) => (
                    <UiTooltip key={i}>
                      <TooltipTrigger asChild>
                        <div className={`p-6 rounded-3xl border ${item.color} shadow-lg transition-all hover:scale-[1.03] group relative overflow-hidden cursor-help`}>
                          <div className="absolute -right-4 -top-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-700">{item.icon}</div>
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex flex-col">
                              <span className="text-[11px] font-black uppercase tracking-[0.15em] opacity-40">{item.label}</span>
                              <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">{item.sub}</span>
                            </div>
                            <div className="p-2 rounded-xl bg-white/5">{item.icon}</div>
                          </div>
                          <div className="text-3xl font-mono font-black tracking-tighter">{(item.val > activeDetail?.spot * 5 ? item.val / 10 : item.val)?.toLocaleString(undefined, {minimumFractionDigits: 1})}</div>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[250px] bg-zinc-900 border-emerald-500/30 text-emerald-100 p-4 rounded-xl shadow-2xl backdrop-blur-3xl animate-in fade-in zoom-in-95 duration-200">
                        <p className="text-sm font-bold leading-relaxed">{item.tip}</p>
                      </TooltipContent>
                    </UiTooltip>
                  ))}
                </div>
                </TooltipProvider>

                {/* ── ANALYTICS CORE (CHARTS & LADDER) ── */}
                <div className="grid grid-cols-12 gap-8">
                  
                  {/* CHART TOWER (8 Cols) */}
                  <div className="col-span-12 xl:col-span-8 flex flex-col gap-6">
                    <Card className="flex-1 bg-zinc-900/40 border-white/5 rounded-[3rem] p-8 backdrop-blur-3xl relative min-h-[650px] shadow-2xl">
                       <Tabs value={mainTab} onValueChange={(v:any) => setMainTab(v)} className="w-full h-full flex flex-col">
                          <div className="flex items-center justify-between mb-8">
                             <TabsList className="bg-black/40 border border-white/10 h-14 p-1.5 rounded-2xl">
                                <TabsTrigger value="exposure" className="px-8 rounded-xl font-black text-[10px] uppercase tracking-widest data-[state=active]:bg-emerald-500 data-[state=active]:text-black">GEX Exposure</TabsTrigger>
                                <TabsTrigger value="activity" className="px-8 rounded-xl font-black text-[10px] uppercase tracking-widest data-[state=active]:bg-emerald-500 data-[state=active]:text-black">Flow Activity</TabsTrigger>
                                <TabsTrigger value="trend" className="px-8 rounded-xl font-black text-[10px] uppercase tracking-widest data-[state=active]:bg-emerald-500 data-[state=active]:text-black">Time Decay</TabsTrigger>
                             </TabsList>

                                  <div className="flex items-center gap-6">
                                    <div className="flex flex-col gap-1 w-32 mr-4">
                                       <div className="flex items-center justify-between">
                                          <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Strike Range</span>
                                          <span className="text-[9px] font-mono font-bold text-emerald-400">±{strikeZoomRange}%</span>
                                       </div>
                                       <Slider 
                                          value={[strikeZoomRange]} 
                                          onValueChange={(v) => setStrikeZoomRange(v[0])} 
                                          min={1} max={15} step={1}
                                          className="h-4"
                                       />
                                    </div>
                                    {mainTab === 'exposure' && (
                                      <div className="flex bg-black/40 p-1.5 rounded-xl border border-white/10">
                                        {['callsPuts', 'net', 'absolute'].map(m => (
                                          <Button key={m} size="sm" variant={exposureMode === m ? 'default' : 'ghost'} onClick={() => setExposureMode(m as any)} className={`text-[9px] font-black h-8 px-4 rounded-lg uppercase transition-all ${exposureMode === m ? 'bg-emerald-500 text-black' : 'text-zinc-500 hover:text-white'}`}>{m}</Button>
                                        ))}
                                      </div>
                                    )}
                                    {mainTab === 'activity' && (
                                      <div className="flex bg-black/40 p-1.5 rounded-xl border border-white/10">
                                        {['volume', 'oi'].map(m => (
                                          <Button key={m} size="sm" variant={activityMode === m ? 'default' : 'ghost'} onClick={() => setActivityMode(m as any)} className={`text-[9px] font-black h-8 px-4 rounded-lg uppercase transition-all ${activityMode === m ? 'bg-emerald-500 text-black' : 'text-zinc-500 hover:text-white'}`}>{m}</Button>
                                        ))}
                                      </div>
                                    )}
                                 </div>
                          </div>
                          
                          <div className="flex-1 relative">
                            {zoomedProfile.length > 0 ? (
                               <div className="w-full h-full min-h-[450px]">
                                <ResponsiveContainer width="100%" height="100%">
                                  {mainTab === 'exposure' ? (
                                    exposureMode === 'callsPuts' ? (
                                      <BarChart layout="vertical" data={zoomedProfile.map((p: any) => ({ ...p, put_gex_down: -p.put_gex }))} margin={{ top: 20, right: 40, left: 60, bottom: 0 }}>
                                        <XAxis type="number" hide domain={['auto', 'auto']} />
                                        <YAxis dataKey="strike" type="category" tick={{ fontSize: 10, fill: '#71717a', fontWeight: 900 }} axisLine={false} tickLine={false} tickFormatter={(v) => v.toLocaleString()} width={60} interval={Math.max(0, Math.floor(zoomedProfile.length / 15))} />
                                        <RechartsTooltip cursor={{fill: 'rgba(255,255,255,0.03)'}} contentStyle={{backgroundColor: '#09090b', border: '1px solid #18181b', borderRadius: '16px', boxShadow: '0 20px 50px rgba(0,0,0,0.5)'}} />
                                        <ReferenceLine x={0} stroke="#27272a" strokeWidth={2} />
                                        <ReferenceLine y={drillSpot > activeDetail?.spot * 5 ? drillSpot / 10 : drillSpot} stroke="#3b82f6" strokeWidth={2} strokeDasharray="8 8" label={{ value: 'SPOT', position: 'right', fill: '#3b82f6', fontSize: 10, fontWeight: 900 }} />
                                        <Bar dataKey="call_gex" fill="#10b981" radius={[0, 4, 4, 0]} />
                                        <Bar dataKey="put_gex_down" fill="#f43f5e" radius={[4, 0, 0, 4]} />
                                      </BarChart>
                                    ) : exposureMode === 'net' ? (
                                       <BarChart layout="vertical" data={zoomedProfile} margin={{ top: 20, right: 40, left: 60, bottom: 0 }}>
                                          <XAxis type="number" hide domain={['auto', 'auto']} />
                                          <YAxis dataKey="strike" type="category" tick={{ fontSize: 10, fill: '#71717a', fontWeight: 900 }} axisLine={false} tickLine={false} width={60} interval={Math.max(0, Math.floor(zoomedProfile.length / 15))} />
                                          <RechartsTooltip cursor={{fill: 'rgba(255,255,255,0.03)'}} contentStyle={{backgroundColor: '#09090b', border: '1px solid #18181b', borderRadius: '16px'}} />
                                          <ReferenceLine x={0} stroke="#27272a" strokeWidth={1} />
                                          <ReferenceLine y={drillSpot > activeDetail?.spot * 5 ? drillSpot / 10 : drillSpot} stroke="#3b82f6" strokeWidth={2} strokeDasharray="8 8" />
                                          <Bar dataKey="net_gex">
                                            {zoomedProfile.map((e: any, i: number) => <Cell key={i} fill={e.net_gex >= 0 ? '#10b981' : '#f43f5e'} />)}
                                          </Bar>
                                       </BarChart>
                                    ) : (
                                      <BarChart layout="vertical" data={zoomedProfile.map((p: any) => ({ ...p, abs_gex: Math.abs(p.net_gex) }))} margin={{ top: 20, right: 40, left: 60, bottom: 0 }}>
                                        <XAxis type="number" hide />
                                        <YAxis dataKey="strike" type="category" tick={{ fontSize: 10, fill: '#71717a', fontWeight: 900 }} axisLine={false} tickLine={false} width={60} interval={Math.max(0, Math.floor(zoomedProfile.length / 15))} />
                                        <RechartsTooltip cursor={{fill: 'rgba(255,255,255,0.03)'}} contentStyle={{backgroundColor: '#09090b', border: '1px solid #18181b', borderRadius: '16px'}} />
                                        <Bar dataKey="abs_gex" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                                      </BarChart>
                                    )
                                  ) : mainTab === 'activity' ? (
                                    <BarChart layout="vertical" data={zoomedProfile} margin={{ top: 20, right: 40, left: 60, bottom: 0 }}>
                                      <XAxis type="number" hide />
                                      <YAxis dataKey="strike" type="category" tick={{ fontSize: 10, fill: '#71717a', fontWeight: 900 }} width={60} interval={Math.max(0, Math.floor(zoomedProfile.length / 15))} />
                                      <RechartsTooltip contentStyle={{backgroundColor: '#09090b', border: '1px solid #18181b', borderRadius: '16px'}} />
                                      <ReferenceLine y={drillSpot > activeDetail?.spot * 5 ? drillSpot / 10 : drillSpot} stroke="#3b82f6" strokeWidth={2} strokeDasharray="8 8" />
                                      <Bar dataKey={activityMode === 'volume' ? 'call_vol' : 'call_oi'} fill="#10b981" radius={[0, 4, 4, 0]} />
                                      <Bar dataKey={activityMode === 'volume' ? 'put_vol' : 'put_oi'} fill="#f43f5e" radius={[0, 4, 4, 0]} />
                                    </BarChart>
                                  ) : (
                                    <AreaChart data={activeTrendData}>
                                      <defs>
                                        <linearGradient id="colorGexFade" x1="0" y1="0" x2="0" y2="1">
                                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                        </linearGradient>
                                      </defs>
                                      <XAxis dataKey="timestamp" hide />
                                      <YAxis hide />
                                      <RechartsTooltip contentStyle={{backgroundColor: '#09090b', border: '1px solid #18181b', borderRadius: '16px'}} />
                                      <Area type="monotone" dataKey="total_gex" stroke="#10b981" fillOpacity={1} fill="url(#colorGexFade)" strokeWidth={4} />
                                    </AreaChart>
                                  )}
                                </ResponsiveContainer>
                               </div>
                            ) : (
                              <div className="h-full flex flex-col items-center justify-center gap-6 opacity-20">
                                <Activity className="h-20 w-20 animate-pulse text-emerald-500" />
                                <span className="text-sm font-black tracking-[0.3em] uppercase">Sector Profile Offline</span>
                              </div>
                            )}
                          </div>
                          
                          {/* Advanced Marker Stats */}
                          <TooltipProvider>
                          <div className="mt-8 grid grid-cols-4 gap-4 px-4 py-6 bg-black/40 rounded-3xl border border-white/5">
                             {[
                               { label: "Call Centroid", val: ms.call_volume_centroid, icon: <Flame size={12} className="text-orange-400" />, tip: "The strike where the most Call trading activity is centered (VWAP of strikes)." },
                               { label: "Put Centroid", val: ms.put_volume_centroid, icon: <Flame size={12} className="text-sky-400" />, tip: "The strike where the most Put trading activity is centered (VWAP of strikes)." },
                               { label: "Net Vanna", val: ms.net_vanna_exposure, icon: <Droplets size={12} className="text-indigo-400" />, fmt: true, tip: "Vanna is the sensitivity of Delta to Volatility shifts. High positive Vanna means if IV falls, dealers buy futures to stay neutral." },
                               { label: "Pin Concentration", val: (ms.pin_odds * 100).toFixed(1) + "%", icon: <Hash size={12} className="text-emerald-400" />, tip: "The statistical probability of price finishing near the current strike cluster at expiry." },
                             ].map((st, i) => (
                               <UiTooltip key={i}>
                                 <TooltipTrigger asChild>
                                   <div className="flex flex-col gap-1 border-r last:border-0 border-white/5 px-4 cursor-help group">
                                      <div className="flex items-center gap-2 opacity-50"><span className="text-[10px] font-black uppercase tracking-widest group-hover:text-emerald-400 transition-colors">{st.label}</span> {st.icon}</div>
                                      <div className="text-lg font-mono font-black">{typeof st.val === 'number' ? (st.fmt ? fmtGex(st.val) : st.val.toLocaleString()) : st.val || "—"}</div>
                                   </div>
                                 </TooltipTrigger>
                                 <TooltipContent className="bg-zinc-900 border-zinc-700 p-3 max-w-[200px]">
                                   <p className="text-xs font-medium leading-relaxed">{st.tip}</p>
                                 </TooltipContent>
                               </UiTooltip>
                             ))}
                          </div>
                          </TooltipProvider>
                       </Tabs>
                    </Card>
                    
                    {/* Footnotes / Additional Info */}
                    <div className="grid grid-cols-3 gap-6">
                       <Card className="bg-zinc-900/30 border-white/5 rounded-3xl p-6 flex flex-col gap-2">
                          <div className="flex items-center gap-2 mb-2"><TrendingUp size={14} className="text-emerald-500" /> <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Vol Nodes (Upper)</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Vanna Node</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Vanna Call Node")?.toLocaleString()}</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Charm Node</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Charm Call Node")?.toLocaleString()}</span></div>
                       </Card>
                       <Card className="bg-zinc-900/30 border-white/5 rounded-3xl p-6 flex flex-col gap-2">
                          <div className="flex items-center gap-2 mb-2"><TrendingDown size={14} className="text-rose-500" /> <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Vol Nodes (Lower)</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Vanna Node</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Vanna Put Node")?.toLocaleString()}</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Charm Node</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Charm Put Node")?.toLocaleString()}</span></div>
                       </Card>
                       <Card className="bg-zinc-900/30 border-white/5 rounded-3xl p-6 flex flex-col gap-2">
                          <div className="flex items-center gap-2 mb-2"><Droplets size={14} className="text-sky-500" /> <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Moneyness</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Delta 25D Call</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Skew Pivot Call 25D")?.toLocaleString()}</span></div>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">Delta 25D Put</span> <span className="text-sm font-bold font-mono">{getLevelValue(activeDetail?.ticker, "Skew Pivot Put 25D")?.toLocaleString()}</span></div>
                       </Card>
                    </div>
                  </div>

                  {/* INFO TOWER (4 Cols) */}
                  <div className="col-span-12 xl:col-span-4 flex flex-col min-h-[600px]">
                      <Tabs value={rightTab} onValueChange={(v:any) => setRightTab(v)} className="flex-1 flex flex-col border border-white/5 bg-zinc-900/40 rounded-[3rem] overflow-hidden shadow-2xl backdrop-blur-xl">
                         <TabsList className="w-full bg-black/40 border-b border-white/10 h-16 rounded-none px-10 justify-start gap-10">
                            <TabsTrigger value="ladder" className="px-0 py-2 border-b-2 border-transparent data-[state=active]:bg-transparent data-[state=active]:text-emerald-500 data-[state=active]:border-emerald-500 rounded-none font-black text-[11px] uppercase tracking-widest transition-all">Ladder</TabsTrigger>
                            <TabsTrigger value="briefing" className="px-0 py-2 border-b-2 border-transparent data-[state=active]:bg-transparent data-[state=active]:text-emerald-500 data-[state=active]:border-emerald-500 rounded-none font-black text-[11px] uppercase tracking-widest transition-all">Briefing</TabsTrigger>
                            <TabsTrigger value="nodes" className="px-0 py-2 border-b-2 border-transparent data-[state=active]:bg-transparent data-[state=active]:text-emerald-500 data-[state=active]:border-emerald-500 rounded-none font-black text-[11px] uppercase tracking-widest transition-all">Leaderboard</TabsTrigger>
                         </TabsList>
                         
                         <TabsContent value="ladder" className="flex-1 m-0 overflow-hidden relative">
                            <div className="absolute top-0 bottom-0 left-12 w-px bg-white/5 pointer-events-none" />
                            <ScrollArea className="h-full">
                               <div className="divide-y divide-white/5 py-4">
                                  {priceLadder.map((lvl: any, i: number) => {
                                    const isSpot = lvl.type === 'spot';
                                    return (
                                      <div key={i} className={`flex items-center justify-between px-10 py-5 transition-all hover:bg-white/5 relative group ${isSpot ? 'bg-emerald-500/10 py-10 my-2 shadow-[0_0_50px_rgba(16,185,129,0.1)] z-10' : ''}`}>
                                        {isSpot && <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)]" />}
                                        <div className="flex flex-col gap-1.5">
                                           {lvl.labels.map((l: string) => (
                                             <span key={l} className={`text-[10px] font-black uppercase tracking-widest leading-none ${isSpot ? 'text-emerald-400' : lvl.type === 'resistance' ? 'text-emerald-500/50' : lvl.type === 'support' ? 'text-rose-500/50' : 'text-zinc-600'}`}>
                                               {l}
                                             </span>
                                           ))}
                                        </div>
                                        <span className={`font-mono font-black leading-none ${isSpot ? 'text-4xl text-emerald-400' : 'text-base text-zinc-300'}`}>
                                          {lvl.price.toLocaleString(undefined, {minimumFractionDigits: 1})}
                                        </span>
                                      </div>
                                    );
                                  })}
                               </div>
                            </ScrollArea>
                         </TabsContent>

                         <TabsContent value="briefing" className="flex-1 m-0 p-10 overflow-y-auto bg-black/10">
                            <div className="space-y-8">
                               {(() => {
                                  const raw = ms?.coach_note;
                                  const lines = Array.isArray(raw) ? raw : typeof raw === 'string' ? raw.split('\n').filter(Boolean) : [];
                                  if (!lines.length) return <div className="text-zinc-700 italic text-sm tracking-widest text-center mt-32 flex flex-col items-center gap-4"><Info size={40} className="text-zinc-800" /> UNABLE TO RETRIEVE INTEL</div>;
                                  
                                  return lines.map((l: string, i: number) => {
                                    const fixed = fixText(l, activeDetail?.ticker, activeDetail?.spot);
                                    const isHeader = fixed.startsWith('**') && fixed.endsWith('**');
                                    return (
                                      <p key={i} className={`text-[13px] leading-relaxed tracking-wide ${isHeader ? 'text-emerald-400 font-extrabold uppercase mt-12 mb-4 border-l-2 border-emerald-500/50 pl-4 bg-emerald-500/5 py-1' : 'text-zinc-400 font-medium'}`}>
                                        {fixed.replace(/\*\*/g, '')}
                                      </p>
                                    );
                                  });
                               })()}
                            </div>
                         </TabsContent>

                         <TabsContent value="nodes" className="flex-1 m-0 p-8 overflow-y-auto">
                             <div className="space-y-10">
                                <div>
                                  <div className="flex items-center justify-between mb-4 px-2">
                                     <h3 className="text-xs font-black uppercase tracking-[0.3em] text-zinc-500">Tiered Institutional Walls</h3>
                                     <div className="flex gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                        <div className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                     </div>
                                  </div>
                                  <div className="grid grid-cols-1 gap-4">
                                     <div className="space-y-3">
                                        {rankedWalls.calls.map((w: any, idx: number) => (
                                          <div key={idx} className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/10 flex justify-between items-center group hover:bg-emerald-500/10 transition-colors">
                                             <div className="flex flex-col">
                                                <span className="text-[9px] font-black text-emerald-500 uppercase tracking-widest">Call Tier {idx+1}</span>
                                                <span className="text-lg font-mono font-black text-white">{(w.strike > activeDetail?.spot * 5 ? w.strike / 10 : w.strike).toLocaleString()}</span>
                                             </div>
                                             <div className="text-right">
                                                <div className="text-[9px] font-black text-emerald-800 uppercase tracking-widest leading-none">+{fmtGex(w.call_gex)}</div>
                                                <div className="text-[8px] font-bold text-zinc-600 mt-1">{((w.call_gex / (activeDetail?.total_gex || 1)) * 100).toFixed(1)}% Weight</div>
                                             </div>
                                          </div>
                                        ))}
                                     </div>
                                     <div className="space-y-3">
                                        {rankedWalls.puts.map((w: any, idx: number) => (
                                          <div key={idx} className="p-4 rounded-2xl bg-rose-500/5 border border-rose-500/10 flex justify-between items-center group hover:bg-rose-500/10 transition-colors">
                                             <div className="flex flex-col">
                                                <span className="text-[9px] font-black text-rose-500 uppercase tracking-widest">Put Tier {idx+1}</span>
                                                <span className="text-lg font-mono font-black text-white">{(w.strike > activeDetail?.spot * 5 ? w.strike / 10 : w.strike).toLocaleString()}</span>
                                             </div>
                                             <div className="text-right">
                                                <div className="text-[9px] font-black text-rose-800 uppercase tracking-widest leading-none">{fmtGex(w.put_gex)}</div>
                                                <div className="text-[8px] font-bold text-zinc-600 mt-1">{((Math.abs(w.put_gex) / (Math.abs(activeDetail?.total_gex) || 1)) * 100).toFixed(1)}% Weight</div>
                                             </div>
                                          </div>
                                        ))}
                                     </div>
                                  </div>
                                </div>

                                <div className="pt-6 border-t border-white/5">
                                   <div className="flex items-center gap-2 mb-4 px-2">
                                      <TrendingUp size={12} className="text-zinc-500" />
                                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-600">Global Strike Map</h3>
                                   </div>
                                   <div className="space-y-2">
                                      {topStrikes.map((s: any, idx: number) => (
                                         <div key={idx} className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-white/5 rounded-lg border border-transparent hover:border-white/5 group">
                                            <span className="font-mono font-black text-zinc-400 group-hover:text-white transition-colors">{(s.strike > activeDetail?.spot * 5 ? s.strike / 10 : s.strike).toLocaleString()}</span>
                                            <div className="flex items-center gap-4">
                                               <span className={`font-mono font-bold text-[10px] ${s.net_gex >= 0 ? 'text-emerald-500/60' : 'text-rose-400/60'}`}>{fmtGex(s.net_gex)}</span>
                                               <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                                                  <div className={`h-full ${s.net_gex >= 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{width: `${Math.min(100, Math.abs(s.net_gex / (activeDetail?.total_gex || 1)) * 100)}%`}} />
                                               </div>
                                            </div>
                                         </div>
                                      ))}
                                   </div>
                                </div>
                             </div>
                          </TabsContent>
                      </Tabs>
                  </div>
                </div>
             </div>
           </ScrollArea>
           
           {/* Navigation Hint */}
           <div className="absolute bottom-6 right-10 flex items-center gap-4 text-[9px] font-black text-zinc-700 tracking-[0.3em] uppercase opacity-40">
              <span className="flex items-center gap-1"><Droplets size={10} /> Liquidity Map</span>
              <span className="flex items-center gap-1"><TrendingUp size={10} /> Volatility Corridor</span>
           </div>
        </div>
      </div>
    </div>
  );
}
