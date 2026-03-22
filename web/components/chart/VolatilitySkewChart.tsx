"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Activity, AlertTriangle, ShieldCheck } from "lucide-react";

interface SkewDataPoint {
  timestamp: string;
  volatility_skew_premium: number | null;
  spot?: number;
}

interface VolatilitySkewChartProps {
  ticker: string;
  data: SkewDataPoint[];
}

export function VolatilitySkewChart({ ticker, data }: VolatilitySkewChartProps) {
  const chartData = useMemo(() => {
    if (!Array.isArray(data)) return [];
    return data
      .filter((d) => d && d.volatility_skew_premium !== null)
      .map((d) => ({
        ...d,
        displayTime: new Date(d.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        // Ensure we have a number for the chart
        skew: d.volatility_skew_premium || 0,
      }));
  }, [data]);

  const latestSkew = chartData.length > 0 ? chartData[chartData.length - 1].skew : 0;
  const isFear = latestSkew > 0;

  if (chartData.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center opacity-20 gap-4 p-10">
        <Activity size={48} />
        <span className="text-sm font-black uppercase tracking-widest text-center">
          Volatility Skew Data Unavailable
          <br />
          Awaiting RTH Telemetry...
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isFear ? "bg-rose-500/10" : "bg-emerald-500/10"}`}>
            {isFear ? (
              <AlertTriangle className="text-rose-500" size={18} />
            ) : (
              <ShieldCheck className="text-emerald-500" size={18} />
            )}
          </div>
          <div>
            <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Institutional Bias</div>
            <div className={`text-lg font-black tracking-tight ${isFear ? "text-rose-400" : "text-emerald-400"}`}>
              {isFear ? "FEAR / PROTECTIVE HEDGING" : "GREED / CALL SPECULATION"}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Skew Premium</div>
          <div className={`text-2xl font-mono font-black ${isFear ? "text-rose-500" : "text-emerald-500"}`}>
            {latestSkew > 0 ? "+" : ""}
            {latestSkew.toFixed(3)}
          </div>
        </div>
      </div>

      <div className="w-full h-[450px]">
        <ResponsiveContainer width="100%" height="100%" debounce={50}>
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
            <XAxis
              dataKey="displayTime"
              stroke="#ffffff10"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
            />
            <YAxis
              stroke="#ffffff10"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => v.toFixed(2)}
              domain={["auto", "auto"]}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                const val = d.skew;
                return (
                  <div className="bg-black/90 border border-white/10 p-4 rounded-2xl backdrop-blur-3xl shadow-2xl">
                    <div className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">
                      {d.displayTime} | Skew Premium
                    </div>
                    <div className={`text-xl font-mono font-black ${val > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                      {val > 0 ? "+" : ""}
                      {val.toFixed(4)}
                    </div>
                    <div className="text-[9px] font-black text-zinc-600 mt-1 uppercase tracking-wider">
                      {val > 0 ? "Put Overwriting / Hedging" : "Call Overwriting / Growth Bias"}
                    </div>
                  </div>
                );
              }}
            />
            <ReferenceLine y={0} stroke="#ffffff20" strokeWidth={1} strokeDasharray="5 5" />
            
            <Line
              type="monotone"
              dataKey="skew"
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              // Dynamic color is tricky with a single Line component in Recharts.
              // We'll use a CSS filter or just stick to one color if we can't easily split.
              // Actually, we can use a functional stroke or just color it based on LATEST if it's a trend.
              // For now, let's use the latest bias as the line color.
              stroke={isFear ? "#f43f5e" : "#10b981"}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      <div className="px-4 py-3 bg-white/[0.02] border border-white/5 rounded-2xl">
        <p className="text-[9px] font-bold text-zinc-500 leading-relaxed uppercase tracking-wider">
          <span className="text-zinc-300">Metric Intelligence:</span> The Volatility Skew Premium (25d Put IV - 25d Call IV) measures the cost of downside protection relative to upside targets. Positive values indicate institutional fear and a demand for protective hedges.
        </p>
      </div>
    </div>
  );
}
