"use client";

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Activity, Crosshair } from 'lucide-react';

interface HeatmapSnapshot {
  t: number;
  b: Record<string, number>;
  a: Record<string, number>;
  spot?: number;
  trades?: {p: number, v: number, t: number}[];
}

export const BookmapWorkspace = () => {
  const [ticker, setTicker] = useState('QQQ');
  const [priceRange, setPriceRange] = useState(1.5); 
  const [priceBinSize, setPriceBinSize] = useState(0.01);
  const [minSize, setMinSize] = useState(150);
  const [maxHeatSize, setMaxHeatSize] = useState(800);
  const [timeWindow, setTimeWindow] = useState(600000); 
  const [bubbleScale, setBubbleScale] = useState(1.0);
  
  const [data, setData] = useState<{heatmap: HeatmapSnapshot[], mhvns: any}>({heatmap: [], mhvns: null});
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  // Panning & Camera State
  const [baseCenter, setBaseCenter] = useState<number | null>(null);
  const [yOffset, setYOffset] = useState(0);
  const isDragging = useRef(false);
  const lastY = useRef(0);

  // Dynamic baseline defaults per ticker
  useEffect(() => {
    if (ticker === 'SPY') { setPriceRange(1.5); setMinSize(200); setMaxHeatSize(1200); setPriceBinSize(0.05); }
    else if (ticker === 'QQQ') { setPriceRange(1.5); setMinSize(150); setMaxHeatSize(800); setPriceBinSize(0.05); }
    else if (ticker === '/ES') { setPriceRange(10.0); setMinSize(50); setMaxHeatSize(400); setPriceBinSize(0.25); }
    else if (ticker === 'AAPL') { setPriceRange(1.0); setMinSize(400); setMaxHeatSize(1500); setPriceBinSize(0.01); }
    else { setPriceRange(3.0); setMinSize(150); setMaxHeatSize(800); setPriceBinSize(0.01); }
    
    // Reset camera anchor on ticker change
    setBaseCenter(null);
    setYOffset(0); 
  }, [ticker]);

  // Handle Resize
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (!entries[0]) return;
      setDimensions({
        width: entries[0].contentRect.width,
        height: entries[0].contentRect.height
      });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Fetch Data
  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      try {
        const cleanTicker = ticker.replace('/', '').toUpperCase();
        const resp = await fetch(`/api/live/heatmap?ticker=${cleanTicker}&t=${Date.now()}`, { cache: 'no-store' });
        if (!resp.ok) throw new Error("API response not OK");
        const json = await resp.json();
        if (mounted) setData({ heatmap: json.heatmap || [], mhvns: json.mhvns || null });
      } catch (e) {
        console.error("Heatmap fetch error", e);
      }
    };
    
    setData({heatmap: [], mhvns: null});
    fetchData();
    const interval = setInterval(fetchData, 250);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [ticker]);

  // Calculate Price Range & Camera Viewport
  const priceStats = useMemo(() => {
    if (data.heatmap.length === 0) return null;
    
    const latest = data.heatmap[data.heatmap.length - 1];
    
    // Helper to calculate center if spot is missing
    const getFallbackCenter = () => {
        const bids = Object.keys(latest.b).map(Number);
        const asks = Object.keys(latest.a).map(Number);
        if (bids.length > 0 && asks.length > 0) return (Math.max(...bids) + Math.min(...asks)) / 2;
        if (bids.length > 0) return Math.max(...bids);
        if (asks.length > 0) return Math.min(...asks);
        return 0;
    };

    const currentSpot = latest.spot || getFallbackCenter();
    if (currentSpot === 0) return null;

    // Anchor the camera if it hasn't been set yet
    if (baseCenter === null) {
        setBaseCenter(currentSpot);
        return null; // Skip one render frame to allow state update
    }
    
    const activePriceRange = Number.isNaN(priceRange) ? 5.0 : Math.max(0.5, priceRange);
    const viewCenter = baseCenter + yOffset;
    
    return { 
      minP: viewCenter - (activePriceRange / 2), 
      maxP: viewCenter + (activePriceRange / 2), 
      spotPrice: currentSpot, // Live price (moves up/down)
      viewCenter,             // Static camera (until dragged)
      range: activePriceRange 
    };
  }, [data, priceRange, yOffset, baseCenter]);

  // Render Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.heatmap.length === 0 || !priceStats) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = dimensions;
    if (width === 0 || height === 0) return;

    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // Deep slate blue background
    ctx.fillStyle = '#0a0d14'; 
    ctx.fillRect(0, 0, width, height);

    const { viewCenter, range } = priceStats;
    const scale = height / range;
    const tickSize = ticker === '/ES' ? 0.25 : 0.01;
    const activePriceBinSize = Number.isNaN(priceBinSize) ? tickSize : Math.max(tickSize, priceBinSize);
    const activeMinSize = Number.isNaN(minSize) ? 0 : Math.max(0, minSize);
    const activeMaxHeatSize = Number.isNaN(maxHeatSize) ? 1000 : Math.max(1, maxHeatSize);

    const maxT = data.heatmap[data.heatmap.length - 1].t; 
    const timeWindowMs = Number.isNaN(timeWindow) ? 600000 : Math.max(10000, timeWindow);
    const pxPerMs = width / timeWindowMs;

    // 1. Calculate dynamic maximum size for color scaling
    const currentMaxDomSize = data.heatmap.length > 0 ? 
      Math.max(
        ...Object.values(data.heatmap[data.heatmap.length - 1].b), 
        ...Object.values(data.heatmap[data.heatmap.length - 1].a), 
        1
      ) : activeMaxHeatSize;
    
    // Smooth Continuous Color Gradient (Bookmap Style) - FIXED LOG SCALE
    const getBookmapColor = (size: number, maxDom: number) => {
        if (size < activeMinSize) return 'transparent';
        
        // Corrected Logarithmic scaling: Normalize between minSize and maxDom
        const logMin = Math.log10(Math.max(1, activeMinSize));
        const logMax = Math.log10(Math.max(maxDom, activeMinSize + 1));
        const logSize = Math.log10(Math.max(1, size));
        
        // This ensures minSize = ratio 0.0 (Blue) and maxDom = ratio 1.0 (White)
        const ratio = Math.min(Math.max((logSize - logMin) / (logMax - logMin), 0), 1.0);
        
        // Color stops: 0=Faint Blue, 0.25=Cyan, 0.5=Yellow, 0.75=Red, 1.0=White
        const stops = [
            { r: 0, g: 30, b: 80, a: 0.6 },      // Deep Blue
            { r: 0, g: 200, b: 255, a: 0.9 },    // Cyan
            { r: 255, g: 200, b: 0, a: 1.0 },    // Yellow
            { r: 220, g: 20, b: 20, a: 1.0 },    // Red
            { r: 255, g: 255, b: 255, a: 1.0 }   // White
        ];

        const p = ratio * (stops.length - 1);
        const idx = Math.floor(p);
        const t = p - idx;

        if (idx >= stops.length - 1) {
            const c = stops[stops.length - 1];
            return `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`;
        }

        const c1 = stops[idx];
        const c2 = stops[idx + 1];

        // Linear interpolation between the two closest color stops
        const r = Math.round(c1.r + (c2.r - c1.r) * t);
        const g = Math.round(c1.g + (c2.g - c1.g) * t);
        const b = Math.round(c1.b + (c2.b - c1.b) * t);
        const a = c1.a + (c2.a - c1.a) * t;

        return `rgba(${r}, ${g}, ${b}, ${a})`;
    };

    // LAYER 1: HEATMAP
    data.heatmap.forEach((snapshot, i) => {
      // Use exact floating-point math, do not floor/ceil here
      const x1 = width - (maxT - snapshot.t) * pxPerMs;
      const nextT = data.heatmap[i+1]?.t || maxT; 
      const x2 = width - (maxT - nextT) * pxPerMs;
      
      // Add a 1px overlap to completely eliminate vertical tearing
      const rectWidth = (x2 - x1) + 1; 
      
      if (x1 + rectWidth < 0) return;

      const processLevels = (levels: Record<string, number>) => {
        Object.entries(levels).forEach(([priceStr, size]) => {
          if (size < activeMinSize) return;
          const pRaw = parseFloat(priceStr);
          const p = Math.round(pRaw / activePriceBinSize) * activePriceBinSize;
          
          if (p < priceStats.minP || p > priceStats.maxP) return;

          const color = getBookmapColor(size, currentMaxDomSize);
          if (color === 'transparent') return;

          // Sub-pixel y-coordinate calculations
          const y = height / 2 - (p - viewCenter) * scale;
          const tickHeight = scale * activePriceBinSize;
          
          // Ensure a minimum visual height, but allow slight overlap to prevent horizontal tearing
          const h = Math.max(1.5, tickHeight + 0.5); 

          ctx.fillStyle = color;
          // Only floor the starting X, leave Y and dimensions as floats for smoothness
          ctx.fillRect(Math.floor(x1), y - h/2, rectWidth, h); 
        });
      };

      processLevels(snapshot.b);
      processLevels(snapshot.a);
    });

    // LAYER 2: TRADED SPOT LINE (Connecting VWAP/Spot)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let hasSpotData = false;
    data.heatmap.forEach((snapshot) => {
        if (!snapshot.spot) return;
        const x = width - (maxT - snapshot.t) * pxPerMs;
        const spotY = height / 2 - (snapshot.spot - viewCenter) * scale;
        if (!hasSpotData) {
            ctx.moveTo(Math.floor(x), spotY);
            hasSpotData = true;
        } else {
            ctx.lineTo(Math.floor(x), spotY);
        }
    });
    if (hasSpotData) ctx.stroke();

    // LAYER 3: TRADE BUBBLES
    data.heatmap.forEach((snapshot) => {
      if (snapshot.trades && snapshot.trades.length > 0) {
        snapshot.trades.forEach(trade => {
            const tx = width - (maxT - trade.t) * pxPerMs;
            const ty = height / 2 - (trade.p - viewCenter) * scale;
            if (tx < 0 || ty < 0 || ty > height) return;

            const isBuy = snapshot.spot ? trade.p >= snapshot.spot : true;
            const radius = Math.sqrt(trade.v) * 0.5 * bubbleScale;
            
            ctx.beginPath();
            ctx.arc(tx, ty, Math.max(2, radius), 0, Math.PI * 2);
            ctx.fillStyle = isBuy ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)';
            ctx.fill();
            if (radius > 4) {
                ctx.strokeStyle = isBuy ? '#059669' : '#dc2626';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        });
      }
    });

    // LAYER 4: AXIS & OVERLAYS
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'; 
    ctx.lineWidth = 1;
    const step = range >= 20 ? 5 : range >= 10 ? 2 : range >= 5 ? 1 : range >= 2 ? 0.5 : 0.1;
    const startPrice = Math.floor(priceStats.minP / step) * step;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.font = '10px monospace';
    
    for (let p = startPrice; p <= priceStats.maxP; p += step) {
      const y = height / 2 - (p - viewCenter) * scale;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      if (step >= 1 || p === startPrice || p === priceStats.maxP) {
        ctx.fillText(p.toFixed(2), 10, y - 4);
      }
    }
    
    if (data.mhvns) {
        const drawMHVN = (levels: any[], color: string) => {
            levels.slice(0, 3).forEach((lvl: any) => {
                const y = height / 2 - (parseFloat(lvl.price) - viewCenter) * scale;
                if (y < 0 || y > height) return;
                ctx.fillStyle = color;
                ctx.fillRect(0, y - 1, width, 3); 
            });
        };
        drawMHVN(data.mhvns.bids || [], 'rgba(16, 185, 129, 0.4)'); 
        drawMHVN(data.mhvns.asks || [], 'rgba(239, 68, 68, 0.4)'); 
    }

    const currentSpot = priceStats.spotPrice;
    const spotY = height / 2 - (currentSpot - viewCenter) * scale;
    if (spotY >= 0 && spotY <= height) {
       ctx.strokeStyle = '#10b981';
       ctx.lineWidth = 1.5;
       ctx.setLineDash([5, 5]);
       ctx.beginPath();
       ctx.moveTo(0, spotY);
       ctx.lineTo(width, spotY);
       ctx.stroke();
       ctx.setLineDash([]);
       
       ctx.fillStyle = 'rgba(16, 185, 129, 0.2)';
       ctx.fillRect(0, spotY - 8, 100, 16);
       
       ctx.fillStyle = '#10b981';
       ctx.font = 'bold 10px monospace';
       ctx.fillText(`SPOT ${currentSpot.toFixed(2)}`, 5, spotY + 3);
    }

  }, [data, dimensions, priceStats, minSize, maxHeatSize, priceBinSize, yOffset, bubbleScale]);

  // Derive DOM Ladder & mHVN Profile
  const currentDOM = useMemo(() => {
    if (data.heatmap.length === 0 || !priceStats) return { bids: [], asks: [], maxDomSize: 1, mhvnProfile: {}, maxMhvn: 1 };
    const latest = data.heatmap[data.heatmap.length - 1];
    
    const activePriceBinSize = Number.isNaN(priceBinSize) ? 0.01 : Math.max(0.01, priceBinSize);
    const activeMinSize = Number.isNaN(minSize) ? 0 : Math.max(0, minSize);
    const tickSize = ticker === '/ES' ? 0.25 : 0.01;
    const finalBinSize = activePriceBinSize > 0.001 ? activePriceBinSize : tickSize;
    
    // 1. Calculate Resting Liquidity (COB)
    const formatLevel = (levels: Record<string, number>, type: 'bid'|'ask') => {
      const binned: Record<number, number> = {};
      Object.entries(levels).forEach(([priceStr, size]) => {
          if (size < activeMinSize) return;
          const pRaw = parseFloat(priceStr);
          const p = Math.round(pRaw / finalBinSize) * finalBinSize;
          if (p < priceStats.minP || p > priceStats.maxP) return;
          if (!binned[p]) binned[p] = 0;
          binned[p] += size;
      });
      return Object.entries(binned)
        .map(([p, size]) => ({ price: parseFloat(p), size, type }))
        .sort((a, b) => b.price - a.price); 
    };

    const asks = formatLevel(latest.a, 'ask');
    const bids = formatLevel(latest.b, 'bid');
    const maxDomSize = Math.max(...asks.map(a => a.size), ...bids.map(b => b.size), 1);

    // 2. Calculate Liquidity Persistence (mHVN)
    const mhvnProfile: Record<number, number> = {};
    let maxMhvn = 1;
    
    if (data.mhvns) {
        const allMhvns = [...(data.mhvns.bids || []), ...(data.mhvns.asks || [])];
        allMhvns.forEach(lvl => {
            const p = Math.round(lvl.price / finalBinSize) * finalBinSize;
            if (p < priceStats.minP || p > priceStats.maxP) return;
            mhvnProfile[p] = (mhvnProfile[p] || 0) + lvl.weight;
            if (mhvnProfile[p] > maxMhvn) maxMhvn = mhvnProfile[p];
        });
    }

    return { asks, bids, maxDomSize, mhvnProfile, maxMhvn };
  }, [data, priceStats, minSize, priceBinSize, ticker]);

  // Panning Event Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
      isDragging.current = true;
      lastY.current = e.clientY;
  };
  
  const handleMouseMove = (e: React.MouseEvent) => {
      if (!isDragging.current) return;
      
      const deltaY = e.clientY - lastY.current;
      lastY.current = e.clientY;
      
      if (dimensions.height > 0) {
         const activeRange = Number.isNaN(priceRange) ? 5.0 : Math.max(0.5, priceRange);
         const scale = dimensions.height / activeRange;
         const deltaPts = deltaY / scale;
         setYOffset(prev => prev + deltaPts);
      }
  };
  
  const handleMouseUp = () => {
      isDragging.current = false;
  };

  return (
    <div className="flex flex-col h-screen bg-black text-white font-sans">
      {/* Top Toolbar */}
      <div className="h-16 flex-shrink-0 border-b border-white/10 bg-[#0a0a0c] px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <Activity className="text-sky-500" size={20} />
            <h1 className="font-black tracking-widest uppercase text-sm">Advanced Bookmap</h1>
            
            {/* Always available Recenter button */}
            <button 
                onClick={() => {
                    if (data.heatmap.length > 0) {
                        const latest = data.heatmap[data.heatmap.length - 1];
                        const fallbackCenter = () => {
                            const bids = Object.keys(latest.b).map(Number);
                            const asks = Object.keys(latest.a).map(Number);
                            if (bids.length > 0 && asks.length > 0) return (Math.max(...bids) + Math.min(...asks)) / 2;
                            if (bids.length > 0) return Math.max(...bids);
                            if (asks.length > 0) return Math.min(...asks);
                            return 0;
                        };
                        setBaseCenter(latest.spot || fallbackCenter());
                        setYOffset(0);
                    }
                }}
                className="ml-2 flex flex-col justify-center items-center h-6 w-6 bg-zinc-800/50 hover:bg-sky-500/40 text-zinc-500 hover:text-sky-500 border border-zinc-700/50 hover:border-sky-500/50 rounded font-bold transition-colors"
                title="Recenter to Live Price"
            >
                <Crosshair size={14} />
            </button>
          </div>
          
          <div className="flex bg-black rounded-lg border border-white/10 p-1">
            {['SPY', 'QQQ', '/ES', 'AAPL'].map(t => (
              <button 
                key={t}
                onClick={() => setTicker(t)}
                className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${ticker === t ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                {t}
              </button>
            ))}
          </div>
          
          {data.heatmap.length === 0 && (
            <div className="flex items-center gap-2 text-sky-500 animate-pulse">
                <div className="w-2 h-2 bg-sky-500 rounded-full" />
                <span className="text-[10px] uppercase font-black tracking-widest">Awaiting feed...</span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex flex-col gap-1 w-28">
            <span className="text-[9px] uppercase font-black text-zinc-500">Price Range</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="0.5" 
                  value={Number.isNaN(priceRange) ? '' : priceRange} 
                  onChange={(e) => setPriceRange(e.target.value === '' ? NaN : parseFloat(e.target.value))}
                  className="w-full bg-transparent text-sky-400 text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>
          
          <div className="flex flex-col gap-1 w-28">
            <span className="text-[9px] uppercase font-black text-zinc-500">Tick Bin Size</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="0.01" 
                  value={Number.isNaN(priceBinSize) ? '' : priceBinSize} 
                  onChange={(e) => setPriceBinSize(e.target.value === '' ? NaN : parseFloat(e.target.value))}
                  className="w-full bg-transparent text-emerald-400 text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>

          <div className="flex flex-col gap-1 w-28">
            <span className="text-[9px] uppercase font-black text-zinc-500">Min Order Size</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="1" 
                  value={Number.isNaN(minSize) ? '' : minSize} 
                  onChange={(e) => setMinSize(e.target.value === '' ? NaN : parseInt(e.target.value))}
                  className="w-full bg-transparent text-rose-400 text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>

          <div className="flex flex-col gap-1 w-32">
            <span className="text-[9px] uppercase font-black text-zinc-500">Max Heat (White)</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="10" 
                  value={Number.isNaN(maxHeatSize) ? '' : maxHeatSize} 
                  onChange={(e) => setMaxHeatSize(e.target.value === '' ? NaN : parseInt(e.target.value))}
                  className="w-full bg-transparent text-white text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>

          <div className="flex flex-col gap-1 w-32">
            <span className="text-[9px] uppercase font-black text-zinc-500">Bubble Scale</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="0.1" min="0.1"
                  value={Number.isNaN(bubbleScale) ? '' : bubbleScale} 
                  onChange={(e) => setBubbleScale(e.target.value === '' ? NaN : parseFloat(e.target.value))}
                  className="w-full bg-transparent text-amber-400 text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>

          <div className="flex flex-col gap-1 w-32">
            <span className="text-[9px] uppercase font-black text-zinc-500">Time Window (s)</span>
            <div className="flex bg-black border border-white/10 rounded-md overflow-hidden focus-within:border-sky-500 transition-colors">
               <input 
                  type="number" step="30" min="30"
                  value={Number.isNaN(timeWindow) ? '' : Math.round(timeWindow / 1000)} 
                  onChange={(e) => setTimeWindow(e.target.value === '' ? NaN : parseInt(e.target.value) * 1000)}
                  className="w-full bg-transparent text-sky-400 text-xs font-mono font-bold px-2 py-1 outline-none appearance-none"
               />
            </div>
          </div>
        </div>
      </div>

      {/* Main Workspace Area */}
      <div className="flex-1 min-h-0 flex bg-[#0a0d14]">
        {/* Canvas Heatmap */}
        <div 
          className="flex-1 relative cursor-grab active:cursor-grabbing border-r border-zinc-800" 
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onDoubleClick={() => setYOffset(0)}
        >
            <canvas 
              ref={canvasRef}
              style={{ width: '100%', height: '100%', display: 'block' }}
            />
        </div>
        
        {/* Right DOM & mHVN Ladder */}
        <div className="w-64 bg-[#0a0a0c] flex flex-col shrink-0 border-l border-zinc-800">
            <div className="h-8 border-b border-zinc-800 flex items-center px-3 justify-between bg-[#050505]">
                <span className="w-1/3 text-[10px] font-black uppercase tracking-widest text-zinc-500 text-left">Price</span>
                <span className="w-1/3 text-[10px] font-black uppercase tracking-widest text-amber-500/70 text-center" title="Micro High Volume Node (Persistence)">mHVN</span>
                <span className="w-1/3 text-[10px] font-black uppercase tracking-widest text-zinc-500 text-right">COB</span>
            </div>
            
            <div className="flex-1 relative overflow-hidden">
               {[...currentDOM.asks, ...currentDOM.bids].map((level, i) => {
                   if (!priceStats || dimensions.height === 0) return null;
                   
                   const { viewCenter, range } = priceStats;
                   const scale = dimensions.height / range;
                   const y = dimensions.height / 2 - (level.price - viewCenter) * scale;
                   
                   const tickSize = ticker === '/ES' ? 0.25 : 0.01;
                   const activePriceBinSize = Number.isNaN(priceBinSize) ? tickSize : Math.max(tickSize, priceBinSize);
                   const pxPerBin = scale * activePriceBinSize;
                   const rowH = Math.max(12, pxPerBin);
                   
                   if (y < -rowH || y > dimensions.height + rowH) return null;
                   
                   const isAsk = level.type === 'ask';
                   const barColor = isAsk ? 'bg-red-600/30' : 'bg-emerald-600/30';
                   const textColor = isAsk ? 'text-red-400' : 'text-emerald-400';
                   const cobFill = (level.size / currentDOM.maxDomSize) * 100;
                   
                   const mhvnWeight = currentDOM.mhvnProfile[level.price] || 0;
                   // Use a log scale for the visual fill so massive nodes don't completely dwarf smaller ones
                   const mhvnFill = mhvnWeight > 0 ? (Math.log10(mhvnWeight) / Math.log10(currentDOM.maxMhvn)) * 100 : 0;
                   
                   return (
                       <div key={`${level.type}-${i}`} 
                            className="absolute left-0 right-0 flex items-center px-3 hover:bg-white/10 transition-colors"
                            style={{ top: `${y}px`, height: `${rowH}px`, marginTop: `-${rowH/2}px` }}>
                           
                           {/* mHVN Persistence Background Bar (Amber) */}
                           {mhvnWeight > 0 && (
                               <div className="absolute top-[1px] left-1/3 bottom-[1px] bg-amber-500/20 transition-all duration-200 border-r border-amber-500/40" 
                                    style={{ width: `${(Math.min(mhvnFill, 100) / 100) * 33}%` }} />
                           )}

                           {/* COB Background Bar (Red/Green) */}
                           <div className={`absolute top-[1px] right-0 bottom-[1px] ${barColor} transition-all duration-200`} 
                                style={{ width: `${(cobFill / 100) * 33}%` }} />
                           
                           {/* Price */}
                           <div className="w-1/3 relative z-10 text-zinc-300 font-mono text-[11px] leading-none text-left">
                               {level.price.toFixed(2)}
                           </div>

                           {/* mHVN Weight */}
                           <div className="w-1/3 relative z-10 text-amber-400/80 font-mono text-[10px] font-bold leading-none text-center">
                               {mhvnWeight > 0 ? mhvnWeight.toLocaleString() : ''}
                           </div>
                           
                           {/* COB Size */}
                           <div className={`w-1/3 relative z-10 font-mono text-[11px] font-bold leading-none text-right ${textColor}`}>
                               {level.size}
                           </div>
                       </div>
                   );
               })}
            </div>
        </div>
      </div>
    </div>
  );
};