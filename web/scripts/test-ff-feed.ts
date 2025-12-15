
async function main() {
    const url = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json';
    try {
        console.log(`Fetching ${url}...`);
        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Failed: ${res.status} ${res.statusText}`);
        }
        const data = await res.json();
        console.log(`Success! Found ${data.length} events.`);
        if (data.length > 0) {
            console.log('Sample event:', data[0]);
        }

        // Check for today's events
        const today = new Date().toISOString().split('T')[0];
        const todayEvents = data.filter((e: any) => e.date && e.date.startsWith(today));
        console.log(`Events for today (${today}): ${todayEvents.length}`);
        todayEvents.forEach((e: any) => console.log(`- ${e.title} (${e.country})`));

    } catch (e) {
        console.error("Error:", e);
    }
}

main();
