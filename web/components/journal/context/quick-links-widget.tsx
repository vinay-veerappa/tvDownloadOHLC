"use client"

import Link from "next/link"
import {
    AreaChart,
    BookOpen,
    Radio,
    Zap,
    History,
    ArrowRight
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function QuickLinksWidget() {
    const links = [
        {
            title: "Profiler",
            description: "Market Profile & TPO Analysis",
            icon: AreaChart,
            href: "/profiler",
            color: "text-blue-500",
            bg: "bg-blue-500/10",
        },
        {
            title: "Live Chart",
            description: "Real-time Charting & Analysis",
            icon: Radio,
            href: "/tools/live-chart",
            color: "text-green-500",
            bg: "bg-green-500/10",
        },
        {
            title: "Expected Move",
            description: "Weekly Volatility Ranges",
            icon: Zap,
            href: "/tools/expected-move",
            color: "text-amber-500",
            bg: "bg-amber-500/10",
        },
        {
            title: "Journal",
            description: "Trade Logging & Review",
            icon: BookOpen,
            href: "/journal",
            color: "text-purple-500",
            bg: "bg-purple-500/10",
        },
        {
            title: "Backtest",
            description: "Strategy Performance Testing",
            icon: History,
            href: "/backtest",
            color: "text-pink-500",
            bg: "bg-pink-500/10",
        },
    ]

    return (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {links.map((link) => (
                <Link key={link.href} href={link.href} className="block group">
                    <Card className="h-full transition-all duration-200 hover:shadow-md hover:border-primary/50">
                        <CardContent className="p-4 flex flex-col items-center text-center space-y-2">
                            <div className={cn("p-3 rounded-full transition-colors", link.bg, link.color)}>
                                <link.icon className="w-6 h-6" />
                            </div>
                            <div className="space-y-1">
                                <h3 className="font-semibold text-sm group-hover:text-primary transition-colors">
                                    {link.title}
                                </h3>
                                {/* <p className="text-xs text-muted-foreground hidden lg:block">
                                    {link.description}
                                </p> */}
                            </div>
                        </CardContent>
                    </Card>
                </Link>
            ))}
        </div>
    )
}
