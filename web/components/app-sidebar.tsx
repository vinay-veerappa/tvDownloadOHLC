"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
    BarChart3,
    BookOpen,
    History,
    Settings,
    ChevronLeft,
    ChevronRight,
    Bell,
    User,
    Activity,
    Database,
    Zap,
    Radio,
    HardDrive,
    Library
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export function AppSidebar() {
    const pathname = usePathname()
    const [collapsed, setCollapsed] = React.useState(true) // Default to collapsed
    const [mounted, setMounted] = React.useState(false)

    // Load and save sidebar state from localStorage
    React.useEffect(() => {
        setMounted(true)
        const saved = localStorage.getItem('app_sidebar_collapsed')
        if (saved !== null) {
            setCollapsed(saved === 'true')
        }
    }, [])

    React.useEffect(() => {
        if (mounted) {
            localStorage.setItem('app_sidebar_collapsed', collapsed.toString())
        }
    }, [collapsed, mounted])

    if (!mounted) {
        return <div className="w-16 h-full border-r bg-background" /> // Static placeholder to prevent shift
    }

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
        {
            label: "Profiler",
            icon: Activity,
            href: "/profiler",
            active: pathname === "/profiler",
        },
        {
            label: "Reference",
            icon: Library,
            href: "/profiler/reference",
            active: pathname === "/profiler/reference",
        },
        {
            label: "Data Manager",
            icon: HardDrive,
            href: "/data",
            active: pathname === "/data",
        },
        {
            label: "Expected Move",
            icon: Zap,
            href: "/tools/expected-move",
            active: pathname === "/tools/expected-move",
        },
        {
            label: "Live Chart",
            icon: Radio,
            href: "/tools/live-chart",
            active: pathname === "/tools/live-chart",
        },
    ]

    return (
        <div suppressHydrationWarning className={cn(
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
                    title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
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
                            "w-full relative group",
                            route.active && "bg-secondary",
                            collapsed ? "justify-center px-2" : "justify-start"
                        )}
                        asChild
                        title={collapsed ? route.label : ""}
                    >
                        <Link href={route.href}>
                            <route.icon className={cn("h-5 w-5", !collapsed && "mr-2")} />
                            {!collapsed && <span>{route.label}</span>}
                            {/* Simple CSS Tooltip for collapsed state */}
                            {collapsed && (
                                <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded border shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                                    {route.label}
                                </div>
                            )}
                        </Link>
                    </Button>
                ))}
            </div>
            <div className="p-2 border-t space-y-1">
                <Button
                    variant="ghost"
                    className={cn("w-full relative group", collapsed ? "justify-center px-2" : "justify-start")}
                    title={collapsed ? "Notifications" : ""}
                >
                    <Bell className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Notifications"}
                    {collapsed && (
                        <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded border shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                            Notifications
                        </div>
                    )}
                </Button>
                <Button
                    variant="ghost"
                    className={cn("w-full relative group", collapsed ? "justify-center px-2" : "justify-start")}
                    title={collapsed ? "Profile" : ""}
                >
                    <User className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Profile"}
                    {collapsed && (
                        <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded border shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                            Profile
                        </div>
                    )}
                </Button>
                <Button
                    variant="ghost"
                    className={cn("w-full relative group", collapsed ? "justify-center px-2" : "justify-start")}
                    title={collapsed ? "Settings" : ""}
                >
                    <Settings className={cn("h-5 w-5", !collapsed && "mr-2")} />
                    {!collapsed && "Settings"}
                    {collapsed && (
                        <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded border shadow-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                            Settings
                        </div>
                    )}
                </Button>
            </div>
        </div>
    )
}
