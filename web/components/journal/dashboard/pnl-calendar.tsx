"use client"

import Link from "next/link"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { startOfMonth, endOfMonth, eachDayOfInterval, format, isSameMonth, getDay, isSameDay } from "date-fns"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface PnLCalendarProps {
    data: { date: string, pnl: number, trades: number }[]
    loading?: boolean
}

export function PnLCalendar({ data, loading }: PnLCalendarProps) {
    const [currentDate, setCurrentDate] = useState(new Date())

    if (loading) return <div className="h-[500px] bg-muted/20 animate-pulse rounded-xl" />

    const monthStart = startOfMonth(currentDate)
    const monthEnd = endOfMonth(currentDate)
    const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd })

    // Generate padding days for the grid
    const startDay = getDay(monthStart)
    const paddingDays = Array(startDay).fill(null)

    const prevMonth = () => setCurrentDate(curr => new Date(curr.getFullYear(), curr.getMonth() - 1, 1))
    const nextMonth = () => setCurrentDate(curr => new Date(curr.getFullYear(), curr.getMonth() + 1, 1))

    const getDataForDay = (date: Date) => {
        const dateStr = format(date, 'yyyy-MM-dd')
        return data.find(d => d.date === dateStr)
    }

    const getCellColor = (pnl: number) => {
        if (pnl > 0) return "bg-green-500/20 hover:bg-green-500/30 border-green-500/50"
        if (pnl < 0) return "bg-red-500/20 hover:bg-red-500/30 border-red-500/50"
        return "bg-card hover:bg-muted"
    }

    return (
        <Card className="bg-card/50 backdrop-blur-sm border-border/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                <CardTitle className="text-xl font-bold">
                    {format(currentDate, 'MMMM yyyy')}
                </CardTitle>
                <div className="flex gap-2">
                    <Button variant="outline" size="icon" onClick={prevMonth}>
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="icon" onClick={nextMonth}>
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-7 gap-2 mb-2">
                    {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                        <div key={day} className="text-center text-sm font-medium text-muted-foreground py-2">
                            {day}
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-7 gap-2 auto-rows-[100px]">
                    {paddingDays.map((_, i) => (
                        <div key={`pad-${i}`} className="bg-transparent" />
                    ))}
                    {daysInMonth.map(date => {
                        const dayData = getDataForDay(date)
                        const pnl = dayData?.pnl || 0
                        const hasData = !!dayData

                        return (
                            <Link 
                                href={`/journal/day/${format(date, 'yyyy-MM-dd')}`}
                                key={date.toISOString()}
                                className="block h-full"
                            >
                                <div
                                    className={`
                                        h-full rounded-lg border p-2 flex flex-col justify-between transition-colors
                                        ${getCellColor(pnl)}
                                        ${!isSameMonth(date, currentDate) ? "opacity-30" : ""}
                                    `}
                                >
                                    <span className="text-sm font-medium text-muted-foreground">
                                        {format(date, 'd')}
                                    </span>
                                    {hasData && (
                                        <div className="text-right">
                                            <div className={`font-bold ${pnl > 0 ? "text-green-500" : pnl < 0 ? "text-red-500" : ""}`}>
                                                ${pnl.toFixed(0)}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {dayData.trades} trades
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </Link>
                        )
                    })}
                </div>
            </CardContent>
        </Card>
    )
}
