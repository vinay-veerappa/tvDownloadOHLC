"use client"
 
import React, { useMemo } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  Info, 
  ShieldCheck, 
  AlertTriangle, 
  Activity,
  ChevronRight
} from 'lucide-react'
 
// Sub-component for highlighted text
const HighlightNarrative = ({ text, ticker, spot }: { text: string, ticker?: string, spot?: number }) => {
  if (!text) return null;
  const parts = text.split(/(\d+\.?\d*|SPY|QQQ|IWM|NVDA|AAPL|TSLA|BTC|ETH|GEX|DEX|Vanna|Charm|Gamma)/gi);
  return (
    <>
      {parts.map((part, i) => {
        const lower = part.toLowerCase();
        const isTicker = ['spy','qqq','iwm','nvda','aapl','tsla','btc','eth'].includes(lower);
        const isConcept = ['gex','dex','vanna','charm','gamma'].includes(lower);
        const isNum = !isNaN(parseFloat(part)) && isFinite(part as any);
 
        if (isTicker) return <span key={i} className="text-emerald-400 font-bold px-1.5 py-0.5 bg-emerald-500/10 rounded-md border border-emerald-500/20 shadow-sm">{part}</span>;
        if (isConcept) return <span key={i} className="text-indigo-400 font-bold px-1">{part}</span>;
        if (isNum) return <span key={i} className="font-mono text-white font-black drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">{part}</span>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};
 
interface TacticalBriefingSidebarProps {
  activeDetail: any
  ms: any
  isOpen: boolean
  onToggle: () => void
}

export function TacticalBriefingSidebar({ activeDetail, ms, isOpen, onToggle }: TacticalBriefingSidebarProps) {
  const narrative = useMemo(() => {
    if (Array.isArray(ms.coach_note) && ms.coach_note.length > 0) return ms.coach_note;
    
    // Fallback narrative based on institutional telemetry
    const bias = activeDetail?.directional_bias || "NEUTRAL";
    const regime = activeDetail?.gex_regime || "UNDEFINED";
    const label = activeDetail?.regime_label || "STABILIZING";
    
    return [
      `System detecting ${bias} bias within the ${label} (${regime} GEX regime).`,
      `Dealers are positioning around the ${activeDetail?.call_wall} Call Wall and ${activeDetail?.put_wall} Put Wall.`,
      `Zero Gamma level at ${activeDetail?.zero_gamma} remains the critical volatility flip point for ${activeDetail?.ticker}.`,
      "Monitor institutional flow for delta-neutral rebalancing at session open."
    ];
  }, [ms.coach_note, activeDetail]);

  return (
    <aside 
      className={`border-l border-white/5 flex flex-col bg-zinc-950/80 backdrop-blur-3xl shrink-0 transition-all duration-500 ease-in-out z-40 overflow-hidden ${
        isOpen ? 'w-[450px] translate-x-0 opacity-100' : 'w-0 translate-x-full opacity-0 pointer-events-none'
      }`}
    >
      <ScrollArea className="flex-1">
        <div className="p-8 space-y-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-emerald-500/10 rounded-xl flex items-center justify-center border border-emerald-500/20 shadow-inner">
                <Info className="text-emerald-500" size={18} />
              </div>
              <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-400">Tactical Briefing</h3>
            </div>
            <div className="flex items-center gap-4">
              <Badge className="bg-emerald-500 text-black border-none text-[8px] font-black px-3 py-1 uppercase shadow-[0_0_15px_rgba(16,185,129,0.3)]">INTELLIGENCE ACTIVE</Badge>
              <button 
                onClick={onToggle}
                className="h-8 w-8 rounded-lg bg-zinc-900 border border-white/5 flex items-center justify-center text-zinc-500 hover:text-emerald-500 hover:border-emerald-500/20 transition-all group"
                title="Collapse Sidebar (>>)"
              >
                <ChevronRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          </div>

          {/* Institutional Alert Card */}
          <Card className={`p-8 rounded-[2.5rem] border ${activeDetail?.total_gex < -1e9 ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : (activeDetail?.total_gex > 0 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-zinc-900 border-white/5 text-zinc-400')} shadow-2xl backdrop-blur-xl relative overflow-hidden group`}>
            <div className="flex items-center gap-3 mb-4">
              {activeDetail?.total_gex < -1e9 ? <AlertTriangle size={18} /> : (activeDetail?.total_gex > 0 ? <ShieldCheck size={18} /> : <Activity size={18} />)}
              <span className="font-black text-[10px] uppercase tracking-[0.15em]">
                {activeDetail?.total_gex < -1e9 ? 'High Move Probability' : (activeDetail?.total_gex > 0 ? 'Compression Expected' : 'Neutral Position')}
              </span>
            </div>
            <p className="text-sm font-bold tracking-tight leading-relaxed text-white/80">
              {activeDetail?.total_gex < -1e9 
                ? "Total GEX warns of potential market moves > ±1.0% today. Dealers are short gamma and will chase volatility." 
                : (activeDetail?.total_gex > 0 
                  ? "Positive GEX indicates increased probability of market moves < ±0.5%. Dealers will absorb rallies and bid dips." 
                  : "Standard volatility environment with symmetrical risk profile.")}
            </p>
          </Card>

          {/* Macro Thesis */}
          <div className="space-y-6">
            <div className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.3em]">Macro Narrative</div>
            <p className="text-base font-bold text-zinc-100 leading-relaxed border-l-4 border-emerald-500 pl-6 py-6 bg-emerald-500/5 rounded-r-3xl pr-6 italic group hover:bg-emerald-500/10 transition-colors">
              <HighlightNarrative text={narrative[0]} ticker={activeDetail?.ticker} spot={activeDetail?.spot} />
            </p>
          </div>

          {/* Tactical Directives */}
          <div className="space-y-8">
            <div className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.3em]">Execution Directives</div>
            <div className="space-y-5">
              {narrative.slice(1).map((note: string, idx: number) => (
                <div key={idx} className="flex gap-6 p-6 rounded-[2rem] bg-zinc-900/50 border border-white/5 hover:border-emerald-500/20 transition-all group shadow-sm hover:shadow-emerald-500/5 hover:-translate-y-1 duration-300">
                  <div className="text-emerald-500 font-black text-xs shrink-0 mt-0.5 opacity-40 group-hover:opacity-100 transition-opacity">{String(idx+1).padStart(2,'0')}</div>
                  <p className="text-xs font-bold text-zinc-300 leading-relaxed group-hover:text-white transition-colors">
                    <HighlightNarrative text={note} ticker={activeDetail?.ticker} spot={activeDetail?.spot} />
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  )
}
