import Link from "next/link"
import { JournalDashboard } from "@/components/journal/journal-dashboard"
import { Button } from "@/components/ui/button"
import { Bot, Settings } from "lucide-react"

export default function JournalPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Trading Journal</h2>
                <div className="flex items-center space-x-2">
                    <Link href="/journal/ai">
                        <Button variant="outline">
                            <Bot className="h-4 w-4 mr-2" />
                            AI Assistant
                        </Button>
                    </Link>
                    <Link href="/journal/settings">
                        <Button variant="outline">
                            <Settings className="h-4 w-4 mr-2" />
                            Settings
                        </Button>
                    </Link>
                </div>
            </div>
            
            <JournalDashboard />
        </div>
    )
}
