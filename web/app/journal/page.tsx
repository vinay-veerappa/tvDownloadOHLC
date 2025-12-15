import Link from "next/link"
import { AddTradeDialog } from "@/components/journal/add-trade-dialog"
import { TradeList } from "@/components/journal/trade-list"
import { Button } from "@/components/ui/button"
import { BarChart3 } from "lucide-react"

export default function JournalPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Trading Journal</h2>
                <div className="flex items-center space-x-2">
                    <Link href="/journal/analytics">
                        <Button variant="outline">
                            <BarChart3 className="h-4 w-4 mr-2" />
                            Analytics
                        </Button>
                    </Link>
                    <AddTradeDialog />
                </div>
            </div>
            <TradeList />
        </div>
    )
}

