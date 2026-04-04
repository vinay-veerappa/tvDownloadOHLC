'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { createChart, ColorType, ISeriesApi, LineData } from 'lightweight-charts';
import { 
  ArrowLeft, 
  Settings2, 
  BarChart4, 
  ShieldCheck, 
  Activity,
  FileJson,
  LayoutGrid,
  Info
} from 'lucide-react';

interface RunMetadata {
  id: string;
  runId: string;
  ticker: string;
  grade: string;
  metricsJson: string;
  configJson: string;
  createdAt: string;
}

export default function ResearchDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [metadata, setMetadata] = useState<RunMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [metaRes, equityRes] = await Promise.all([
          fetch(`/api/research/run/${id}`),
          fetch(`/api/research/run/${id}/equity`)
        ]);
        
        const metaData = await metaRes.json();
        const equityData = await equityRes.json();
        
        setMetadata(metaData);
        
        // --- High Performance 1m Charting ---
        if (chartContainerRef.current && equityData.values) {
          const chart = createChart(chartContainerRef.current, {
            layout: { 
              background: { type: ColorType.Solid, color: 'transparent' },
              textColor: 'rgba(255, 255, 255, 0.6)',
            },
            grid: {
              vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
              horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
          });

          const lineSeries = (chart as any).addLineSeries({ 
            color: '#2962FF',
            lineWidth: 2,
          });

          const formattedData: LineData[] = equityData.timestamps.map((t: string, i: number) => ({
            time: Math.floor(new Date(t).getTime() / 1000) as any,
            value: equityData.values[i]
          }));
          
          lineSeries.setData(formattedData);
          chart.timeScale().fitContent();
          chartRef.current = chart;
        }
      } catch (error) {
        console.error('Failed to load deep-dive data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [id]);

  if (loading || !metadata) return (
    <div className="flex flex-col items-center justify-center h-screen text-muted-foreground animate-pulse">
      <Activity className="animate-spin h-8 w-8 mb-4 opacity-50" />
      Hydrating High-Fidelity Equity Curve...
    </div>
  );

  const metrics = JSON.parse(metadata.metricsJson || '{}');
  const config = JSON.parse(metadata.configJson || '{}');

  return (
    <div className="max-w-[1200px] mx-auto space-y-6 pb-20">
      {/* Back Navigation */}
      <button 
        onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors hover:translate-x-[-4px] duration-200"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Research Hub
      </button>

      {/* Header / ID Badge */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-4xl font-black tracking-tighter text-white uppercase italic">{metadata.ticker}</h1>
            <div className="px-3 py-1 bg-primary text-primary-foreground text-xs font-black italic skew-[-12deg] shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)]">
              {metadata.grade} CLASS
            </div>
          </div>
          <p className="text-muted-foreground font-mono text-sm opacity-60">{metadata.runId}</p>
        </div>
        
        <div className="flex gap-3">
          <div className="p-3 bg-secondary/20 rounded-xl border border-white/5 flex items-center gap-3">
            <LayoutGrid className="h-5 w-5 text-primary opacity-50" />
            <div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground">Trades</div>
              <div className="text-xl font-bold">{metrics.total_trades}</div>
            </div>
          </div>
          <div className="p-3 bg-emerald-500/5 rounded-xl border border-emerald-500/10 flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-emerald-500 opacity-50" />
            <div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground">Sharp</div>
              <div className="text-xl font-bold text-emerald-500">{metrics.sharpe?.toFixed(2)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 space-y-6">
          {/* Equity Chart */}
          <div className="bg-card/30 border border-white/5 rounded-2xl overflow-hidden glassmorphism shadow-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <BarChart4 className="h-5 w-5 text-primary" />
                <h3 className="font-bold text-lg">1m High-Fidelity Performance</h3>
              </div>
              <div className="text-xs bg-white/5 px-2 py-1 rounded text-muted-foreground flex items-center gap-1">
                <Info className="h-3 w-3" />
                Interactive Time Scale
              </div>
            </div>
            <div ref={chartContainerRef} className="w-full relative rounded-lg border border-white/5 bg-black/20" />
          </div>

          {/* Detailed Metrics Table */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricBox label="Profit Factor" value={metrics.profit_factor} symbol="" />
            <MetricBox label="Win Rate" value={`${metrics.win_rate?.toFixed(1)}%`} symbol="" />
            <MetricBox label="Max Drawdown" value={`${metrics.drawdown?.toFixed(2)}%`} symbol="" isNegative />
            <MetricBox label="Profit/Loss" value={metrics.grade} symbol="" isGrade />
          </div>
        </div>

        {/* Sidebar: Parameters */}
        <div className="space-y-6">
          <div className="bg-card/30 border border-white/5 rounded-2xl p-6 glassmorphism">
            <div className="flex items-center gap-2 mb-6">
              <Settings2 className="h-5 w-5 text-primary" />
              <h3 className="font-bold">DNA (Params)</h3>
            </div>
            <div className="space-y-4">
              {Object.entries(config).map(([key, val]) => (
                <div key={key} className="space-y-1">
                  <div className="text-[10px] uppercase font-bold text-muted-foreground opacity-50">{key}</div>
                  <div className="font-mono text-sm p-2 bg-white/5 rounded-lg border border-white/5 truncate" title={String(val)}>
                    {typeof val === 'boolean' ? (val ? 'TRUE' : 'FALSE') : String(val)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl flex items-center gap-3">
             <FileJson className="h-5 w-5 text-primary" />
             <div className="text-xs">
                Run Artifacts saved at <br/>
                <span className="font-mono opacity-60">results/RESEARCH/...</span>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, symbol, isNegative, isGrade }: any) {
  return (
    <div className="p-4 bg-secondary/5 border border-white/5 rounded-2xl glassmorphism">
      <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">{label}</div>
      <div className={`text-2xl font-black ${isNegative ? 'text-rose-500' : isGrade ? 'text-primary' : 'text-white'}`}>
        {symbol}{value}
      </div>
    </div>
  );
}
