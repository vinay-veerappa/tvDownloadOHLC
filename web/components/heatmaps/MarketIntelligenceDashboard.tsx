'use client';

import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { TrendingUp, TrendingDown, Activity, Zap, Calendar, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export default function MarketIntelligenceDashboard() {
  const [movers, setMovers] = useState<any>(null);
  const [options, setOptions] = useState<any>(null);
  const [earnings, setEarnings] = useState<any[]>([]);

  useEffect(() => {
    async function loadData() {
      try {
        const [mRes, oRes, eRes] = await Promise.all([
          fetch('/api/screeners/movers'),
          fetch('/api/screeners/unusual_options'),
          fetch('/api/screeners/earnings')
        ]);
        setMovers(await mRes.json());
        setOptions(await oRes.json());
        setEarnings(await eRes.json());
      } catch (err) {
        console.error('Failed loading screener intelligence:', err);
      }
    }
    loadData();
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 font-sans">
      {/* 1. Top Movers Card */}
      <Card className="bg-zinc-950 border-zinc-800 p-5 space-y-4 rounded-xl shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-emerald-400" />
            <h3 className="text-sm font-bold font-mono text-white tracking-tight uppercase">Top Movers</h3>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono">Schwab Equity Streamer</span>
        </div>

        {/* Gainers */}
        <div className="space-y-2">
          <div className="text-[11px] font-bold font-mono text-emerald-400 uppercase tracking-wider flex items-center gap-1">
            <ArrowUpRight className="h-3.5 w-3.5" /> Top Gainers
          </div>
          <div className="space-y-1.5">
            {movers?.topGainers && movers.topGainers.length > 0 ? (
              movers.topGainers.map((t: any) => (
                <Link key={t.ticker} href={`/research/screener/${t.ticker}`}>
                  <div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-850 transition-colors text-xs font-mono">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-white w-12">{t.ticker}</span>
                      <span className="text-zinc-400">${t.price.toFixed(2)}</span>
                    </div>
                    <span className="font-bold text-emerald-400">+{t.changePct.toFixed(2)}%</span>
                  </div>
                </Link>
              ))
            ) : (
              <div className="text-xs text-zinc-500 font-mono py-2 text-center">Loading movers...</div>
            )}
          </div>
        </div>

        {/* Losers */}
        <div className="space-y-2 pt-2 border-t border-zinc-850">
          <div className="text-[11px] font-bold font-mono text-rose-400 uppercase tracking-wider flex items-center gap-1">
            <ArrowDownRight className="h-3.5 w-3.5" /> Top Losers
          </div>
          <div className="space-y-1.5">
            {movers?.topLosers && movers.topLosers.length > 0 ? (
              movers.topLosers.map((t: any) => (
                <Link key={t.ticker} href={`/research/screener/${t.ticker}`}>
                  <div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-850 transition-colors text-xs font-mono">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-white w-12">{t.ticker}</span>
                      <span className="text-zinc-400">${t.price.toFixed(2)}</span>
                    </div>
                    <span className="font-bold text-rose-400">{t.changePct.toFixed(2)}%</span>
                  </div>
                </Link>
              ))
            ) : (
              <div className="text-xs text-zinc-500 font-mono py-2 text-center">Loading losers...</div>
            )}
          </div>
        </div>
      </Card>

      {/* 2. Unusual Options Flow */}
      <Card className="bg-zinc-950 border-zinc-800 p-5 space-y-4 rounded-xl shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <Zap className="h-5 w-5 text-cyan-400" />
            <h3 className="text-sm font-bold font-mono text-white tracking-tight uppercase">Unusual Options Flow</h3>
          </div>
          <Badge className="bg-cyan-950 text-cyan-400 border border-cyan-800 font-mono text-[9px]">
            Schwab Screener Keys
          </Badge>
        </div>

        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
          {options?.sweeps && options.sweeps.length > 0 ? (
            options.sweeps.map((s: any, idx: number) => {
              const isBull = s.sentiment === 'BULLISH_SWEEP';
              return (
                <Link key={idx} href={`/research/screener/${s.ticker}`}>
                  <div className="p-3 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-850 space-y-1.5 transition-colors font-mono">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">{s.ticker}</span>
                      <span className={`font-bold ${isBull ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isBull ? '+' : ''}{s.changePct.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex justify-between text-[11px] text-zinc-400">
                      <span>Call/Put Ratio: <strong className="text-zinc-200">{s.callPutRatio}</strong></span>
                      <span>Vol: <strong className="text-cyan-300">{(s.totalOptionVolume / 1000).toFixed(0)}k</strong></span>
                    </div>
                    <div className="text-[9px] text-zinc-500 flex justify-between pt-1 border-t border-zinc-800/60">
                      <span>Key: {s.screenerKey}</span>
                      <span className={isBull ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                        {s.sentiment}
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })
          ) : (
            <div className="text-xs text-zinc-500 font-mono py-8 text-center">No option sweeps recorded</div>
          )}
        </div>
      </Card>

      {/* 3. This Week's Earnings */}
      <Card className="bg-zinc-950 border-zinc-800 p-5 space-y-4 rounded-xl shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <Calendar className="h-5 w-5 text-amber-400" />
            <h3 className="text-sm font-bold font-mono text-white tracking-tight uppercase">Earnings Calendar</h3>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono">Prisma DB</span>
        </div>

        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
          {earnings && earnings.length > 0 ? (
            earnings.slice(0, 10).map((e: any, idx: number) => (
              <Link key={idx} href={`/research/screener/${e.ticker}`}>
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-850 transition-colors text-xs font-mono">
                  <div>
                    <div className="font-bold text-white">{e.ticker}</div>
                    <div className="text-[10px] text-zinc-500 max-w-[140px] truncate">{e.company}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-amber-400 font-bold">{e.date}</div>
                    <Badge className="bg-zinc-800 text-zinc-400 font-mono text-[9px] px-1.5 py-0 mt-0.5">
                      {e.session}
                    </Badge>
                  </div>
                </div>
              </Link>
            ))
          ) : (
            <div className="text-xs text-zinc-500 font-mono py-8 text-center">No earnings scheduled</div>
          )}
        </div>
      </Card>
    </div>
  );
}
