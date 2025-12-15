
import { YahooQuote } from "./yahoo-finance"

export interface LiveEconomicEvent {
    title: string
    country: string
    date: string // ISO string
    impact: string
    forecast: string
    previous: string
}

const FF_FEED_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
export const COUNTRIES = ['USD', 'EUR', 'GBP', 'CAD', 'JPY', 'AUD', 'CHF', 'NZD']

export async function fetchLiveCalendar(): Promise<LiveEconomicEvent[]> {
    try {
        const res = await fetch(FF_FEED_URL, {
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            next: { revalidate: 3600 } // Cache for 1 hour
        })

        if (!res.ok) {
            console.error(`Failed to fetch calendar: ${res.status}`)
            return []
        }

        const events = await res.json()

        // Filter and map
        return events.filter((e: any) => COUNTRIES.includes(e.country))
            .map((e: any) => ({
                title: e.title,
                country: e.country,
                date: e.date,
                impact: e.impact,
                forecast: e.forecast,
                previous: e.previous
            }))

    } catch (error) {
        console.error("Error fetching live calendar:", error)
        return []
    }
}

export function mapImpact(impact: string): "HIGH" | "MEDIUM" | "LOW" {
    switch (impact.toLowerCase()) {
        case 'high': return 'HIGH'
        case 'medium': return 'MEDIUM'
        default: return 'LOW'
    }
}

// Helper to sync events to DB
import prisma from "@/lib/prisma"

export async function syncLiveEventsToDb(events: LiveEconomicEvent[]) {
    // Fire and forget logic, but safer to run in a controlled way
    for (const e of events) {
        try {
            const dt = new Date(e.date)
            // Check existence by Name + Time
            const exists = await prisma.economicEvent.findFirst({
                where: {
                    name: e.title,
                    datetime: dt
                }
            })
            if (!exists) {
                await prisma.economicEvent.create({
                    data: {
                        datetime: dt,
                        name: e.title,
                        impact: mapImpact(e.impact),
                        forecast: parseFloat(e.forecast) || null,
                        previous: parseFloat(e.previous) || null
                    }
                })
            }
        } catch (err) {
            console.error("Failed to sync event:", e.title, err)
        }
    }
}
