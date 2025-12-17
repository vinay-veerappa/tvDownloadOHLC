"use client";

import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { getTickerHistory } from "@/actions/get-ticker-history";
import { Loader2 } from "lucide-react";
import {
    ComposedChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Area
} from "recharts";

interface HistoryViewProps {
    ticker: string | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function EmHistoryView({ ticker, open, onOpenChange }: HistoryViewProps) {
    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (open && ticker) {
            loadHistory(ticker);
        }
    }, [open, ticker]);

    const loadHistory = async (t: string) => {
        setLoading(true);
        const res = await getTickerHistory(t);
        if (res.success && res.data) {
            // Sort asc for chart
            const sorted = [...res.data].sort((a, b) => new Date(a.calculationDate).getTime() - new Date(b.calculationDate).getTime());
            setData(sorted);
        }
        setLoading(false);
    };

    if (!ticker) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Historical Expected Moves: {ticker}</DialogTitle>
                </DialogHeader>

                {loading ? (
                    <div className="flex justify-center p-8">
                        <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                ) : (
                    <div className="space-y-6">
                        {/* Chart */}
                        <div className="h-[300px] w-full border rounded-lg p-4 bg-slate-50 dark:bg-slate-900">
                            <ResponsiveContainer width="100%" height="100%">
                                <ComposedChart data={data}>
                                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                    <XAxis
                                        dataKey="calculationDate"
                                        tickFormatter={(val) => new Date(val).toLocaleDateString()}
                                        minTickGap={30}
                                    />
                                    <YAxis domain={['auto', 'auto']} />
                                    <Tooltip
                                        labelFormatter={(val) => new Date(val).toLocaleDateString()}
                                    />
                                    <Legend />
                                    <Line type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} name="Price" dot={false} />

                                    {/* Bands? A bit hard since we have multiple expirations per day possibly? 
                      Actually our DB constraint is unique ticker, calcDate, expiryDate. 
                      If we have multiple expiries for same day, chart might be messy.
                      Let's filtering for the "nearest" expiry or just showing Price vs AdjEM value?
                      AdjEM is a value, not a price level. 
                      Let's plot Price +/- AdjEM as a range.
                  */}
                                    <Area
                                        type="monotone"
                                        dataKey="upper"
                                        fill="#82ca9d"
                                        stroke="#82ca9d"
                                        fillOpacity={0.1}
                                        name="Expected Move"
                                        data={data.map(d => ({ ...d, upper: d.price + d.adjEm, lower: d.price - d.adjEm }))}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="lower"
                                        stroke="#82ca9d"
                                        strokeDasharray="3 3"
                                        dot={false}
                                        data={data.map(d => ({ ...d, lower: d.price - d.adjEm }))}
                                        name="Lower Bound"
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="upper"
                                        stroke="#82ca9d"
                                        strokeDasharray="3 3"
                                        dot={false}
                                        data={data.map(d => ({ ...d, upper: d.price + d.adjEm }))}
                                        name="Upper Bound"
                                        legendType="none" // Hide duplicate
                                    />

                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Table */}
                        <div className="border rounded-md">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Calc Date</TableHead>
                                        <TableHead>Expiry</TableHead>
                                        <TableHead className="text-right">Price</TableHead>
                                        <TableHead className="text-right">Straddle</TableHead>
                                        <TableHead className="text-right">Adj EM</TableHead>
                                        <TableHead className="text-right">Manual</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {[...data].reverse().map((row) => (
                                        <TableRow key={row.id}>
                                            <TableCell>{new Date(row.calculationDate).toLocaleDateString()}</TableCell>
                                            <TableCell>{new Date(row.expiryDate).toLocaleDateString()}</TableCell>
                                            <TableCell className="text-right">{row.price.toFixed(2)}</TableCell>
                                            <TableCell className="text-right">{row.straddle.toFixed(2)}</TableCell>
                                            <TableCell className="text-right font-bold text-green-600">{row.adjEm.toFixed(2)}</TableCell>
                                            <TableCell className="text-right text-blue-600">{row.manualEm || '-'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
