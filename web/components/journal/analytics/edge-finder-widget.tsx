"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getEdgeFinderStats, EdgeStat } from "@/actions/analytics-actions"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts"

interface EdgeFinderProps {
  accountId?: string;
}

export function EdgeFinderWidget({ accountId }: EdgeFinderProps) {
  const [activeTab, setActiveTab] = useState<"timeframe" | "session" | "marketCondition" | "setup" | "dayOfWeek">("session")
  const [data, setData] = useState<EdgeStat[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const stats = await getEdgeFinderStats(activeTab, { accountId })
        setData(stats)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [activeTab, accountId])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload as EdgeStat;
      return (
        <div className="bg-background border rounded p-2 shadow-lg text-xs">
          <p className="font-bold mb-1">{label}</p>
          <p>Trades: {d.trades}</p>
          <p className={d.pnl >= 0 ? "text-green-500" : "text-red-500"}>
             PnL: ${d.pnl.toFixed(2)}
          </p>
          <p>Win Rate: {d.winRate.toFixed(1)}%</p>
          <p>PF: {d.pf.toFixed(2)}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="col-span-2">
      <CardHeader>
        <div className="flex items-center justify-between">
            <CardTitle>Edge Finder</CardTitle>
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-auto">
                <TabsList className="grid grid-cols-5 h-8">
                    <TabsTrigger value="session" className="text-xs px-2">Session</TabsTrigger>
                    <TabsTrigger value="dayOfWeek" className="text-xs px-2">Day</TabsTrigger>
                    <TabsTrigger value="setup" className="text-xs px-2">Setup</TabsTrigger>
                    <TabsTrigger value="timeframe" className="text-xs px-2">TF</TabsTrigger>
                    <TabsTrigger value="marketCondition" className="text-xs px-2">Cond</TabsTrigger>
                </TabsList>
            </Tabs>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
            {loading ? (
                <div className="h-full flex items-center justify-center text-muted-foreground">Analyzing...</div>
            ) : data.length === 0 ? (
                <div className="h-full flex items-center justify-center text-muted-foreground">No data found</div>
            ) : (
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                        <XAxis type="number" hide />
                        <YAxis dataKey="group" type="category" width={80} tick={{fontSize: 12}} />
                        <Tooltip content={<CustomTooltip />} cursor={{fill: 'hsl(var(--muted)/0.2)'}} />
                        <ReferenceLine x={0} stroke="hsl(var(--muted-foreground))" />
                        <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? "hsl(var(--chart-2))" : "hsl(var(--chart-5))"} /> // Green/Red using CSS vars if possible, else hardcode
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            )}
        </div>
      </CardContent>
    </Card>
  )
}
