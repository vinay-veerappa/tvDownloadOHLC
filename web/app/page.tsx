import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TopToolbar } from "@/components/top-toolbar"
import { getAvailableData } from "@/actions/data-actions"
import { ChartWrapper } from "@/components/chart-wrapper"

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export default async function Home(props: PageProps) {
  const searchParams = await props.searchParams
  const { tickers, timeframes } = await getAvailableData()

  const ticker = (searchParams?.ticker as string) || "ES1"
  const timeframe = (searchParams?.timeframe as string) || "1D"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
      </div>

      {/* Top Toolbar */}
      <TopToolbar tickers={tickers} timeframes={timeframes} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0%</div>
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-7 h-[650px]">
          <CardHeader>
            <CardTitle>Chart: {ticker} ({timeframe})</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ChartWrapper ticker={ticker} timeframe={timeframe} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
