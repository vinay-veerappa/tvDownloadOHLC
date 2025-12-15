import Link from "next/link"
import { AddTradeDialog } from "@/components/journal/add-trade-dialog"
import { TradeList } from "@/components/journal/trade-list"
import { ImportExportDialog } from "@/components/journal/import-export-dialog"
import { Button } from "@/components/ui/button"
import { BarChart3, Bot } from "lucide-react"

export default function JournalPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Trading Journal</h2>
                <div className="flex items-center space-x-2">
                    <ImportExportDialog />
                    <Link href="/journal/ai">
                        <Button variant="outline">
                            <Bot className="h-4 w-4 mr-2" />
                            AI Assistant
                        </Button>
                    </Link>
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

