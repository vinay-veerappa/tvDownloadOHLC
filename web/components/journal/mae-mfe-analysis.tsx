"use client"

import { useEffect, useState } from "react"
import { getMaeMfeAnalysis, MaeMfePoint } from "@/actions/analytics-actions"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, Cell, ReferenceLine } from "recharts"

export function MaeMfeAnalysis() {
    const [data, setData] = useState<MaeMfePoint[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function loadData() {
            const result = await getMaeMfeAnalysis()
            if (result.success && result.data) {
                setData(result.data)
            }
            setLoading(false)
        }
        loadData()
    }, [])

    if (loading) return <div className="h-[300px] flex items-center justify-center">Loading Analysis...</div>
    if (data.length === 0) return <div className="h-[300px] flex items-center justify-center text-muted-foreground">No MAE/MFE data available for closed trades.</div>

    return (
        <div className="grid gap-4 md:grid-cols-2">
            <Card>
                <CardHeader>
                    <CardTitle>MAE vs MFE (%)</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                <XAxis type="number" dataKey="maePercent" name="MAE %" unit="%" label={{ value: 'Adverse (Bad)', position: 'insideBottom', offset: -10 }} />
                                <YAxis type="number" dataKey="mfePercent" name="MFE %" unit="%" label={{ value: 'Favorable (Good)', angle: -90, position: 'insideLeft' }} />
                                <ZAxis type="number" range={[40, 40]} />
                                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                <ReferenceLine y={0} stroke="#666" />
                                <ReferenceLine x={0} stroke="#666" />
                                <Scatter name="Trades" data={data} fill="#8884d8">
                                    {data.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.win ? "#22c55e" : "#ef4444"} />
                                    ))}
                                </Scatter>
                            </ScatterChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Analysis Insights</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div>
                            <div className="text-sm font-medium text-muted-foreground">Average MAE (Pain Tolerance)</div>
                            <div className="text-2xl font-bold">
                                {(data.reduce((acc, curr) => acc + curr.maePercent, 0) / data.length).toFixed(2)}%
                            </div>
                        </div>
                        <div>
                            <div className="text-sm font-medium text-muted-foreground">Average MFE (Potential Reach)</div>
                            <div className="text-2xl font-bold">
                                {(data.reduce((acc, curr) => acc + curr.mfePercent, 0) / data.length).toFixed(2)}%
                            </div>
                        </div>
                        <div>
                            <div className="text-sm font-medium text-muted-foreground">Correlation</div>
                            <div className="text-sm text-muted-foreground">
                                Green dots = Winning trades. Red dots = Losing trades.<br/>
                                Ideal trades are in the Top-Left quadrant (Low MAE, High MFE).
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
