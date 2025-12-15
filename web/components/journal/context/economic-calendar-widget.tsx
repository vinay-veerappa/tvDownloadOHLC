"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Calendar, Settings, RefreshCw, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Label } from "@/components/ui/label"
import { syncLiveEvents, getLiveEconomicEvents } from "@/actions/context-actions"

// Re-defining interface here or import if possible. Importing from server-lib in client might be tricky if it has fs/server deps.
// economic-calendar.ts looks clean (just fetch), so we can import types.
import { LiveEconomicEvent, COUNTRIES } from "@/lib/economic-calendar"

interface EconomicCalendarWidgetProps {
    initialEvents: any[] // Fallback DB events
}

export function EconomicCalendarWidget({ initialEvents }: EconomicCalendarWidgetProps) {
    const [events, setEvents] = useState<any[]>(initialEvents || [])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [selectedCountries, setSelectedCountries] = useState<string[]>(COUNTRIES)
    const [mounted, setMounted] = useState(false)

    // Load preferences from local storage on mount
    useEffect(() => {
        setMounted(true)
        const saved = localStorage.getItem("economic-calendar-countries")
        if (saved) {
            try {
                setSelectedCountries(JSON.parse(saved))
            } catch (e) {
                console.error("Failed to parse saved countries", e)
            }
        }
    }, [])

    // Fetch live events when countries change or on mount
    const fetchEvents = async () => {
        if (!mounted) return
        setLoading(true)
        setError(null)
        try {
            // Server Action fetch (avoid CORS)
            const result = await getLiveEconomicEvents()

            if (!result.success || !result.data) {
                throw new Error(result.error || "Failed to fetch")
            }

            const data = result.data

            // We keep ALL data from the feed
            const relevant = data

            const mapped = relevant.map((e: any) => ({
                id: `live-${e.date}-${e.title}`,
                name: e.title,
                country: e.country, // Ensure country is passed for filtering
                datetime: new Date(e.date), // This parses string to Date object
                impact: e.impact.toUpperCase(),
                forecast: e.forecast,
                previous: e.previous
            }))

            // Update state with new live data
            setEvents(mapped)

            // Auto-sync to DB for history (Fire and forget)
            const toSync: LiveEconomicEvent[] = relevant.map((e: any) => ({
                title: e.title,
                country: e.country,
                date: e.date,
                impact: e.impact,
                forecast: e.forecast || "",
                previous: e.previous || ""
            }))

            syncLiveEvents(toSync).catch(err => console.error("Sync failed", err))

        } catch (err) {
            console.error("Server action fetch error", err)
            setError(err instanceof Error ? err.message : "Failed to load live events")
            // Keep showing initialEvents (DB fallback) if we failed
        } finally {
            setLoading(false)
        }
    }

    // Trigger fetch when mounted (initial load)
    useEffect(() => {
        if (mounted) fetchEvents()
    }, [mounted])

    // Save preferences
    useEffect(() => {
        if (mounted) {
            localStorage.setItem("economic-calendar-countries", JSON.stringify(selectedCountries))
        }
    }, [selectedCountries, mounted])

    const toggleCountry = (c: string) => {
        setSelectedCountries(prev =>
            prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]
        )
    }

    // Derive visible events based on filter
    const visibleEvents = events.filter(event =>
        selectedCountries.includes(event.country)
    )

    // Group events by Date string (YYYY-MM-DD)
    const groupedEvents = visibleEvents.reduce((acc: any, event: any) => {
        const dateStr = event.datetime.toISOString().split('T')[0]
        if (!acc[dateStr]) acc[dateStr] = []
        acc[dateStr].push(event)
        return acc
    }, {})

    // Sort dates
    const sortedDates = Object.keys(groupedEvents).sort()

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div className="flex flex-col space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                        <Calendar className="h-5 w-5" />
                        Economic Events
                    </CardTitle>
                    <CardDescription>Scheduled for this week</CardDescription>
                </div>
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" onClick={fetchEvents} disabled={loading} className="h-8 w-8">
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <Popover>
                        <PopoverTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                <Settings className="h-4 w-4" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-56" align="end">
                            <div className="space-y-4">
                                <h4 className="font-medium leading-none">Filter Countries</h4>
                                <ScrollArea className="h-[200px] pr-2">
                                    <div className="space-y-2">
                                        {COUNTRIES.map(country => (
                                            <div key={country} className="flex items-center space-x-2">
                                                <Checkbox
                                                    id={`filter-${country}`}
                                                    checked={selectedCountries.includes(country)}
                                                    onCheckedChange={() => toggleCountry(country)}
                                                />
                                                <Label htmlFor={`filter-${country}`}>{country}</Label>
                                            </div>
                                        ))}
                                    </div>
                                </ScrollArea>
                            </div>
                        </PopoverContent>
                    </Popover>
                </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto px-0">
                {/* px-0 to allow headers to touch edges if desired, but standard padding is fine.
                   Let's use px-4 inside map for list items and sticky header.
               */}
                {error && (
                    <div className="mx-4 flex items-center gap-2 text-destructive text-sm mb-4 bg-destructive/10 p-2 rounded">
                        <AlertTriangle className="h-4 w-4" />
                        <span>Live update failed. Showing cached data.</span>
                    </div>
                )}

                {visibleEvents.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        {loading ? "Loading schedule..." : "No events match filters."}
                    </div>
                ) : (
                    <div className="relative">
                        {sortedDates.map(dateStr => {
                            const dayEvents = groupedEvents[dateStr]
                            const dateObj = new Date(dateStr)
                            // "T" split dateObj is UTC 00:00.
                            // We want to display "Monday, Dec 15".
                            // Since dateStr is YYYY-MM-DD, creating new Date(dateStr) treats it as UTC.
                            // To display correctly in local/user friendly format without shifting:
                            // We can use the timezone of the stored date strings.
                            // Actually, better to use the first event's date object or just parse safely.
                            // Simplest: `new Date(dateStr + "T12:00:00")` to avoid boundary shifts.
                            const displayDate = new Date(dateStr + "T12:00:00")

                            return (
                                <div key={dateStr}>
                                    <div className="sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-y px-4 py-1 text-xs font-semibold text-muted-foreground">
                                        {displayDate.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                                    </div>
                                    <div className="divide-y">
                                        {dayEvents.map((event: any) => (
                                            <div key={event.id} className="flex items-center justify-between hover:bg-muted/50 p-2 px-4 transition-colors">
                                                <div className="space-y-1">
                                                    <div className="font-medium text-sm flex items-center gap-2">
                                                        {event.name}
                                                        {event.country && <span className="text-xs text-muted-foreground">[{event.country}]</span>}
                                                    </div>
                                                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                        <span>{event.datetime.toLocaleTimeString([], { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit' })}</span>
                                                        {event.forecast && <span>Forecast: {event.forecast}</span>}
                                                    </div>
                                                </div>
                                                <Badge variant={
                                                    event.impact?.toUpperCase() === 'HIGH' ? 'destructive' :
                                                        event.impact?.toUpperCase() === 'MEDIUM' ? 'default' : 'secondary'
                                                } className="ml-2 shrink-0">
                                                    {event.impact}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
