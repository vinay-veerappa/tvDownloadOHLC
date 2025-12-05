"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { runBacktest } from "@/actions/backtest-actions"

export default function BacktestPage() {
    const [logs, setLogs] = useState<string[]>([])
    const [running, setRunning] = useState(false)

    const handleRunBacktest = async () => {
        setRunning(true)
        setLogs(prev => [...prev, "Starting backtest..."])

        const result = await runBacktest()

        if (result.success && result.logs) {
            setLogs(prev => [...prev, ...result.logs])
        } else {
            setLogs(prev => [...prev, "Backtest failed or returned no logs."])
        }

        setRunning(false)
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Backtesting</h2>
                <Button onClick={handleRunBacktest} disabled={running}>
                    {running ? "Running..." : "Run Backtest"}
                </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Strategy Configuration</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground">
                            Strategy selection and parameter tuning will go here.
                        </p>
                    </CardContent>
                </Card>

                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Execution Logs</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[400px] w-full rounded-md border bg-muted p-4 font-mono text-xs overflow-auto">
                            {logs.length === 0 ? (
                                <span className="text-muted-foreground">No logs yet.</span>
                            ) : (
                                logs.map((log, i) => (
                                    <div key={i} className="mb-1">
                                        {log}
                                    </div>
                                ))
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
