import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TopToolbar } from "@/components/top-toolbar"
import { getAvailableData } from "@/actions/data-actions"
import { ChartWrapper } from "@/components/chart-wrapper"
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
        {/* Top Toolbar integrated into Card */}
        <div className="border-b">
          <TopToolbar tickers={tickers} timeframes={timeframes} tickerMap={tickerMap || {}}>
            <div className="flex items-center gap-4 px-4">
              <div className="h-4 w-[1px] bg-border" />
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Trades:</span>
                <span className="font-bold">0</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Win Rate:</span>
                <span className="font-bold">0%</span>
              </div>
            </div>
          </TopToolbar>
        </div>

        {/* Chart Wrapper fills remaining space */}
        <CardContent className="flex-1 p-0 relative min-h-0">
          <ChartWrapper
            ticker={ticker}
            timeframe={timeframe}
            style={(searchParams?.style as string) || "candles"}
            indicators={searchParams?.indicators ? (searchParams.indicators as string).split(",") : []}
          />
        </CardContent>

        <BottomBar />
      </Card>
    </div>
  )
}
