import { format } from "date-fns"
import { getDailyContext } from "@/actions/routine-actions"
import { getTrades } from "@/actions/trade-actions" // Need a filtered version!
import { TradeList } from "@/components/journal/trade-list"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import prisma from "@/lib/prisma" // Direct db access for server component efficiency

interface DayPageProps {
    params: { date: string }
}

export default async function DayPage({ params }: DayPageProps) {
    const dateStr = params.date
    const date = new Date(dateStr)
    
    // Normalize range for the day
    const start = new Date(date)
    start.setHours(0, 0, 0, 0)
    const end = new Date(date)
    end.setHours(23, 59, 59, 999)

    // Fetch Data
    const [routineData, trades] = await Promise.all([
        getDailyContext(start),
        prisma.trade.findMany({
            where: {
                // Determine which date to use? Entry or Exit? Usually Exit for P&L, Entry for journal.
                // Let's grab all trades active on this day or closed on this day.
                // For simplicity, let's use Exit Date for P&L attribution, Entry Date for context.
                // Edgewonk likely uses Exit Date for P&L.
                OR: [
                    { entryDate: { gte: start, lte: end } },
                    { exitDate: { gte: start, lte: end } }
                ]
            },
            orderBy: { entryDate: 'asc' }
        })
    ])

    const { analysis, routine } = routineData

    // Calculate Day Stats
    let totalPnl = 0
    let winCount = 0
    let lossCount = 0
    trades.forEach(t => {
        if (t.exitDate && t.exitDate >= start && t.exitDate <= end) {
            const pnl = t.pnl || 0
            totalPnl += pnl
            if (pnl > 0) winCount++
            if (pnl < 0) lossCount++
        }
    })

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Link href="/journal">
                    <Button variant="ghost" size="icon">
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                </Link>
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{format(date, "EEEE, MMMM do, yyyy")}</h1>
                    <p className="text-muted-foreground">Daily Review</p>
                </div>
                <div className="ml-auto flex items-center gap-4">
                     <div className={`text-2xl font-bold ${totalPnl > 0 ? "text-green-500" : totalPnl < 0 ? "text-red-500" : ""}`}>
                        {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
                    </div>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Trades</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{trades.length}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Win/Loss</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{winCount}W / {lossCount}L</div>
                    </CardContent>
                </Card>
                <Card>
                   <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Sentiment</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{analysis?.sentiment || "-"}</div>
                    </CardContent>
                </Card>
                <Card>
                   <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Discipline</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{routine?.rating ? `${routine.rating}/10` : "-"}</div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-1">
                 <Card>
                    <CardHeader>
                        <CardTitle>Trades</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <TradeList trades={trades} />
                    </CardContent>
                </Card>
            </div>

             <div className="grid gap-4 md:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle>Daily Analysis</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {analysis?.notes ? (
                            <div className="prose dark:prose-invert">
                                <p>{analysis.notes}</p>
                            </div>
                        ) : (
                            <p className="text-muted-foreground italic">No analysis notes.</p>
                        )}
                    </CardContent>
                </Card>
                <Card>
                     <CardHeader>
                        <CardTitle>Routine & Review</CardTitle>
                    </CardHeader>
                    <CardContent>
                         {routine?.notes ? (
                            <div className="prose dark:prose-invert">
                                <p>{routine.notes}</p>
                            </div>
                        ) : (
                             <p className="text-muted-foreground italic">No routine notes.</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
