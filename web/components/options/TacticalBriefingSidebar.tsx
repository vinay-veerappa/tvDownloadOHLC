"use client";

import React from 'react';
import { Info, AlertTriangle, ShieldCheck, Activity, ChevronRight } from 'lucide-react';
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { HighlightNarrative } from "./HighlightNarrative";

interface TacticalBriefingSidebarProps {
  activeDetail: any;
  ms: any;
  isOpen: boolean;
}

/**
 * Professional right-hand dashboard for narrative trading.
 * Houses market structure context, volatility risk warnings, and actionable directives.
 */
export const TacticalBriefingSidebar = ({ activeDetail, ms, isOpen }: TacticalBriefingSidebarProps) => {
  if (!activeDetail) return null;

  return (
    <aside 
      className={`border-l border-white/5 flex flex-col bg-zinc-950/95 backdrop-blur-3xl shrink-0 transition-all duration-500 ease-in-out z-40 h-screen shadow-2xl relative ${
        isOpen ? 'w-[450px] translate-x-0 opacity-100' : 'w-0 translate-x-full opacity-0 pointer-events-none'
      }`}
    >
      {/* Sidebar Header */}
      <div className="p-8 border-b border-white/5 flex items-center justify-between bg-black/20">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 bg-emerald-500/10 rounded-2xl flex items-center justify-center border border-emerald-500/10">
            <Info className="text-emerald-500" size={18} />
          </div>
          <div>
            <h3 className="text-[10px] font-black uppercase tracking-[0.25em] text-zinc-500 mb-0.5">Stream Intelligence</h3>
            <div className="text-sm font-black tracking-tight text-white uppercase">Tactical Briefing</div>
          </div>
        </div>
        <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[9px] font-black px-4 py-1.5 uppercase rounded-full">Live</Badge>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-10 space-y-12 pb-32">
          
          {/* Macro Thesis */}
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Macro Narrative</div>
            </div>
            <p className="text-lg font-bold text-zinc-100 leading-relaxed border-l-4 border-emerald-500 pl-8 py-6 bg-emerald-500/5 rounded-r-[2rem] pr-8 italic shadow-inner">
               <HighlightNarrative 
                 text={Array.isArray(ms.coach_note) ? ms.coach_note[0] : "Synthesizing market context..."} 
                 ticker={activeDetail?.ticker} 
                 spot={activeDetail?.spot} 
               />
            </p>
          </div>

          {/* Volatility Status Card */}
          <Card className={`p-10 rounded-[2.5rem] border overflow-hidden relative shadow-2xl ${
            activeDetail?.total_gex < -1e9 
              ? 'bg-rose-500/5 border-rose-500/20 text-rose-400' 
              : (activeDetail?.total_gex > 0 ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-zinc-900 border-white/5 text-zinc-400')
          }`}>
            <div className="absolute top-0 right-0 p-8 opacity-20 pointer-events-none">
              {activeDetail?.total_gex < -1e9 ? <AlertTriangle size={64} /> : <ShieldCheck size={64} />}
            </div>
            
            <div className="flex items-center gap-4 mb-6 relative z-10">
              {activeDetail?.total_gex < -1e9 ? <AlertTriangle size={20} /> : (activeDetail?.total_gex > 0 ? <ShieldCheck size={20} /> : <Activity size={20} />)}
              <span className="font-black text-xs uppercase tracking-[0.2em] whitespace-nowrap">
                {activeDetail?.total_gex < -1e9 ? 'High Move Probability' : (activeDetail?.total_gex > 0 ? 'Compression Expected' : 'Neutral Position')}
              </span>
            </div>
            <p className="text-sm font-bold tracking-tight leading-relaxed max-w-[85%] relative z-10">
               {activeDetail?.total_gex < -1e9 
                  ? "Net GEX below -1B warns of high volatility expansion probability (>±1.5%). Defensive trade configuration recommended." 
                  : (activeDetail?.total_gex > 0 
                     ? "Positive GEX environment indicates structural stability and mean-reversion probability." 
                     : "Standard volatility environment with distributed liquidity nodes.")}
            </p>
          </Card>

          {/* Directives List */}
          <div className="space-y-8">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Tactical Directives</div>
            </div>
            <div className="space-y-4">
               {(Array.isArray(ms.coach_note) ? ms.coach_note.slice(1, 15) : ["Awaiting system intelligence..."]).map((note: string, idx: number) => (
                  <div 
                    key={idx} 
                    className="flex gap-6 p-8 rounded-[2rem] bg-zinc-900/40 border border-white/5 hover:border-emerald-500/30 transition-all group shadow-sm hover:shadow-emerald-500/10 cursor-default"
                  >
                     <div className="text-emerald-500 font-black text-xs shrink-0 mt-0.5 opacity-40 group-hover:opacity-100 transition-opacity">
                       {String(idx+1).padStart(2,'0')}
                     </div>
                     <p className="text-xs font-bold text-zinc-400 leading-relaxed group-hover:text-zinc-100 transition-colors">
                       <HighlightNarrative text={note} ticker={activeDetail?.ticker} spot={activeDetail?.spot} />
                     </p>
                  </div>
               ))}
            </div>
          </div>
        </div>
      </ScrollArea>

      {/* Footer / Status */}
      <div className="p-8 border-t border-white/5 bg-black/20 mt-auto">
        <div className="flex items-center justify-between text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em]">
          <span>Institutional Feed</span>
          <span className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Connected
          </span>
        </div>
      </div>
    </aside>
  );
};
