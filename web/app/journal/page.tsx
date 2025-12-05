import { AddTradeDialog } from "@/components/journal/add-trade-dialog"
import { TradeList } from "@/components/journal/trade-list"

export default function JournalPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Trading Journal</h2>
                <div className="flex items-center space-x-2">
                    <AddTradeDialog />
                </div>
            </div>
            <TradeList />
        </div>
    )
}
