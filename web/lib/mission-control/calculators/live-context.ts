
// --- Constants ---
// Times are in EST (America/New_York)
// Format: HHMM
const SESSIONS = {

    Asia: {
        ref_start: 1800, ref_end: 1930, // 18:00 - 19:30 range
        status_start: 1930, status_end: 230 // 19:30 - 02:30 check
    },
    London: {
        ref_start: 230, ref_end: 330,   // 02:30 - 03:30 range
        status_start: 330, status_end: 730 // 03:30 - 07:30 check
    },
    NY1: {
        ref_start: 730, ref_end: 830,   // 07:30 - 08:30 range
        status_start: 830, status_end: 1130 // 08:30 - 11:30 check
    }
};

// Helper: Convert Date to HHMM int (e.g. 1925)
function getHHMM(date: Date): number {
    // Need EST time. The input dates from parquet usually UTC or EST?
    // Assuming backend standardizes to EST. 
    // If dates are UTC strings, we need conversion.
    // For now, let's assume the timestamps are UNIX or ISO correctly handled.
    // The safest way is to use 'America/New_York' string conversion
    const estString = date.toLocaleString("en-US", { timeZone: "America/New_York", hour12: false, hour: '2-digit', minute: '2-digit' });
    const [h, m] = estString.split(':').map(Number);
    return h * 100 + m;
}

// 0=Neutral, 1=LongTrue, 2=LongFalse, 3=ShortTrue, 4=ShortFalse
function calcStatus(bars: any[], refH: number, refL: number): number {
    let mode = 0;
    for (const bar of bars) {
        // Pine Logic:
        // b_h = high > h
        // b_l = low < l
        const b_h = bar.high > refH;
        const b_l = bar.low < refL;

        if (mode === 0) {
            if (b_h && !b_l) mode = 1;
            else if (b_l && !b_h) mode = 3;
            else if (b_h && b_l) mode = 2; // Both break same bar? Rare.
        } else if (mode === 1 && b_l) {
            mode = 2;
        } else if (mode === 3 && b_h) {
            mode = 4;
        }
    }
    return mode;
}

const MODE_MAP = ['Neutral', 'Long True', 'Long False', 'Short True', 'Short False'];

export async function getLiveContext(ticker: string, dateStr: string): Promise<any> {
    // 1. Get Live Bars (1m)
    // We need 'today's' bars. 
    // Simplified: Load recent 1440 bars from parquet/json
    // Actually, `mission-control` usually has a unified `getRecentBars`.
    // I will mock/implement a simple reader here for now.

    // Using existing parquet reader if available?
    // Let's assume we can fetch the last 1 day of 1m data.
    // NOTE: This logic needs to run on the server.

    // For now, implementing logic assuming we pass in the bars.
    return {};
}

export function determineSessionStatus(bars: { time: number, high: number, low: number }[], sessionName: 'Asia' | 'London' | 'NY1'): string {
    // 1. Filter Bars by Time Windows
    const config = SESSIONS[sessionName];

    // Identify Trading Day? 
    // Assuming 'bars' passed are relevant for the current trading session (e.g. last 24h).

    // Separate Ref Bars vs Status Bars
    let refH = -Infinity;
    let refL = Infinity;

    // Check if we handle wrapping across midnight (Asia 18:00->02:30).
    // HHMM compare is tricky if crossing 2400.
    // Logic: compare Minutes from 18:00?

    const getM = (hhmm: number) => {
        let h = Math.floor(hhmm / 100);
        let m = hhmm % 100;
        // Adjust for 18:00 start day
        if (h < 18) h += 24;
        return h * 60 + m;
    };

    const startM = getM(config.ref_start);
    const endM = getM(config.ref_end); // Exclusive?
    const statStartM = getM(config.status_start);
    const statEndM = getM(config.status_end);

    const statusBars: any[] = [];

    let hasRefData = false;

    bars.forEach(bar => {
        const d = new Date(bar.time * 1000);
        const hhmm = getHHMM(d);
        const m = getM(hhmm); // Normalized minutes from 18:00 prev day

        // Ref Window
        if (m >= startM && m < endM) {
            if (bar.high > refH) refH = bar.high;
            if (bar.low < refL) refL = bar.low;
            hasRefData = true;
        }

        // Status Window
        if (m >= statStartM && m < statEndM) {
            statusBars.push(bar);
        }
    });

    if (!hasRefData || refH === -Infinity) return 'Pending';

    // Calculate Mode 
    const modeCode = calcStatus(statusBars, refH, refL);

    // If status window hasn't started, it's 'Neutral' or 'Pending'?
    // Pine script returns initialized mode (0 -> Neutral).
    // If we have ref data but no status bars (yet), it's Neutral/Open.

    return MODE_MAP[modeCode];
}
