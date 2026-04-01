"use client";

import React from 'react';
import { ShieldCheck, AlertTriangle, Activity, Target, Gauge } from 'lucide-react';
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ActiveMetricsHUDProps {
  detail: any;
}

/**
 * Compact, high-visibility dashboard for key Greeks.
 * Floats at the top of the chart for immediate situational awareness.
 */
export const ActiveMetricsHUD = ({ detail }: ActiveMetricsHUDProps) => {
  if (!detail) return null;
  
  const gexVal = detail.total_gex || 0;
  const regimeColor = gexVal < -1e9 ? 'text-rose-500' : (gexVal > 0 ? 'text-emerald-500' : 'text-amber-500');
  const regimeBg = gexVal < -1e9 ? 'bg-rose-500/10 border-rose-500/20' : (gexVal > 0 ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-amber-500/10 border-amber-500/20');
  
  const metrics = [
    { 
      label: 'GEX REGIME', 
      value: detail.gex_regime || 'NEUTRAL', 
      color: regimeColor,
      icon: gexVal < -1e9 ? <AlertTriangle size={12} className="text-rose-500 animate-pulse" /> : <ShieldCheck size={12} className="text-emerald-500" />
    },
    { 
      label: 'WALL DIST', 
      value: `${Math.abs(((detail.spot - detail.call_wall)/detail.spot)*100).toFixed(1)}% to CW`, 
      color: 'text-zinc-400',
      icon: <Target size={12} className="text-blue-400" />
    },
    { 
      label: 'GAMMA FLIP', 
      value: detail.zero_gamma ? `${Math.abs(((detail.spot - detail.zero_gamma)/detail.spot)*100).toFixed(1)}% to Flip` : 'N/A', 
      color: 'text-amber-400',
      icon: <Gauge size={12} className="text-amber-400" />
    },
    { 
      label: 'BIAS', 
      value: detail.directional_bias || 'NEUTRAL', 
      color: detail.directional_bias === 'BULLISH' ? 'text-emerald-400' : 'text-rose-400',
      icon: <Activity size={12} />
    }
  ];

  return (
    <div className="flex items-center gap-6 bg-zinc-950/90 backdrop-blur-3xl border border-white/10 px-6 py-4 rounded-3xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.8)] border shadow-emerald-500/5 animate-in fade-in zoom-in-95 duration-500">
      {metrics.map((m, i) => (
        <div key={i} className="flex items-center gap-4 group">
          <div className="p-2 bg-white/5 rounded-xl group-hover:bg-white/10 transition-colors">
            {m.icon}
          </div>
          <div className="flex flex-col">
            <span className="text-[8px] font-black tracking-[0.25em] text-zinc-600 uppercase mb-0.5">{m.label}</span>
            <span className={`text-[11px] font-black uppercase tracking-tight ${m.color}`}>{m.value}</span>
          </div>
          {i < metrics.length - 1 && <div className="h-6 w-[1px] bg-white/5 mx-2" />}
        </div>
      ))}
    </div>
  );
};
