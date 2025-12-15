import { AIChat } from "@/components/journal/ai-chat"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowLeft } from "lucide-react"

export default function AIPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Link href="/journal">
                    <Button variant="ghost" size="icon">
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                </Link>
                <div>
                    <h2 className="text-2xl font-bold">AI Trading Assistant</h2>
                    <p className="text-sm text-muted-foreground">
                        Analyze your trades and get insights using AI
                    </p>
                </div>
            </div>

            <AIChat />
        </div>
    )
}
