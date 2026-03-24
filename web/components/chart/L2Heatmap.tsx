"use client";

import React, { useEffect, useRef, useState, useMemo } from 'react';

interface HeatmapSnapshot {
  t: number; // timestamp
  b: Record<string, number>; // bids {price: size}
  a: Record<string, number>; // asks {price: size}
}

export const L2Heatmap = ({ ticker = "SPY" }: { ticker?: string }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<HeatmapSnapshot[]>([]);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  // Track dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    
    const observer = new ResizeObserver((entries) => {
      if (!entries[0]) return;
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Sync canvas dimensions
  useEffect(() => {
    if (canvasRef.current && dimensions.width > 0) {
      canvasRef.current.width = dimensions.width;
      canvasRef.current.height = dimensions.height;
    }
  }, [dimensions]);

  // Fetch logic
  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      try {
        const cleanTicker = ticker.replace('/', '').toUpperCase();
        const resp = await fetch(`/api/live/heatmap?ticker=${cleanTicker}`);
        if (!resp.ok) throw new Error("API response not OK");
        const json = await resp.json();
        if (mounted) setData(json);
      } catch (e) {
        console.error("Heatmap fetch error", e);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [ticker]);

  // Stable price range calculation
  const priceStats = useMemo(() => {
    if (data.length === 0) return null;
    
    const allPrices = data.flatMap(snapshot => [
      ...Object.keys(snapshot.b).map(Number),
      ...Object.keys(snapshot.a).map(Number)
    ]);
    
    if (allPrices.length === 0) return null;
    
    let minP = Infinity;
    let maxP = -Infinity;
    for (const p of allPrices) {
      if (p < minP) minP = p;
      if (p > maxP) maxP = p;
    }
    
    const center = (minP + maxP) / 2;
    const range = Math.max((maxP - minP) * 1.5, 0.5); // 50% padding, min 0.5 points
    
    return { minP, maxP, center, range };
  }, [data]);

  // Render Logic
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0 || !priceStats) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = dimensions;
    if (width === 0 || height === 0) return;

    ctx.clearRect(0, 0, width, height);

    const cellWidth = Math.max(width / data.length, 1);
    const { center, range } = priceStats;
    
    // Scale factor: pixels per point
    const scale = height / range;
    
    data.forEach((snapshot, i) => {
      const x = i * cellWidth;
      
      // Render Bids (Emerald)
      Object.entries(snapshot.b).forEach(([price, size]) => {
          const p = parseFloat(price);
          const y = height / 2 - (p - center) * scale;
          const alpha = Math.min(size / 200, 0.7); // Higher sensitivity for visibility
          ctx.fillStyle = `rgba(16, 185, 129, ${alpha})`; 
          ctx.fillRect(x, y - 1, cellWidth + 0.5, 3); // Slightly bleed width to avoid gaps
      });
      
      // Render Asks (Rose)
      Object.entries(snapshot.a).forEach(([price, size]) => {
          const p = parseFloat(price);
          const y = height / 2 - (p - center) * scale;
          const alpha = Math.min(size / 200, 0.7); 
          ctx.fillStyle = `rgba(244, 63, 94, ${alpha})`; 
          ctx.fillRect(x, y - 1, cellWidth + 0.5, 3);
      });
    });

    // Draw Price Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    
    const step = range > 10 ? 5 : 1;
    const startPrice = Math.floor(priceStats.minP / step) * step;
    for (let p = startPrice; p <= priceStats.maxP; p += step) {
        const y = height / 2 - (p - center) * scale;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
        
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.font = 'bold 12px monospace';
        ctx.fillText(p.toString(), 10, y - 5);
    }
    ctx.setLineDash([]);

  }, [data, dimensions, priceStats]);

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[400px] bg-[#050505] rounded-[2rem] overflow-hidden border border-white/5 shadow-2xl">
      <div className="absolute top-6 left-8 z-10 flex flex-col gap-1">
        <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
            <h2 className="text-[10px] font-black text-white uppercase tracking-[0.2em]">Live Bookmap Engine</h2>
        </div>
        <div className="text-[18px] font-mono font-black text-orange-400/80">{ticker}</div>
      </div>
      
      {data.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/40 backdrop-blur-sm z-0">
          <div className="w-12 h-12 border-4 border-orange-500/20 border-t-orange-500 rounded-full animate-spin" />
          <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Awaiting Tier-2 Liquidity...</span>
        </div>
      )}

      <canvas 
        ref={canvasRef} 
        style={{ width: '100%', height: '100%', display: 'block' }}
      />
    </div>
  );
};
