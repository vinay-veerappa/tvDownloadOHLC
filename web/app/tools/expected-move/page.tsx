'use client';

import React, { useEffect, useState } from 'react';
import { getExpectedMoveData } from '@/actions/get-expected-move';
import { updateManualEm } from '@/actions/update-manual-em';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Loader2, RefreshCw, History, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { AddTicker } from '@/components/expected-move/add-ticker';
import { EmHistoryView } from '@/components/expected-move/em-history-view';

interface ExpirationData {
    id?: number; // DB ID
    date: string;
    dte: number;
    straddle: number;
    em_365: number;
    em_252: number;
    adj_em: number;
    manual_em?: number | null;
}

interface TickerData {
    ticker: string;
    price: number;
    expirations: ExpirationData[];
}

const DEFAULT_TICKERS = ['NVDA', 'TSLA', 'AAPL', 'SPY', 'QQQ', 'IWM', '/ES', '/NQ'];

export default function ExpectedMovePage() {
    const [tickers, setTickers] = useState<string[]>(DEFAULT_TICKERS);
    const [data, setData] = useState<TickerData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // History View State
    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
    const [historyOpen, setHistoryOpen] = useState(false);

    // Initial load
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async (refresh: boolean = false, currentTickers: string[] = tickers) => {
        setLoading(true);
        setError(null);
        try {
            // Pass the current list of tickers to the server action
            const res = await getExpectedMoveData(currentTickers, refresh);
            if (res.success && res.data) {
                setData(res.data as TickerData[]);
            } else {
                setError(res.error || 'Unknown error');
            }
        } catch (err) {
            setError('Failed to fetch data');
        } finally {
            setLoading(false);
        }
    };

    const handleAddTicker = (newTicker: string) => {
        if (!tickers.includes(newTicker)) {
            const updated = [...tickers, newTicker];
            setTickers(updated);
            // Trigger fetch with new list, but don't force refresh of all unless needed
            // Actually, we need to fetch specifically for the new one essentially.
            // For simplicity, just re-fetch the batch. Ideally we'd optimize this.
            fetchData(false, updated);
        }
    };

    const handleRemoveTicker = (tickerToRemove: string) => {
        const updated = tickers.filter(t => t !== tickerToRemove);
        setTickers(updated);
        setData(prev => prev.filter(d => d.ticker !== tickerToRemove));
    };

    const handleManualChange = async (tickerIndex: number, expIndex: number, newValue: string) => {
        const val = parseFloat(newValue);
        if (isNaN(val)) return;

        // Optimistic Update
        const newData = [...data];
        const item = newData[tickerIndex].expirations[expIndex];
        item.manual_em = val;
        setData(newData);

        // Server Update
        if (item.id) {
            await updateManualEm(item.id, val);
        }
    };

    const openHistory = (ticker: string) => {
        setSelectedTicker(ticker);
        setHistoryOpen(true);
    };

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div className="flex justify-between items-center flex-wrap gap-4">
                <div className="flex items-center gap-4">
                    <h1 className="text-3xl font-bold tracking-tight">Expected Move Dashboard</h1>
                    <AddTicker onAdd={handleAddTicker} />
                </div>

                <Button
                    variant="outline"
                    onClick={() => fetchData(true, tickers)}
                    disabled={loading}
                >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    Refresh Data
                </Button>
            </div>

            {error && (
                <div className="p-4 border border-red-200 bg-red-50 text-red-900 rounded-md">
                    Error: {error}
                </div>
            )}

            {loading && !data.length && (
                <div className="flex justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                </div>
            )}

            <div className="grid gap-6">
                {data.map((item, tIdx) => (
                    <Card key={item.ticker} className="overflow-hidden">
                        <CardHeader className="bg-muted/50 py-3">
                            <div className="flex justify-between items-center">
                                <CardTitle className="text-lg flex items-center gap-2">
                                    {item.ticker}
                                    <Badge variant="secondary" className="font-mono">${item.price.toFixed(2)}</Badge>
                                </CardTitle>
                                <div className="flex gap-2">
                                    <Button variant="ghost" size="sm" onClick={() => openHistory(item.ticker)}>
                                        <History className="h-4 w-4 mr-2" />
                                        History
                                    </Button>
                                    {!DEFAULT_TICKERS.includes(item.ticker) && (
                                        <Button variant="ghost" size="icon" onClick={() => handleRemoveTicker(item.ticker)} className="text-muted-foreground hover:text-red-500">
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="p-0">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[120px]">Expiration</TableHead>
                                        <TableHead className="w-[60px]">DTE</TableHead>
                                        <TableHead className="text-right">Straddle</TableHead>
                                        <TableHead className="text-right">EM (365)</TableHead>
                                        <TableHead className="text-right">EM (252)</TableHead>
                                        <TableHead className="text-right font-bold">Adj (85%)</TableHead>
                                        <TableHead className="text-right w-[100px]">My Value</TableHead>
                                        <TableHead className="text-right w-[180px]">Range</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {item.expirations.length > 0 ? (
                                        item.expirations.map((exp, eIdx) => {
                                            const effectiveEm = exp.manual_em || exp.adj_em;
                                            const lower = (item.price - effectiveEm).toFixed(2);
                                            const upper = (item.price + effectiveEm).toFixed(2);
                                            const isManual = !!exp.manual_em;

                                            return (
                                                <TableRow key={exp.date}>
                                                    <TableCell className="font-medium">{exp.date}</TableCell>
                                                    <TableCell>{exp.dte}</TableCell>
                                                    <TableCell className="text-right text-muted-foreground">${exp.straddle.toFixed(2)}</TableCell>
                                                    <TableCell className="text-right text-muted-foreground">${exp.em_365.toFixed(2)}</TableCell>
                                                    <TableCell className="text-right text-muted-foreground">${exp.em_252.toFixed(2)}</TableCell>
                                                    <TableCell className="text-right font-bold text-primary">${exp.adj_em.toFixed(2)}</TableCell>
                                                    <TableCell className="text-right p-1">
                                                        <Input
                                                            className="h-8 w-24 text-right ml-auto"
                                                            type="number"
                                                            step="0.1"
                                                            placeholder="-"
                                                            defaultValue={exp.manual_em || ''}
                                                            onBlur={(e) => handleManualChange(tIdx, eIdx, e.target.value)}
                                                        />
                                                    </TableCell>
                                                    <TableCell className={`text-right font-mono text-xs ${isManual ? 'font-bold text-blue-600' : ''}`}>
                                                        {lower} - {upper}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-4 text-muted-foreground">
                                                No expirations found for this week.
                                                {(item.ticker === '/ES' || item.ticker === '/NQ') && (
                                                    <div className="text-xs text-red-400 mt-1">
                                                        API Error: Futures data currently unavailable.
                                                    </div>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* History Dialog */}
            <EmHistoryView
                ticker={selectedTicker}
                open={historyOpen}
                onOpenChange={setHistoryOpen}
            />
        </div>
    );
}
