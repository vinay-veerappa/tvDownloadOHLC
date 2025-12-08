"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, BookOpen, History, Settings, ChevronLeft, ChevronRight, Bell, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export function AppSidebar() {
    const pathname = usePathname()
    const [collapsed, setCollapsed] = React.useState(true) // Default to collapsed

    // Load and save sidebar state from localStorage
    React.useEffect(() => {
        const saved = localStorage.getItem('app_sidebar_collapsed')
        if (saved !== null) {
            setCollapsed(saved === 'true')
        }
    }, [])

    React.useEffect(() => {
        localStorage.setItem('app_sidebar_collapsed', collapsed.toString())
    }, [collapsed])

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
        <div className={cn(
            "flex flex-col h-full border-r bg-background transition-all duration-300",
            collapsed ? "w-16" : "w-64"
        )}>
            <div className={cn("flex items-center p-4", collapsed ? "justify-center" : "justify-between")}>
                {!collapsed && <h1 className="text-xl font-bold tracking-tight truncate">TradeNote</h1>}
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setCollapsed(!collapsed)}
                >
                    {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                </Button>
            </div>
            <div className="flex-1 px-2 space-y-2">
                {routes.map((route) => (
                    <Button
                        key={route.href}
                        variant={route.active ? "secondary" : "ghost"}
                        className={cn(
                            "w-full",
                            route.active && "bg-secondary",
                            collapsed ? "justify-center px-2" : "justify-start"
                        )}
                        asChild
                    >
                        <Link href={route.href}>
                            <route.icon className={cn("h-5 w-5", !collapsed && "mr-2")} />
                            {!collapsed && <span>{route.label}</span>}
                        </Link>
                    </Button>
                ))}
            </div>
            <div className="p-2 border-t space-y-1">
                <Button
                    variant="ghost"
                    className={cn("w-full", collapsed ? "justify-center px-2" : "justify-start")}
                >
                    <Bell className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Notifications"}
                </Button>
                <Button
                    variant="ghost"
                    className={cn("w-full", collapsed ? "justify-center px-2" : "justify-start")}
                >
                    <User className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Profile"}
                </Button>
                <Button
                    variant="ghost"
                    className={cn("w-full", collapsed ? "justify-center px-2" : "justify-start")}
                >
                    <Settings className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Settings"}
                </Button>
            </div>
        </div>
    )
}
