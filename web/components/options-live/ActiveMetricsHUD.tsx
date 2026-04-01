"use client"

import React from 'react'
import { Card } from '@/components/ui/card'
import { Activity, ShieldCheck, AlertTriangle } from 'lucide-react'

interface ActiveMetricsHUDProps {
  activeDetail: any
}

const fmtGex = (val: number | undefined) => {
  if (val === undefined || isNaN(val)) return '—'
  const abs = Math.abs(val)
  if (abs >= 1e9) return (val / 1e9).toFixed(2) + 'B'
  if (abs >= 1e6) return (val / 1e6).toFixed(1) + 'M'
  if (abs >= 1e3) return (val / 1e3).toFixed(1) + 'K'
  return val.toFixed(0)
}

export function ActiveMetricsHUD({ activeDetail }: ActiveMetricsHUDProps) {
  if (!activeDetail) return null;

  const gexValue = activeDetail.total_gex || 0;
  const isHighMove = gexValue < -1e9;
  const isPositive = gexValue > 0;

  return (
    <div className="p-8 border-b border-white/5 bg-zinc-950/40 backdrop-blur-3xl shrink-0 z-40">
      <div className="grid grid-cols-5 gap-8">
        {/* Total GEX Telemetry */}
        <div className="col-span-1 border-r border-white/5 pr-8 group">
          <div className="flex items-center gap-2 mb-2">
            <Activity size={12} className={isPositive ? 'text-emerald-500' : 'text-rose-500'} />
            <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em] group-hover:text-zinc-300 transition-colors">Total Net GEX</span>
          </div>
          <div className={`text-4xl font-mono font-black tracking-tighter transition-all duration-500 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fmtGex(gexValue)}
          </div>
          <p className="text-[9px] font-bold text-zinc-600 mt-2 uppercase tracking-widest leading-relaxed">
            {isHighMove ? 'Vol Amplification Zone' : isPositive ? 'Volatility Suppression' : 'Neutral Dispersion'}
          </p>
        </div>

        {/* GAMMA FLIP */}
        <div className="col-span-1 border-r border-white/5 pr-8 group">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck size={12} className="text-amber-500/50" />
            <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.2em]">Zero Gamma Flip</span>
          </div>
          <div className="text-4xl font-mono font-black tracking-tighter text-white/90">
             {activeDetail.zero_gamma ? activeDetail.zero_gamma.toFixed(2) : '—'}
          </div>
          <div className="flex items-center gap-2 mt-2">
             <div className="h-1 flex-1 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                   className="h-full bg-amber-500 transition-all duration-1000" 
                   style={{ width: `${Math.min(100, Math.abs((activeDetail.spot - activeDetail.zero_gamma) / activeDetail.spot) * 1000)}%` }} 
                />
             </div>
             <span className="text-[9px] font-black text-amber-500">
               {activeDetail.zero_gamma ? (Math.abs((activeDetail.spot - activeDetail.zero_gamma) / activeDetail.spot) * 100).toFixed(1) : 0}%
             </span>
          </div>
        </div>

        {/* TOP HUD CARDS for Key Walls */}
        <div className="col-span-3 flex items-center justify-between gap-6 pl-2">
          {([{ label: 'Call Wall', price: activeDetail.call_wall, type: 'resistance' },
             { label: 'Put Wall',  price: activeDetail.put_wall,  type: 'support' },
             { label: 'Spot',      price: activeDetail.spot,          type: 'spot' }] as const).map((item, i) => (
             <Card key={i} className="bg-zinc-900/40 border-white/5 p-6 rounded-3xl flex-1 hover:border-emerald-500/20 transition-all group shadow-2xl backdrop-blur-xl">
                <div className="flex justify-between items-start mb-2">
                   <span className="text-[9px] font-black text-zinc-500 uppercase tracking-widest group-hover:text-emerald-400 transition-colors">{item.label}</span>
                   {item.type === 'resistance' ? <AlertTriangle size={12} className="text-rose-500/50" /> : <ShieldCheck size={12} className="text-emerald-500/50" />}
                </div>
                <div className="text-2xl font-mono font-black tracking-tighter text-white/90">
                  {item.price ? item.price.toFixed(2) : '—'}
                </div>
                <div className="text-[8px] font-black text-zinc-600 mt-2 uppercase tracking-widest">
                  {item.type === 'spot' ? 'Live Telemtry' : `${Math.abs((activeDetail.spot - item.price) / activeDetail.spot * 100).toFixed(1)}% Distance`}
                </div>
             </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
