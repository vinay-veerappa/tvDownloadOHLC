"use client";

import React, { useEffect, useState, useRef } from 'react';
import { getLiveChartData } from '@/actions/get-live-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Play, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries } from 'lightweight-charts';

export default function LiveChartPage() {
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(true);
    const [lastPrice, setLastPrice] = useState<string>("---");
    const [symbol, setSymbol] = useState<string>("---");

    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const isFirstLoad = useRef(true);

    const fetchData = async () => {
        const res = await getLiveChartData();
        if (res.success && res.data) {
            setLoading(false);
            setSymbol(res.data.symbol);
            updateChart(res.data.candles);
        }
    };

    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Initialize Chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#9ca3af',
            },
            grid: {
                vertLines: { color: '#334155', style: 0 },
                horzLines: { color: '#334155', style: 0 },
            },
            width: chartContainerRef.current.clientWidth,
            height: 500,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
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

        // Start Polling
        fetchData();
        const id = setInterval(() => {
            if (running) fetchData();
        }, 1000);

        return () => {
            window.removeEventListener('resize', handleResize);
            clearInterval(id);
            chart.remove();
        };
    }, []); // Run once on mount

    // Effect to toggle running state impact?
    // Actually the interval checks the state ref, but state in interval closure is stale.
    // We need a ref for running or restart interval.
    // Simplest is to just check a ref.
    const runningRef = useRef(running);
    useEffect(() => { runningRef.current = running; }, [running]);

    // Override the interval to use ref
    useEffect(() => {
        const id = setInterval(() => {
            if (runningRef.current) fetchData();
        }, 1000);
        return () => clearInterval(id);
    }, []);


    const updateChart = (candles: any[]) => {
        if (!seriesRef.current || !candles.length) return;

        // Transform data
        // Schwab gives epoch ms. Lightweight charts likes seconds or date strings?
        // It accepts timestamps in seconds.
        const formatted = candles.map(c => ({
            time: c.time / 1000,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        }));

        // Sort just in case
        formatted.sort((a, b) => a.time - b.time);

        // If first load, set data. Else update last candle.
        // Actually, for simplicity in this MVP, we can just setData() if array is small < 1000.
        // But lightweight charts setData might flicker if done every second? No, it's fine.
        // Better: Check if we have new bars.

        seriesRef.current.setData(formatted);

        if (isFirstLoad.current) {
            chartRef.current?.timeScale().fitContent();
            isFirstLoad.current = false;
        }

        const last = formatted[formatted.length - 1];
        if (last) setLastPrice(last.close.toFixed(2));
    };

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <h1 className="text-3xl font-bold tracking-tight">Live Chart Experiment</h1>
                    <Badge variant={running ? "default" : "secondary"}>
                        {running ? "LIVE" : "PAUSED"}
                    </Badge>
                </div>
                <Button onClick={() => setRunning(!running)} variant="outline">
                    {running ? <Square className="h-4 w-4 mr-2 fill-current" /> : <Play className="h-4 w-4 mr-2" />}
                    {running ? "Pause" : "Resume"}
                </Button>
            </div>

            <Card className="bg-slate-950 border-slate-800">
                <CardHeader>
                    <CardTitle className="flex justify-between text-slate-100">
                        <span>{symbol}</span>
                        <span className="font-mono text-2xl">${lastPrice}</span>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <div ref={chartContainerRef} className="w-full h-[500px]" />
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                            <Loader2 className="h-8 w-8 animate-spin text-white" />
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="text-sm text-muted-foreground">
                <p>To run the backend:</p>
                <code className="bg-muted p-1 rounded">python scripts/streaming/stream_chart.py</code>
            </div>
        </div>
    );
}
