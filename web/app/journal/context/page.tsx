"use server" // Ensure this is a server component to fetch initial data

import { getDashboardContext } from "@/actions/context-actions"
import { YahooQuote, YahooNewsItem } from "@/lib/yahoo-finance"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { TrendingUp, TrendingDown, Minus, RefreshCw, Calendar, Globe, Newspaper } from "lucide-react"
import { detectSession } from "@/lib/market-utils"
import { ContextForm } from "@/components/journal/context/context-form"
import { WatchlistWidget } from "@/components/journal/context/watchlist-widget"

export default async function ContextDashboardPage() {
    const contextResult = await getDashboardContext()
    const { marketData, news, dailyNote, events, watchlist } = contextResult.success && contextResult.data ? contextResult.data : {
        marketData: [], news: [], dailyNote: null, events: [], watchlist: []
    }

    const today = new Date()
    const currentSession = detectSession(today)

    // Filter quotes for watchlist items
    // The marketData array contains everything (Indices + Watchlist), we filter by symbol matching
    // Note: This matches simple symbols. Yahoo might return ^GSPC for SPY sometimes but usually query matches result.
    // For simplicity, we pass the whole marketData to the widget and let it find what it needs, or filter here.
    // Actually, passing the whole marketData array is fine, the widget maps over the watchlist items and finds the quote.

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Market Context</h2>
                    <p className="text-muted-foreground">
                        {today.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-sm py-1 px-3">
                        Session: <span className="font-semibold ml-1">{currentSession}</span>
                    </Badge>
                </div>
            </div>

            {/* Market Overview Grid (Top Indices) */}
            <div className="grid gap-4 md:grid-cols-4">
                {marketData.filter(q => ["^VIX", "^VVIX", "SPY", "QQQ"].includes(q.symbol)).map((quote: YahooQuote) => (
                    <Card key={quote.symbol}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">
                                {quote.name || quote.symbol}
                            </CardTitle>
                            {quote.changePercent > 0 ? (
                                <TrendingUp className="h-4 w-4 text-green-500" />
                            ) : quote.changePercent < 0 ? (
                                <TrendingDown className="h-4 w-4 text-red-500" />
                            ) : (
                                <Minus className="h-4 w-4 text-muted-foreground" />
                            )}
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{quote.price.toFixed(2)}</div>
                            <p className={`text-xs ${quote.changePercent >= 0 ? "text-green-500" : "text-red-500"}`}>
                                {quote.change > 0 ? "+" : ""}{quote.change.toFixed(2)} ({quote.changePercent.toFixed(2)}%)
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

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
                    <Card className="h-full">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Calendar className="h-5 w-5" />
                                Economic Events
                            </CardTitle>
                            <CardDescription>Scheduled events for today</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {events.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    No events scheduled for today.
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {events.map((event: any) => (
                                        <div key={event.id} className="flex items-center justify-between border-b pb-2 last:border-0 hover:bg-muted/50 p-2 rounded">
                                            <div>
                                                <p className="font-medium text-sm">{event.name}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {new Date(event.datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                </p>
                                            </div>
                                            <Badge variant={
                                                event.impact === 'HIGH' ? 'destructive' :
                                                    event.impact === 'MEDIUM' ? 'default' : 'secondary'
                                            }>
                                                {event.impact}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* 4. News */}
                <div className="md:col-span-3 space-y-6">
                    <Card className="h-full">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Newspaper className="h-5 w-5" />
                                Market News
                            </CardTitle>
                            <CardDescription>Latest headlines</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                {news.slice(0, 5).map((item: YahooNewsItem) => (
                                    <div key={item.uuid} className="group">
                                        <div className="flex flex-col space-y-1">
                                            <a href={item.link} target="_blank" rel="noopener noreferrer" className="font-medium text-sm group-hover:underline line-clamp-2">
                                                {item.title}
                                            </a>
                                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                                <span>{item.publisher}</span>
                                                <span>{new Date(item.providerPublishTime * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                            </div>
                                        </div>
                                        <Separator className="my-3" />
                                    </div>
                                ))}
                                <a href="https://finance.yahoo.com/news/" target="_blank" rel="noopener noreferrer" className="block text-center text-xs text-muted-foreground hover:underline pt-2">
                                    View on Yahoo Finance
                                </a>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
