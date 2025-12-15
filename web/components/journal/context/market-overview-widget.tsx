"use client"

import { useState } from "react"
import { YahooQuote } from "@/lib/yahoo-finance"
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react"
import { getLatestQuotes } from "@/actions/context-actions"

interface MarketOverviewWidgetProps {
    initialQuotes: YahooQuote[]
}

const INDICES = ["^VIX", "^VVIX", "SPY", "QQQ"]

export function MarketOverviewWidget({ initialQuotes }: MarketOverviewWidgetProps) {
    const [quotes, setQuotes] = useState<YahooQuote[]>(initialQuotes)
    const [loading, setLoading] = useState(false)

    const fetchQuotes = async () => {
        setLoading(true)
        try {
            const res = await getLatestQuotes(INDICES)
            if (res.success && res.data) {
                setQuotes(res.data)
            }
        } catch (error) {
            console.error("Failed to fetch indices", error)
        } finally {
            setLoading(false)
        }
    }

    // Ensure we display in specific order if possible, or just map what we have
    // Filtering ensures we only show the relevant ones even if initialQuotes has more
    const displayQuotes = quotes.filter(q => INDICES.includes(q.symbol))
        .sort((a, b) => INDICES.indexOf(a.symbol) - INDICES.indexOf(b.symbol))

    // Handle missing indices if fetch failed or initial was empty by still rendering placeholders or just list
    // If empty, we might want to trigger fetch

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-end">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchQuotes}
                    disabled={loading}
                    className="h-6 px-2 text-xs text-muted-foreground"
                >
                    <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>
            <div className="grid gap-4 md:grid-cols-4">
                {displayQuotes.map((quote: YahooQuote) => (
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
        </div>
    )
}
