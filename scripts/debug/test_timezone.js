const time = 1733266800; // 2024-12-03 23:00:00 UTC (Expected 18:00 EST)
const date = new Date(time * 1000);

console.log('UTC String:', date.toUTCString());

const est = date.toLocaleTimeString('en-US', {
    timeZone: 'America/New_York',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
});

console.log('Formatted EST:', est);

const local = date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
});

console.log('Formatted Local (System):', local);
