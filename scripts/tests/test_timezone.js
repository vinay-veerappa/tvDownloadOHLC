const displayTimezone = 'America/New_York';
const time = 1735056000; // 2024-12-24 16:00:00 UTC -> 11:00 EST

const format = (t) => {
    const date = new Date(t * 1000);
    return date.toLocaleString('en-US', {
        timeZone: displayTimezone,
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false
    });
}
console.log("Expected: 11:00 AM (approx)");
console.log("Actual:", format(time));
