"use server" // Ensure this is a server component to fetch initial data

import { getDashboardContext } from "@/actions/context-actions"
import { YahooQuote, YahooNewsItem } from "@/lib/yahoo-finance"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Newspaper } from "lucide-react"
import { detectSession } from "@/lib/market-utils"
import { ContextForm } from "@/components/journal/context/context-form"
import { WatchlistWidget } from "@/components/journal/context/watchlist-widget"
import { EconomicCalendarWidget } from "@/components/journal/context/economic-calendar-widget"
import { MarketOverviewWidget } from "@/components/journal/context/market-overview-widget"
import { MarketNewsWidget } from "@/components/journal/context/market-news-widget"

export default async function ContextDashboardPage() {
    const contextResult = await getDashboardContext()
    const { marketData, news, dailyNote, events, watchlist } = contextResult.success && contextResult.data ? contextResult.data : {
        marketData: [], news: [], dailyNote: null, events: [], watchlist: []
    }

    const today = new Date()
    const currentSession = detectSession(today)

    // Reconstruct news query for consistency with initial fetch
    const watchlistSymbols = watchlist.map(w => w.symbol)
    const keySymbols = ["SPY", ...watchlistSymbols.slice(0, 3)]
    // Use simple space or comma for multiple terms. Yahoo search handles space as flexible match.
    const newsQuery = keySymbols.join(" ") + " news"

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between space-y-2">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Market Context</h2>
                    <p className="text-muted-foreground">
                        Daily preparation and market overview
                    </p>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <div className="col-span-full flex items-center gap-2">
                    <Badge variant="outline" className="text-sm py-1 px-3">
                        Session: <span className="font-semibold ml-1">{currentSession}</span>
                    </Badge>
                </div>
            </div>

            {/* Market Overview Grid (Top Indices) */}
            <MarketOverviewWidget initialQuotes={marketData} />

            <div className="grid gap-6 md:grid-cols-12">
                {/* 1. Daily Context Form */}
                <div className="md:col-span-3 space-y-6">
                    <ContextForm initialNote={dailyNote} />
                </div>

                {/* 2. Watchlist (New) */}
                <div className="md:col-span-3 space-y-6">
                    <WatchlistWidget watchlist={watchlist} quotes={marketData} />
                </div>

                {/* 3. Economic Calendar */}
                <div className="md:col-span-3 space-y-6">
                    <EconomicCalendarWidget initialEvents={events} />
                </div>

                {/* 4. News */}
                <div className="md:col-span-3 space-y-6">
                    <MarketNewsWidget initialNews={news} defaultQuery={newsQuery} />
                </div>
            </div>
        </div>
    )
}
