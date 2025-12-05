import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getAvailableData } from "@/actions/data-actions"
import { ChartPageClient } from "@/components/chart-page-client"
import { BottomBar } from "@/components/bottom-bar"

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export default async function Home(props: PageProps) {
  const searchParams = await props.searchParams
  const { tickers, timeframes, tickerMap } = await getAvailableData()

  const ticker = (searchParams?.ticker as string) || "ES1"
  const timeframe = (searchParams?.timeframe as string) || "1D"

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] space-y-2">
      {/* Main Chart Area */}
      <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <ChartPageClient
          tickers={tickers}
          timeframes={timeframes}
          tickerMap={tickerMap || {}}
          ticker={ticker}
          timeframe={timeframe}
          style={(searchParams?.style as string) || "candles"}
          indicators={searchParams?.indicators ? (searchParams.indicators as string).split(",") : []}
        />

        <BottomBar />
      </Card>
    </div>
  )
}
