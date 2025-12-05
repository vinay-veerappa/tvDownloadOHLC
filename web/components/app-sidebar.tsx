"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, BookOpen, History, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export function AppSidebar() {
    const pathname = usePathname()

    const routes = [
        {
            label: "Chart",
            icon: BarChart3,
            href: "/",
            active: pathname === "/",
        },
        {
            label: "Journal",
            icon: BookOpen,
            href: "/journal",
            active: pathname === "/journal",
        },
        {
            label: "Backtest",
            icon: History,
            href: "/backtest",
            active: pathname === "/backtest",
        },
    ]

    return (
        <div className="flex flex-col h-full w-64 border-r bg-background">
            <div className="p-6">
                <h1 className="text-2xl font-bold tracking-tight">TradeNote</h1>
            </div>
            <div className="flex-1 px-4 space-y-2">
                {routes.map((route) => (
                    <Button
                        key={route.href}
                        variant={route.active ? "secondary" : "ghost"}
                        className={cn("w-full justify-start", route.active && "bg-secondary")}
                        asChild
                    >
                        <Link href={route.href}>
                            <route.icon className="mr-2 h-5 w-5" />
                            {route.label}
                        </Link>
                    </Button>
                ))}
            </div>
            <div className="p-4 border-t">
                <Button variant="ghost" className="w-full justify-start">
                    <Settings className="mr-2 h-5 w-5" />
                    Settings
                </Button>
            </div>
        </div>
    )
}
