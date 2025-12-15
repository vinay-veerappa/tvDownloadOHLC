export interface YahooQuote {
    symbol: string
    price: number
    change: number
    changePercent: number
    name?: string
    timestamp: number
}

export interface YahooNewsItem {
    uuid: string
    title: string
    publisher: string
    link: string
    providerPublishTime: number
    type: string
}

const YAHOO_BASE_URL = "https://query1.finance.yahoo.com/v8/finance"
const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

export async function fetchMarketData(symbols: string[]): Promise<YahooQuote[]> {
    const results: YahooQuote[] = []

    for (const symbol of symbols) {
        try {
            // Using chart API as it's more stable than quote API without auth cookie sometimes
            const url = `${YAHOO_BASE_URL}/chart/${symbol}?interval=1d&range=2d`

            const response = await fetch(url, {
                headers: {
                    "User-Agent": USER_AGENT
                },
                next: { revalidate: 300 } // Cache for 5 minutes
            })

            if (!response.ok) {
                console.error(`Failed to fetch data for ${symbol}: ${response.status}`)
                continue
            }

            const data = await response.json()
            const result = data.chart?.result?.[0]

            if (!result || !result.meta) continue

            const meta = result.meta
            const price = meta.regularMarketPrice
            const prevClose = meta.chartPreviousClose
            const change = price - prevClose
            const changePercent = (change / prevClose) * 100

            results.push({
                symbol: meta.symbol,
                name: meta.symbol, // Meta doesn't always have full name in chart endpoint w/o params
                price,
                change,
                changePercent,
                timestamp: Date.now()
            })

        } catch (error) {
            console.error(`Error fetching ${symbol}:`, error)
        }
    }

    return results
}

export async function fetchNews(query: string = "stock market"): Promise<YahooNewsItem[]> {
    try {
        const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&newsCount=10`

        const response = await fetch(url, {
            headers: {
                "User-Agent": USER_AGENT
            },
            next: { revalidate: 900 } // Cache for 15 minutes
        })

        if (!response.ok) return []

        const data = await response.json()
        return data.news || []

    } catch (error) {
        console.error("Error fetching news:", error)
        return []
    }
}
