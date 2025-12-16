
import { ProfilerSession, DailyHodLodResponse, LevelTouchesResponse } from '@/lib/api/profiler';

export interface ExportDataParams {
    outcome: string; // If single string provided, specific outcome. If "ALL", generic context.
    ticker: string;
    targetSession: string;
    sessions: ProfilerSession[]; // The specific subset for "outcome" (used for single export)
    allSessions: ProfilerSession[]; // Global context (used for base calcs and bulk export)
    dailyHodLod?: DailyHodLodResponse | null;
    levelTouches?: LevelTouchesResponse | null;
}

const HEADER = "Session|Direction|Stats|LOD Time Mode|HOD Time Mode|LOD Distribution|HOD Distribution|P12 High|P12 Mid|P12 Low|Asia Mid|London Mid|Captured At";

// Helper to convert HH:MM to minutes
function timeToMinutes(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
}

// Helper to convert minutes back to HH:MM
function minutesToTime(mins: number): string {
    const h = Math.floor(mins / 60) % 24;
    const m = mins % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

// Round time to nearest bucket (15m default for export)
function roundToBucket(time: string, granularity: number = 15): string {
    const mins = timeToMinutes(time);
    const rounded = Math.floor(mins / granularity) * granularity;
    return minutesToTime(rounded);
}

// Calculate Time Mode Range (e.g., "18:00 - 18:15")
function calculateTimeModeRange(times: string[], bucketSize: number = 15): string {
    if (times.length === 0) return "-";

    const buckets: Record<string, number> = {};
    times.forEach(t => {
        const bucketStart = roundToBucket(t, bucketSize);
        buckets[bucketStart] = (buckets[bucketStart] || 0) + 1;
    });

    // Find mode
    const sorted = Object.entries(buckets).sort((a, b) => b[1] - a[1]);
    if (sorted.length === 0) return "-";

    const bestStart = sorted[0][0];
    // Calculate End Time
    const startMins = timeToMinutes(bestStart);
    const endMins = startMins + bucketSize;
    const bestEnd = minutesToTime(endMins);

    return `${bestStart} - ${bestEnd}`;
}

// Calculate Price Distribution Range (Mode to Median)
function calculatePriceDistRange(values: number[], bucketSize: number = 0.1): string {
    if (values.length === 0) return "-";

    // Clamping to match UI
    const clamped = values.map(v => Math.max(-5.0, Math.min(5.0, v)));

    // 1. Calculate Mode
    const buckets: Record<string, number> = {};
    clamped.forEach(v => {
        const b = (Math.floor(v / bucketSize) * bucketSize).toFixed(1);
        buckets[b] = (buckets[b] || 0) + 1;
    });
    const sortedRun = Object.entries(buckets).sort((a, b) => b[1] - a[1]);
    const modeVal = sortedRun.length > 0 ? parseFloat(sortedRun[0][0]) : 0;

    // 2. Calculate Median
    const sortedVals = [...clamped].sort((a, b) => a - b);
    const midIndex = Math.floor(sortedVals.length / 2);
    const medianRaw = sortedVals[midIndex];
    const medianVal = parseFloat((Math.floor(medianRaw / bucketSize) * bucketSize).toFixed(1));

    // Format Range
    const start = Math.min(modeVal, medianVal).toFixed(1);
    const end = Math.max(modeVal, medianVal).toFixed(1);

    return `${start} to ${end} %`;
}

// Extract Level Probability by iterating matched dates
function getLevelProb(
    levelTouches: LevelTouchesResponse | null | undefined,
    dates: Set<string>,
    levelKey: "p12h" | "p12m" | "p12l" | "asia_mid" | "london_mid"
): string {
    if (!levelTouches || dates.size === 0) return "-";

    let hits = 0;
    let total = 0;

    // levelTouches is Record<string, DayLevelTouches> (Date -> Levels)
    // We iterate the dates in our subset
    dates.forEach(date => {
        const dayData = levelTouches[date];
        if (dayData) {
            total++;
            // Check if specific level was touched
            if (dayData[levelKey] && dayData[levelKey].touched) {
                hits++;
            }
        }
    });

    if (total === 0) return "-";

    return `${((hits / total) * 100).toFixed(2)} %`;
}


/**
 * Generates a single line string for a specific outcome subset.
 */
export function generateSingleOutcomeString({
    outcome,
    targetSession,
    sessions,
    allSessions,
    dailyHodLod,
    levelTouches
}: ExportDataParams): string {

    const sessionStr = `Wargame ${targetSession}`;
    const directionStr = outcome;

    // 2. Stats: Count / Total * 100
    // We need the BASE for this outcome "Direction".
    // E.g. "Long True" base is "Long True + Long False".
    // We deduce Direction from Outcome string.
    const direction = outcome.includes('Long') ? 'Long' : outcome.includes('Short') ? 'Short' : 'Any';

    // Filter allSessions to get the base count (e.g. Total Long Attempts)
    // CRITICAL: Must filter by targetSession to avoid mixing Asia/London/NY1
    const baseSessions = allSessions.filter(s =>
        s.session === targetSession &&
        s.status.includes(direction)
    );
    const total = baseSessions.length > 0 ? baseSessions.length : (sessions.length || 1);
    const count = sessions.length;
    const pct = total > 0 ? ((count / total) * 100).toFixed(2) : "0.00";

    const statsStr = `${pct}% - ${count} Days`;

    // 3. Time Modes
    const hodTimes: string[] = [];
    const lodTimes: string[] = [];
    const outcomeDates = new Set(sessions.map(s => s.date));

    if (dailyHodLod) {
        outcomeDates.forEach(date => {
            const d = dailyHodLod[date];
            if (d) {
                if (d.hod_time) hodTimes.push(d.hod_time);
                if (d.lod_time) lodTimes.push(d.lod_time);
            }
        });
    } else {
        // Fallback or skip
    }

    const lodTimeMode = calculateTimeModeRange(lodTimes, 15);
    const hodTimeMode = calculateTimeModeRange(hodTimes, 15);

    // 4. Price Distributions
    const highPcts: number[] = [];
    const lowPcts: number[] = [];

    outcomeDates.forEach(date => {
        if (dailyHodLod && dailyHodLod[date]) {
            const d = dailyHodLod[date];
            if (d.daily_open && d.daily_high && d.daily_low) {
                highPcts.push(((d.daily_high - d.daily_open) / d.daily_open) * 100);
                lowPcts.push(((d.daily_low - d.daily_open) / d.daily_open) * 100);
            }
        }
    });

    const lodDist = calculatePriceDistRange(lowPcts);
    const hodDist = calculatePriceDistRange(highPcts);

    // 5. Levels
    // Level keys in DayLevelTouches: p12h, p12m, p12l, asia_mid, london_mid
    const p12High = getLevelProb(levelTouches, outcomeDates, "p12h");
    const p12Mid = getLevelProb(levelTouches, outcomeDates, "p12m");
    const p12Low = getLevelProb(levelTouches, outcomeDates, "p12l");
    const asiaMid = getLevelProb(levelTouches, outcomeDates, "asia_mid");
    const londonMid = getLevelProb(levelTouches, outcomeDates, "london_mid");

    // 6. Captured At
    const date = new Date();
    const m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const capturedAt = `${date.getFullYear()} ${m[date.getMonth()]} ${date.getDate()} - ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;

    return [
        sessionStr,
        directionStr,
        statsStr,
        lodTimeMode,
        hodTimeMode,
        lodDist,
        hodDist,
        p12High,
        p12Mid,
        p12Low,
        asiaMid,
        londonMid,
        capturedAt
    ].join("|");
}

export interface BulkExportParams extends Omit<ExportDataParams, 'outcome' | 'sessions'> {
    validOutcomes?: string[]; // Optional specific list of outcomes to export
}

/**
 * Generates export string for ALL Standard Outcomes (Long/Short True/False).
 * Respects validOutcomes if provided (to match UI tabs).
 */
export function generateBulkExportString({
    ticker,
    targetSession,
    allSessions,
    dailyHodLod,
    levelTouches,
    validOutcomes
}: BulkExportParams): string {

    const outcomesToProcess = validOutcomes && validOutcomes.length > 0
        ? validOutcomes
        : ['Long True', 'Long False', 'Short True', 'Short False'];

    const lines = [HEADER];

    outcomesToProcess.forEach(outcome => {
        // Filter sessions for this specific outcome AND target session
        const subset = allSessions.filter(s =>
            s.session === targetSession &&
            s.status === outcome
        );

        if (subset.length === 0) return;

        const line = generateSingleOutcomeString({
            outcome,
            ticker,
            targetSession,
            sessions: subset,
            allSessions,
            dailyHodLod,
            levelTouches
        });
        lines.push(line);
    });

    return lines.join("\n");
}
