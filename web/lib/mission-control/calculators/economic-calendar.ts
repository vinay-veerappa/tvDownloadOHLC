/**
 * Economic Calendar Calculator
 * 
 * Fetches high-impact economic news from Prisma database.
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export interface EconomicEvent {
    id: string;
    datetime: string;
    name: string;
    impact: 'HIGH' | 'MEDIUM' | 'LOW';
    actual: number | null;
    forecast: number | null;
    previous: number | null;
}

export async function calculateEconomicCalendar(): Promise<EconomicEvent[]> {
    const now = new Date();

    // Start from current time
    const startDate = new Date(now);

    // End at end of today (system local time)
    const endDate = new Date(now);
    endDate.setHours(23, 59, 59, 999);

    try {
        const events = await prisma.economicEvent.findMany({
            where: {
                datetime: {
                    gte: startDate,
                    lte: endDate
                }
            },
            orderBy: {
                datetime: 'asc'
            }
        });

        const EXCLUDE_KEYWORDS = [
            "German", "French", "Spanish", "Italian", "Eurozone",
            "UK ", "JPY", "AUD", "CAD", "CNY", "Swiss", "ECB",
            "EU ", "Australian", "British", "Canadian", "Japanese", "Chinese",
            "NAB", "RBA", "RBNZ", "BOE", "BOC", "BOJ", "New Zealand", "Mexico",
            "Brazil", "India", "Russia", "South Africa", "Turkish", "Lira"
        ];

        return events
            .filter(e => !EXCLUDE_KEYWORDS.some(kw => e.name.includes(kw)))
            .map(e => ({
                id: e.id,
                datetime: e.datetime.toISOString(),
                name: e.name,
                impact: e.impact as any,
                actual: e.actual,
                forecast: e.forecast,
                previous: e.previous
            }));
    } catch (error) {
        console.error('Error fetching economic events:', error);
        return [];
    }
}
