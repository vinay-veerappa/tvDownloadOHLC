"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { executeBacktest } from "@/actions/backtest-actions"
import { BacktestResult } from "@/lib/backtest/runner"
import { toast } from "sonner"
import { ChartContainer } from "@/components/chart-container"

export default function BacktestPage() {
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<BacktestResult | null>(null)
    const [markers, setMarkers] = useState<any[]>([])

    const [config, setConfig] = useState<{
        ticker: string
        timeframe: string
        strategy: string
        fastPeriod: number
        slowPeriod: number
        tp_mode: 'R' | 'BPS'
        tp_value: number
        max_trades: number
    }>({
        ticker: "ES1",
        timeframe: "1h",
        strategy: "SMA_CROSSOVER",
        fastPeriod: 9,
        slowPeriod: 21,
        tp_mode: 'R',
        tp_value: 1.0,
        max_trades: 0 // Unlimited
    })

    const handleRun = async () => {
        setLoading(true)
        try {
            const res = await executeBacktest({
                ticker: config.ticker,
                timeframe: config.timeframe,
                strategy: config.strategy,
                params: config.strategy === 'SMA_CROSSOVER' ? {
                    fastPeriod: config.fastPeriod,
                    slowPeriod: config.slowPeriod
                } : {
                    tp_mode: config.tp_mode,
                    tp_value: config.tp_value,
                    max_trades: config.max_trades
                }
            })

            if (res.success && res.result) {
                setResult(res.result)

                // Transform trades to markers
                const newMarkers = res.result.trades.flatMap(t => [
                    {
                        time: t.entryDate,
                        position: t.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                        color: t.direction === 'LONG' ? '#2196F3' : '#E91E63',
                        shape: t.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                        text: `Entry ${t.direction}`
                    },
                    {
                        time: t.exitDate,
                        position: t.direction === 'LONG' ? 'aboveBar' : 'belowBar',
                        color: t.pnl > 0 ? '#4CAF50' : '#F44336',
                        shape: t.direction === 'LONG' ? 'arrowDown' : 'arrowUp',
                        text: `Exit (${t.pnl.toFixed(2)})`
                    }
                ]).sort((a, b) => (a.time as number) - (b.time as number))

                setMarkers(newMarkers)

                toast.success("Backtest completed")
            } else {
                toast.error(res.error || "Backtest failed")
            }
        } catch (e) {
            toast.error("An unexpected error occurred")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="container mx-auto p-4 space-y-4">
            <h1 className="text-2xl font-bold">Backtesting Platform</h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Configuration Panel */}
                <Card className="md:col-span-1">
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label>Strategy</Label>
                            <select
                                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                value={config.strategy}
                                onChange={(e) => {
                                    const strat = e.target.value
                                    if (strat === 'NQ_1MIN') {
                                        setConfig({ ...config, strategy: strat, ticker: 'NQ1!', timeframe: '1m' })
                                    } else {
                                        setConfig({ ...config, strategy: strat })
                                    }
                                }}
                            >
                                <option value="SMA_CROSSOVER">SMA Crossover</option>
                                <option value="NQ_1MIN">NQ 9:30 Reversal</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <Label>Ticker</Label>
                            <Input
                                value={config.ticker}
                                onChange={(e) => setConfig({ ...config, ticker: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Timeframe</Label>
                            <Input
                                value={config.timeframe}
                                onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}
                            />
                        </div>

                        {config.strategy === 'SMA_CROSSOVER' && (
                            <>
                                <div className="space-y-2">
                                    <Label>Fast SMA</Label>
                                    <Input
                                        type="number"
                                        value={config.fastPeriod}
                                        onChange={(e) => setConfig({ ...config, fastPeriod: parseInt(e.target.value) })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Slow SMA</Label>
                                    <Input
                                        type="number"
                                        value={config.slowPeriod}
                                        onChange={(e) => setConfig({ ...config, slowPeriod: parseInt(e.target.value) })}
                                    />
                                </div>
                            </>
                        )}

                        {config.strategy === 'NQ_1MIN' && (
                            <div className="space-y-4 border-l-2 border-muted pl-4">
                                <div className="space-y-2">
                                    <Label>TP Mode</Label>
                                    <select
                                        title="Take Profit Mode"
                                        className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                        value={config.tp_mode}
                                        onChange={(e) => setConfig({ ...config, tp_mode: e.target.value as 'R' | 'BPS' })}
                                    >
                                        <option value="R">R-Multiple (Risk units)</option>
                                        <option value="BPS">Basis Points (bps)</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label>{config.tp_mode === 'R' ? 'R-Multiple Value' : 'Basis Points Value'}</Label>
                                    <Input
                                        title={config.tp_mode === 'R' ? "Example: 1.0 for 1R" : "Example: 10 for 10bps"}
                                        type="number"
                                        step={config.tp_mode === 'R' ? "0.1" : "1"}
                                        value={config.tp_value}
                                        onChange={(e) => setConfig({ ...config, tp_value: parseFloat(e.target.value) })}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        {config.tp_mode === 'R' ? 'Default: 1.0 (1x Risk)' : 'Default: 10 (0.10%)'}
                                    </p>
                                </div>
                                <div className="space-y-2">
                                    <Label>Max Trades (0 = All)</Label>
                                    <Input
                                        title="Maximum number of trades to execute"
                                        type="number"
                                        value={config.max_trades}
                                        onChange={(e) => setConfig({ ...config, max_trades: parseInt(e.target.value) })}
                                    />
                                </div>
                            </div>
                        )}

                        <Button className="w-full" onClick={handleRun} disabled={loading}>
                            {loading ? "Running..." : "Run Backtest"}
                        </Button>
                    </CardContent>
                </Card>

                {/* Results Panel */}
                <Card className="md:col-span-2 flex flex-col h-[800px]">
                    <CardHeader>
                        <CardTitle>Results</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col min-h-0">
                        {result ? (
                            <div className="space-y-4 flex-1 flex flex-col">
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div className="p-4 bg-muted rounded-lg text-center">
                                        <div className="text-sm text-muted-foreground">Total Trades</div>
                                        <div className="text-2xl font-bold">{result.totalTrades}</div>
                                    </div>
                                    <div className="p-4 bg-muted rounded-lg text-center">
                                        <div className="text-sm text-muted-foreground">Win Rate</div>
                                        <div className="text-2xl font-bold">{result.winRate.toFixed(1)}%</div>
                                    </div>
                                    <div className="p-4 bg-muted rounded-lg text-center">
                                        <div className="text-sm text-muted-foreground">Profit Factor</div>
                                        <div className="text-2xl font-bold">{result.profitFactor.toFixed(2)}</div>
                                    </div>
                                    <div className="p-4 bg-muted rounded-lg text-center">
                                        <div className="text-sm text-muted-foreground">Total PnL</div>
                                        <div className={`text-2xl font-bold ${result.totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            ${result.totalPnl.toFixed(2)}
                                        </div>
                                    </div>
                                </div>

                                {/* Chart */}
                                <div className="flex-1 min-h-[400px] border rounded-lg overflow-hidden relative">
                                    <ChartContainer
                                        ticker={config.ticker}
                                        timeframe={config.timeframe}
                                        style="candles"
                                        indicators={[`sma:${config.fastPeriod}`, `sma:${config.slowPeriod}`]}
                                        selectedTool="cursor"
                                        onToolSelect={() => { }}
                                        onDrawingCreated={() => { }}
                                        markers={markers}
                                    />
                                </div>

                                {/* Trade List Preview */}
                                <div className="border rounded-md max-h-[200px] overflow-y-auto">
                                    <div className="p-2 bg-muted font-medium grid grid-cols-5 gap-2 text-sm sticky top-0">
                                        <div>Entry Date</div>
                                        <div>Type</div>
                                        <div>Entry</div>
                                        <div>Exit</div>
                                        <div>PnL</div>
                                    </div>
                                    <div>
                                        {result.trades.slice().reverse().map((trade, i) => (
                                            <div key={i} className="p-2 border-t grid grid-cols-5 gap-2 text-sm hover:bg-muted/50">
                                                <div>{new Date(trade.entryDate * 1000).toLocaleDateString()}</div>
                                                <div className={trade.direction === 'LONG' ? 'text-green-500' : 'text-red-500'}>{trade.direction}</div>
                                                <div>{trade.entryPrice.toFixed(2)}</div>
                                                <div>{trade.exitPrice.toFixed(2)}</div>
                                                <div className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                    {trade.pnl.toFixed(2)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full border-2 border-dashed rounded-lg text-muted-foreground">
                                Run a backtest to see results
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
