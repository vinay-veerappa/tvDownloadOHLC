"use client";

import React, { useEffect, useRef, useState } from 'react';

interface HeatmapSnapshot {
  t: number; // timestamp
  b: Record<string, number>; // bids {price: size}
  a: Record<string, number>; // asks {price: size}
}

export const L2Heatmap = ({ ticker = "ES" }: { ticker?: string }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<HeatmapSnapshot[]>([]);
  
  // Simulation/Fetch logic
  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await fetch(`/api/live/heatmap?ticker=${ticker.replace('/','')}`);
        const json = await resp.json();
        setData(json);
      } catch (e) {
        console.error("Heatmap fetch error", e);
      }
    };
    
    const interval = setInterval(fetchData, 1000);
    return () => clearInterval(interval);
  }, [ticker]);

  // Render Logic
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Simplified Heatmap Rendering
    const cellWidth = width / data.length;
    const priceRange = 20; // 20 points for demo
    const centerPrice = 5000;
    const tickSize = 0.25;
    
    data.forEach((snapshot, i) => {
      const x = i * cellWidth;
      
      // Render Bids
      Object.entries(snapshot.b).forEach(([price, size]) => {
          const p = parseFloat(price);
          const y = height / 2 - (p - centerPrice) * (height / priceRange);
          const alpha = Math.min(size / 200, 1.0);
          ctx.fillStyle = `rgba(0, 255, 0, ${alpha})`;
          ctx.fillRect(x, y, cellWidth, 2);
      });
      
      // Render Asks
      Object.entries(snapshot.a).forEach(([price, size]) => {
          const p = parseFloat(price);
          const y = height / 2 - (p - centerPrice) * (height / priceRange);
          const alpha = Math.min(size / 200, 1.0);
          ctx.fillStyle = `rgba(255, 0, 0, ${alpha})`;
          ctx.fillRect(x, y, cellWidth, 2);
      });
    });

  }, [data]);

  return (
    <div className="relative w-full h-[600px] bg-slate-900 rounded-lg overflow-hidden border border-slate-800">
      <div className="absolute top-2 left-2 text-xs text-slate-400 z-10">
        L2 BOOKMAP - {ticker}
      </div>
      <canvas 
        ref={canvasRef} 
        width={1200} 
        height={600} 
        className="w-full h-full"
      />
    </div>
  );
};
