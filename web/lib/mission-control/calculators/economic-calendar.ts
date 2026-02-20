import { fetchLiveCalendar, LiveEconomicEvent } from '@/lib/economic-calendar';

export async function calculateEconomicCalendar() {
    try {
        const rawEvents = await fetchLiveCalendar();
        
        const events = rawEvents.map((e, i) => ({
            id: `ec-${e.date}-${i}`,
            datetime: e.date,
            name: e.title,
            impact: e.impact,
            actual: null,
            forecast: e.forecast || null,
            previous: e.previous || null
        }));

        return {
            events
        };
    } catch (error) {
        console.error("Failed to calculate economic calendar", error);
        return { events: [] };
    }
}
