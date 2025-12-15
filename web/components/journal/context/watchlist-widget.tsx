"use client"

import { useState, useEffect } from "react"
import { YahooQuote } from "@/lib/yahoo-finance"
import { addToWatchlist, removeFromWatchlist, searchTicker } from "@/actions/watchlist-actions"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, Trash2, TrendingUp, TrendingDown, Minus, List } from "lucide-react"

interface WatchlistWidgetProps {
    watchlist: any[]
    quotes: YahooQuote[]
}

export function WatchlistWidget({ watchlist, quotes }: WatchlistWidgetProps) {
    const [searchQuery, setSearchQuery] = useState("")
    const [searchResults, setSearchResults] = useState<any[]>([])
    const [showResults, setShowResults] = useState(false)
    const [adding, setAdding] = useState(false)

    // De-bounce search
    useEffect(() => {
        const timer = setTimeout(async () => {
            if (searchQuery.length >= 2) {
                const res = await searchTicker(searchQuery)
                if (res.success && res.data) {
                    setSearchResults(res.data)
                    setShowResults(true)
                }
            } else {
                setSearchResults([])
                setShowResults(false)
            }
        }, 500)
        return () => clearTimeout(timer)
    }, [searchQuery])

    const handleSelect = async (symbol: string, name?: string) => {
        setSearchQuery(symbol)
        setShowResults(false)

        setAdding(true)
        const result = await addToWatchlist(symbol)

        if (!result.success) {
            alert(result.error || "Failed to add symbol")
        } else {
            setSearchQuery("")
        }
        setAdding(false)
    }

    const handleRemove = async (id: string) => {
        if (confirm("Remove from watchlist?")) {
            await removeFromWatchlist(id)
        }
    }

    // Merge DB items with live quotes
    const items = watchlist.map(item => {
        const quote = quotes.find(q => q.symbol === item.symbol)
        return {
            ...item,
            quote
        }
    })

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                    <List className="h-5 w-5" />
                    Watchlist
                </CardTitle>
                <CardDescription>Track key tickers</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 flex-1 overflow-hidden flex flex-col">
                <div className="relative">
                    <Input
                        placeholder="Search Symbol (e.g. NVDA)"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="uppercase"
                    />
                    {showResults && searchResults.length > 0 && (
                        <div className="absolute top-full left-0 right-0 z-10 bg-background border rounded-md shadow-lg mt-1 max-h-60 overflow-y-auto">
                            {searchResults.map((res: any) => (
                                <button
                                    key={res.symbol}
                                    className="w-full text-left px-3 py-2 hover:bg-muted text-sm flex justify-between items-center"
                                    onClick={() => handleSelect(res.symbol, res.shortname)}
                                >
                                    <span className="font-bold">{res.symbol}</span>
                                    <span className="text-muted-foreground truncate max-w-[150px]">{res.shortname}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                <div className="space-y-1 overflow-y-auto flex-1 pr-1">
                    {items.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            No symbols observed.
                        </p>
                    ) : (
                        items.map((item) => (
                            <div key={item.id} className="flex items-center justify-between p-2 hover:bg-muted/50 rounded group gap-2">
                                <div className="flex flex-col min-w-0 flex-1">
                                    <span className="font-bold">{item.symbol}</span>
                                    <span className="text-xs text-muted-foreground line-clamp-1 truncate">{item.name}</span>
                                </div>

                                {item.quote && typeof item.quote.price === 'number' ? (
                                    <div className="text-right shrink-0">
                                        <div className="font-mono text-sm">{item.quote.price.toFixed(2)}</div>
                                        <div className={`text-xs flex items-center justify-end ${item.quote.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            {item.quote.change >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                                            {item.quote.changePercent?.toFixed(2)}%
                                        </div>
                                    </div>
                                ) : (
                                    <span className="text-xs text-muted-foreground shrink-0 w-16 text-right">
                                        {item.quote ? "N/A" : "Loading..."}
                                    </span>
                                )}

                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 text-muted-foreground hover:text-destructive shrink-0"
                                    onClick={() => handleRemove(item.id)}
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                        ))
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
