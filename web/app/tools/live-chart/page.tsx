"use client";

import React, { useEffect, useState, useRef } from 'react';
import { getLiveChartData } from '@/actions/get-live-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Play, Square, Activity } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, Time } from 'lightweight-charts';
import { cn } from '@/lib/utils';

export default function LiveChartPage() {
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(true);
    const [livePrice, setLivePrice] = useState<number | null>(null);
    const [lastUpdate, setLastUpdate] = useState<string>("");
    const [symbol, setSymbol] = useState<string>("---");

    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const isFirstLoad = useRef(true);
    const runningRef = useRef(running);

    useEffect(() => { runningRef.current = running; }, [running]);

    const fetchData = async () => {
        try {
            const res = await getLiveChartData();
            if (res.success && res.data) {
                setSymbol(res.data.symbol);
                setLivePrice(res.data.live_price);
                setLastUpdate(res.data.last_update);
                updateChart(res.data.candles, res.data.live_price);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Initialize Chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#9ca3af',
                fontSize: 12,
            },
            localization: {
                locale: 'en-US',
                // Lightweight charts uses UTC if we don't override formatters
                // For EST, we can use a custom formatter or just rely on the browser local time
                // if the user's PC is set to EST. To FORCE EST:
                timeFormatter: (tick: number) => {
                    return new Date(tick * 1000).toLocaleString('en-US', {
                        timeZone: 'America/New_York',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                }
            },
            grid: {
                vertLines: { color: 'rgba(51, 65, 85, 0.5)', style: 1 },
                horzLines: { color: 'rgba(51, 65, 85, 0.5)', style: 1 },
            },
            width: chartContainerRef.current.clientWidth,
            height: 550,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                barSpacing: 10, // Wider candles
                rightOffset: 12, // Space on the right
            },
            crosshair: {
                mode: 0,
            },
        });

        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444'
        });

        chartRef.current = chart;
        seriesRef.current = series;

        // Resize handler
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };
        window.addEventListener('resize', handleResize);

        // Start Polling (2000ms for rate limit safety: 30 calls/min)
        fetchData();
        const id = setInterval(() => {
            if (runningRef.current) fetchData();
        }, 2000);

        return () => {
            window.removeEventListener('resize', handleResize);
            clearInterval(id);
            chart.remove();
        };
    }, []); // Run once on mount

    interface RawCandle {
        time: number;
        open: number;
        high: number;
        low: number;
        close: number;
    }

    const lastCandleRef = useRef<number | null>(null);

    const updateChart = (candles: RawCandle[], live_price: number | null) => {
        if (!seriesRef.current || !candles.length) return;

        // Transform data
        const formatted = candles.map(c => ({
            time: (c.time / 1000) as Time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        }));

        formatted.sort((a, b) => (Number(a.time) - Number(b.time)));

        // Initial load: Bring in all the session history found in the buffer
        if (isFirstLoad.current) {
            seriesRef.current.setData(formatted);
            chartRef.current?.timeScale().fitContent();
            isFirstLoad.current = false;
        }

        // Real-time Fluid Update: 
        // We use series.update() which gracefully handles:
        // 1. Updating the current candle (same timestamp)
        // 2. Adding a new candle (new timestamp)
        if (live_price !== null) {
            const latestRaw = formatted[formatted.length - 1];
            const updatedCandle = { ...latestRaw };
            updatedCandle.close = live_price;

            // Sync High/Low with the live price
            if (live_price > updatedCandle.high) updatedCandle.high = live_price;
            if (live_price < updatedCandle.low) updatedCandle.low = live_price;

            seriesRef.current.update(updatedCandle);
        }
    };

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <h1 className="text-3xl font-bold tracking-tight">Live Chart</h1>
                    <div className="flex items-center gap-2">
                        <Badge variant={running ? "default" : "secondary"} className={cn(running && "bg-green-600 hover:bg-green-700 animate-pulse")}>
                            {running ? "LIVE" : "PAUSED"}
                        </Badge>
                        {lastUpdate && (
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                                <Activity className="h-3 w-3" />
                                {new Date(lastUpdate).toLocaleTimeString()}
                            </span>
                        )}
                    </div>
                </div>
                <Button onClick={() => setRunning(!running)} variant="outline">
                    {running ? <Square className="h-4 w-4 mr-2 fill-current" /> : <Play className="h-4 w-4 mr-2" />}
                    {running ? "Pause" : "Resume"}
                </Button>
            </div>

            <Card className="bg-slate-950 border-slate-800 overflow-hidden">
                <CardHeader className="border-b border-slate-800 bg-slate-900/50 py-4">
                    <CardTitle className="flex justify-between items-baseline text-slate-100">
                        <div className="flex flex-col">
                            <span className="text-sm font-medium text-slate-400">Futures Index</span>
                            <span className="text-2xl font-bold tracking-wider">{symbol}</span>
                        </div>
                        <div className="flex flex-col items-end">
                            <span className="text-sm font-medium text-slate-400">Current Price</span>
                            <span className={cn(
                                "font-mono text-4xl transition-all duration-300",
                                running ? "text-green-400" : "text-slate-300"
                            )}>
                                ${livePrice?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "---"}
                            </span>
                        </div>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0 relative">
                    <div ref={chartContainerRef} className="w-full h-[550px]" />
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10 transition-opacity">
                            <div className="text-center p-8 bg-slate-900/80 rounded-2xl border border-slate-700 backdrop-blur-sm shadow-2xl">
                                <Loader2 className="h-10 w-10 animate-spin text-blue-500 mx-auto mb-4" />
                                <p className="text-white font-medium">Syncing Ledger...</p>
                                <p className="text-slate-400 text-xs mt-2 uppercase tracking-widest">establishing connection</p>
                            </div>
                        </div>
                    )}
                    {!loading && symbol === "---" && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/60 z-10 backdrop-blur-[2px]">
                            <div className="text-center p-8 bg-slate-900/90 rounded-2xl border border-slate-700 shadow-2xl max-w-sm">
                                <Activity className="h-12 w-12 text-amber-500 mx-auto mb-6 opacity-80" />
                                <h3 className="text-xl font-semibold text-white mb-2">Data Stream Offline</h3>
                                <p className="text-slate-400 text-sm mb-8 leading-relaxed">
                                    The persistent storage buffer is empty. Launch the Schwab streamer to begin data collection.
                                </p>
                                <div className="space-y-3">
                                    <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Terminal Command</p>
                                    <code className="block p-3 bg-black/50 border border-slate-800 rounded-lg text-amber-400 text-xs font-mono text-left overflow-x-auto whitespace-nowrap">
                                        python scripts/streaming/stream_chart.py
                                    </code>
                                </div>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="flex items-center justify-between text-[10px] uppercase tracking-tighter text-slate-500 font-bold px-1">
                <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" /> Schwab Trader API</span>
                    <span>Polling: 2000ms (Safe Limit)</span>
                </div>
                <div>
                    Storage: data/live_storage.parquet
                </div>
            </div>
        </div>
    );
}
