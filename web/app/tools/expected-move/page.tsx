'use client';

import React, { useEffect, useState } from 'react';
import { getExpectedMoveData } from '@/actions/get-expected-move';
import { updateManualEm } from '@/actions/update-manual-em';
import { updateExpectedMoveEntry } from '@/actions/update-expected-move-entry';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Loader2, RefreshCw, History, Trash2, PlusCircle, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { AddTicker } from '@/components/expected-move/add-ticker';
import { EmHistoryView } from '@/components/expected-move/em-history-view';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip"

interface BasisCalc {
    price: number;
    index_em: number;
    etf_em?: number;
}

interface BasisData {
    open: BasisCalc;
    close: BasisCalc;
    last: BasisCalc;
}

interface ExpirationData {
    id?: number; // DB ID
    date: string;
    dte: number;
    straddle: number;
    em_365: number;
    em_252: number;
    adj_em: number;
    manual_em?: number | null;

    // New Fields
    basis?: BasisData;
    note?: string;
}

interface TickerData {
    ticker: string;
    price: number;
    expirations: ExpirationData[];
}

import { DEFAULT_WATCHLIST } from "@/lib/watchlist-constants";

export default function ExpectedMovePage() {
    const [tickers, setTickers] = useState<string[]>(DEFAULT_WATCHLIST);
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
            fetchData(false, updated);
        }
    };

    const handleRemoveTicker = (tickerToRemove: string) => {
        const updated = tickers.filter(t => t !== tickerToRemove);
        setTickers(updated);
        setData(prev => prev.filter(d => d.ticker !== tickerToRemove));
    };

    const handleManualPriceChange = async (tickerIndex: number, newValue: string) => {
        const val = parseFloat(newValue);
        if (isNaN(val)) return;

        const newData = [...data];
        newData[tickerIndex].price = val;
        setData(newData);

        // We update the FIRST expiration or ALL? 
        // Price is technically per-row in DB but logically per-ticker for the week.
        // We'll update for the nearest expiry (or if empty, waiting for expiry creation).
        // Actually, updateExpectedMoveEntry expects an expiry.
        // If we have expirations, update them all? Or just the first?
        // Let's assume we update the first available or we need an expiry to save.
        // If no expirations, we can't save to DB yet (need unique key).
        // So we just hold state until they add an expiry?
        // Or we auto-create a default expiry?

        // For now, simple optimistic update of local state.
        // DB save happens when they edit an EM row or "Add Expiration".
    };

    const handleManualEmChange = async (tickerIndex: number, expIndex: number, newValue: string) => {
        const val = parseFloat(newValue);
        if (isNaN(val)) return;

        // Optimistic Update
        const newData = [...data];
        const item = newData[tickerIndex];
        const exp = item.expirations[expIndex];
        exp.manual_em = val;
        setData(newData);

        // Server Update
        await updateExpectedMoveEntry(item.ticker, exp.date, {
            price: item.price, // Save current price too
            expiryDate: exp.date,
            manualEm: val
        });
    };

    const handleAddManualExpiration = async (tickerIndex: number) => {
        const item = data[tickerIndex];
        // Default to this Friday
        const today = new Date();
        const friday = new Date(today);
        friday.setDate(today.getDate() + (5 - today.getDay() + 7) % 7);
        const dateStr = friday.toISOString().split('T')[0];

        // Check if exists
        if (item.expirations.some(e => e.date === dateStr)) return;

        // Optimistic append
        const newExp: ExpirationData = {
            date: dateStr,
            dte: Math.ceil((friday.getTime() - Date.now()) / (1000 * 3600 * 24)),
            straddle: 0,
            em_365: 0,
            em_252: 0,
            adj_em: 0,
            manual_em: 0
        };

        const newData = [...data];
        newData[tickerIndex].expirations.push(newExp);
        setData(newData);

        // Persist default entry
        await updateExpectedMoveEntry(item.ticker, dateStr, {
            price: item.price,
            expiryDate: dateStr,
            manualEm: 0
        });
    };

    const openHistory = (ticker: string) => {
        setSelectedTicker(ticker);
        setHistoryOpen(true);
    };

    return (
        <TooltipProvider>
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
                    {data.map((item, tIdx) => {
                        const isManualPrice = item.price === 0 && !item.expirations.some(e => e.basis); // Only strictly manual if no basis data

                        return (
                            <Card key={item.ticker} className="overflow-hidden">
                                <CardHeader className="bg-muted/50 py-3">
                                    <div className="flex justify-between items-center">
                                        <CardTitle className="text-lg flex items-center gap-2">
                                            {item.ticker}
                                            {isManualPrice ? (
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="destructive" className="text-xs">Manual Entry</Badge>
                                                    <Input
                                                        className="h-7 w-24 bg-white dark:bg-black"
                                                        type="number"
                                                        placeholder="Price"
                                                        defaultValue={item.price || ''}
                                                        onBlur={(e) => handleManualPriceChange(tIdx, e.target.value)}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="secondary" className="font-mono">${item.price.toFixed(2)}</Badge>
                                                    {item.expirations[0]?.note && (
                                                        <Badge variant="outline" className="text-xs text-muted-foreground border-blue-200 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-800">
                                                            {item.expirations[0].note}
                                                        </Badge>
                                                    )}
                                                </div>
                                            )}
                                        </CardTitle>
                                        <div className="flex gap-2">
                                            <Button variant="ghost" size="sm" onClick={() => openHistory(item.ticker)}>
                                                <History className="h-4 w-4 mr-2" />
                                                History
                                            </Button>
                                            {!DEFAULT_WATCHLIST.includes(item.ticker) && (
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
                                                <TableHead className="text-right font-bold w-[180px]">Adj (85%)</TableHead>
                                                <TableHead className="text-right w-[100px]">My Value</TableHead>
                                                <TableHead className="text-right w-[180px]">Range</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {item.expirations.length > 0 ? (
                                                item.expirations.map((exp, eIdx) => {
                                                    // Determine the Value to Use
                                                    let displayEm = exp.adj_em;
                                                    let etfEm = undefined;

                                                    if (exp.basis) {
                                                        displayEm = exp.basis.close.index_em;
                                                        etfEm = exp.basis.close.etf_em;
                                                    }

                                                    const effectiveEm = exp.manual_em || displayEm;
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
                                                            <TableCell className="text-right">

                                                                {exp.basis ? (
                                                                    <Tooltip>
                                                                        <TooltipTrigger asChild>
                                                                            <div className="flex flex-col items-end cursor-help">
                                                                                <span className={`font-bold ${exp.adj_em > 0 ? 'text-primary' : 'text-gray-400'}`}>
                                                                                    ${displayEm.toFixed(2)}
                                                                                </span>
                                                                                {etfEm && (
                                                                                    <span className="text-xs text-muted-foreground">
                                                                                        ETF: ${etfEm.toFixed(2)}
                                                                                    </span>
                                                                                )}
                                                                            </div>
                                                                        </TooltipTrigger>
                                                                        <TooltipContent className="p-4 w-64 bg-background border border-border shadow-md">
                                                                            <div className="space-y-2">
                                                                                <h4 className="font-semibold text-sm border-b pb-1 mb-1">Calculation Basis</h4>
                                                                                <div className="grid grid-cols-2 gap-2 text-xs">
                                                                                    <div className="font-medium">Index Close</div>
                                                                                    <div className="text-right font-bold">${exp.basis.close.index_em.toFixed(2)}</div>

                                                                                    <div className="font-medium text-muted-foreground">ETF Close</div>
                                                                                    <div className="text-right text-muted-foreground">${exp.basis.close.etf_em?.toFixed(2)}</div>

                                                                                    <div className="font-medium mt-2">Index Open</div>
                                                                                    <div className="text-right mt-2 font-bold">${exp.basis.open.index_em.toFixed(2)}</div>

                                                                                    <div className="font-medium text-muted-foreground">ETF Open</div>
                                                                                    <div className="text-right text-muted-foreground">${exp.basis.open.etf_em?.toFixed(2)}</div>
                                                                                </div>
                                                                            </div>
                                                                        </TooltipContent>
                                                                    </Tooltip>
                                                                ) : (
                                                                    <span className={`font-bold ${exp.adj_em > 0 ? 'text-primary' : 'text-gray-400'}`}>
                                                                        ${displayEm.toFixed(2)}
                                                                    </span>
                                                                )}

                                                            </TableCell>
                                                            <TableCell className="text-right p-1">
                                                                <Input
                                                                    className="h-8 w-24 text-right ml-auto"
                                                                    type="number"
                                                                    step="0.1"
                                                                    placeholder="-"
                                                                    defaultValue={exp.manual_em || ''}
                                                                    onBlur={(e) => handleManualEmChange(tIdx, eIdx, e.target.value)}
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
                                                        No expirations found.
                                                        <Button
                                                            variant="secondary"
                                                            size="sm"
                                                            className="ml-4"
                                                            onClick={() => handleAddManualExpiration(tIdx)}
                                                        >
                                                            <PlusCircle className="mr-2 h-3 w-3" />
                                                            Add Manual Expiry
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>

                {/* History Dialog */}
                <EmHistoryView
                    ticker={selectedTicker}
                    open={historyOpen}
                    onOpenChange={setHistoryOpen}
                />
            </div>
        </TooltipProvider>
    );
}
