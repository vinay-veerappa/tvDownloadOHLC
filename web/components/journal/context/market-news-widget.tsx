"use client"

import { useState } from "react"
import { YahooNewsItem } from "@/lib/yahoo-finance"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Newspaper, RefreshCw } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { getLatestNews } from "@/actions/context-actions"

interface MarketNewsWidgetProps {
    initialNews: YahooNewsItem[]
    defaultQuery?: string
}

export function MarketNewsWidget({ initialNews, defaultQuery = "stock market" }: MarketNewsWidgetProps) {
    const [news, setNews] = useState<YahooNewsItem[]>(initialNews)
    const [loading, setLoading] = useState(false)

    const fetchNews = async () => {
        setLoading(true)
        try {
            const res = await getLatestNews(defaultQuery)
            if (res.success && res.data) {
                setNews(res.data)
            }
        } catch (error) {
            console.error("Failed to refresh news", error)
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
                <div className="flex flex-col space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                        <Newspaper className="h-5 w-5" />
                        Market News
                    </CardTitle>
                    <CardDescription>Latest headlines</CardDescription>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={fetchNews}
                    disabled={loading}
                    className="h-8 w-8"
                >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden">
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
    )
}
