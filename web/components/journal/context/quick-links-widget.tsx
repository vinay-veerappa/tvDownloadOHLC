"use client"

import Link from "next/link"
import {
    AreaChart,
    BookOpen,
    Radio,
    Zap,
    Activity,
    Flame,
    Radar,
    Beaker
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function QuickLinksWidget() {
    const links = [
        {
            title: "Chart",
            description: "Real-time Charting & Analysis",
            icon: Activity,
            href: "/tools/live-chart",
            color: "text-green-500",
            bg: "bg-green-500/10",
        },
        {
            title: "Profiler",
            description: "Market Profile & TPO Analysis",
            icon: AreaChart,
            href: "/profiler",
            color: "text-blue-500",
            bg: "bg-blue-500/10",
        },
        {
            title: "Edgeful Dashboard",
            description: "Institutional Edge & Research",
            icon: Beaker,
            href: "/research",
            color: "text-indigo-500",
            bg: "bg-indigo-500/10",
        },
        {
            title: "Mission Control",
            description: "Real-time Bias & Alignment",
            icon: Radio,
            href: "/dashboard/mission-control/NQ1",
            color: "text-red-500",
            bg: "bg-red-500/10",
        },
        {
            title: "GEX Dashboard V3",
            description: "Live Options Flow & GEX",
            icon: Radar,
            href: "/options-live-v3",
            color: "text-rose-500",
            bg: "bg-rose-500/10",
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
            title: "Candle Science",
            description: "3-Candle Pattern Projections",
            icon: Flame,
            href: "/candle-science",
            color: "text-orange-500",
            bg: "bg-orange-500/10",
        },
        {
            title: "Journal",
            description: "Trade Logging & Review",
            icon: BookOpen,
            href: "/journal",
            color: "text-purple-500",
            bg: "bg-purple-500/10",
        },
    ]

    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
