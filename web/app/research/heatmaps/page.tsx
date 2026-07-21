import React from 'react';
import HeatmapTreemap from '@/components/heatmaps/HeatmapTreemap';
import MarketIntelligenceDashboard from '@/components/heatmaps/MarketIntelligenceDashboard';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowLeft, LayoutGrid } from 'lucide-react';

export const metadata = {
  title: 'Market Heatmaps & Intelligence | AntiGravity Trading Platform',
  description: 'Interactive stock heatmaps, unusual option surges, top movers, and earnings calendar.'
};

export default function MarketHeatmapsPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-6 space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div className="flex items-center space-x-3">
          <Link href="/research/screener">
            <Button variant="outline" size="icon" className="h-9 w-9 bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-300">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-2xl font-extrabold tracking-tight text-white font-mono flex items-center gap-2">
                <LayoutGrid className="h-6 w-6 text-cyan-400" />
                Market Heatmaps & Intelligence
              </h1>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5 font-mono">
              Batch-powered treemaps, Schwab Streamer option flow, top movers & earnings calendar
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <Link href="/research/screener">
            <Button variant="outline" className="h-9 bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-800 text-xs font-mono font-bold">
              Stock Screener →
            </Button>
          </Link>
        </div>
      </div>

      {/* 1. Full Width Interactive Treemap */}
      <HeatmapTreemap initialType="sp500" />

      {/* 2. Market Intelligence Dashboard (Top Movers, Options Sweeps, Earnings) */}
      <MarketIntelligenceDashboard />
    </div>
  );
}
