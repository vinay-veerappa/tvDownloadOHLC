import { ProfilerSession } from '@/lib/api/profiler';
import fs from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';

// --- Types ---

interface LiveStatus {
    ticker: string;
    timestamp: number;
    asia: { status: string; broken: boolean };
    london: { status: string; broken: boolean };
    ny1: { status: string; broken: boolean };
    ny2?: { status: string; broken: boolean };
}

interface SessionContextData {
    status: string;
    trend: 'Bullish' | 'Bearish' | 'Neutral';
    streak: number;
    broken: boolean;
    probabilities?: Record<string, number>;
}

export interface MissionMatrixContext {
    asia: SessionContextData;
    london: SessionContextData;
    ny1: SessionContextData;
    ny2: SessionContextData;
    overnight_bias: 'Bullish' | 'Bearish' | 'Neutral' | 'Mixed';
    status_streaks?: {
        [key: string]: {
            current: number;
            group: number;
        }
    };
}

export interface OutcomeStats {
    scenario: string; // "Long True", "Long False", "Short True", "Short False"
    probability: number; // 0-100
    count: number;
    bias: 'Bullish' | 'Bearish';
    avg_hod_pct: number;
    avg_lod_pct: number;
    hod_time_mode: string;
    lod_time_mode: string;
    hod_pct_display: string;
    lod_pct_display: string;
    // Level Probabilities
    pdh_hit_rate: number;
    pdl_hit_rate: number;
    pdm_hit_rate: number;
    p12h_hit_rate: number;
    p12l_hit_rate: number;
    p12m_hit_rate: number;
    asia_mid_hit_rate: number;
    london_mid_hit_rate: number;
    ny1_mid_hit_rate: number;
    midnight_open_hit_rate: number;
    open_0730_hit_rate: number;
    key_level_hits: string[]; // For top list summary
}

export interface MissionMatrixResponse {
    context: MissionMatrixContext;
    matrix: OutcomeStats[];
    dominant_scenario: string; // The specific outcome name with highest prob
    total_samples: number;
    target_session: string; // "Asia", "London", "NY1", or "NY2"
    target_phase_name: string; // "Asia Outcomes", etc.
}

// --- Constants ---

const OUTCOMES = ['Long True', 'Long False', 'Short True', 'Short False'];
const SESSION_ORDER = ['Asia', 'London', 'NY1', 'NY2'];

// --- Helper Functions ---

async function readJsonFile<T>(filePath: string): Promise<T> {
    try {
        const raw = await fs.readFile(filePath, 'utf-8');
        return JSON.parse(raw);
    } catch (error) {
        throw error;
    }
}

// Convert "HH:MM" (EST) or ISO to minutes from 18:00 Prev Day
function getMinutesFrom1800(timeStr: string): number {
    if (!timeStr) return 0;
    // Handle ISO string
    const timePart = timeStr.includes('T') ? timeStr.split('T')[1].substring(0, 5) : timeStr;
    const [h, m] = timePart.split(':').map(Number);
    if (isNaN(h) || isNaN(m)) return 0;
    const minutesFromMidnight = h * 60 + m;
    // 18:00 is 1080 minutes from midnight.
    return (minutesFromMidnight - 1080 + 1440) % 1440;
}

function formatMinutesToHHMM(minutesFrom1800: number): string {
    const m = (minutesFrom1800 + 1080) % 1440;
    const h = Math.floor(m / 60);
    const mm = m % 60;
    return `${h.toString().padStart(2, '0')}:${mm.toString().padStart(2, '0')}`;
}

function calculateModeTime(times: (string | null | undefined)[]): string {
    const validTimes = times.filter((t): t is string => !!t);
    if (validTimes.length === 0) return 'N/A';

    const BUCKET_SIZE = 15;
    const buckets: Record<string, number> = {};
    const firstSeen: Record<string, number> = {};

    validTimes.forEach((t, idx) => {
        const m = getMinutesFrom1800(t);
        const bStart = Math.floor(m / BUCKET_SIZE) * BUCKET_SIZE;
        const bKey = bStart.toString();

        buckets[bKey] = (buckets[bKey] || 0) + 1;
        if (!(bKey in firstSeen)) firstSeen[bKey] = idx;
    });

    const entries = Object.entries(buckets);
    // Sort by count DESC, then by first occurrence ASC (to match Dashboard stable sort)
    entries.sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return (firstSeen[a[0]] ?? 0) - (firstSeen[b[0]] ?? 0);
    });

    const maxB = parseInt(entries[0][0]);
    const startT = maxB;
    const endT = startT + BUCKET_SIZE;
    return `${formatMinutesToHHMM(startT)}-${formatMinutesToHHMM(endT)}`;
}

function calculateModePct(pcts: number[], bucketSize: number = 0.1): string {
    if (pcts.length === 0) return 'N/A';

    // 1. Calculate Median (average of middle two for even)
    const sorted = [...pcts].sort((a, b) => a - b);
    const n = sorted.length;
    const mid = Math.floor(n / 2);
    const medianVal = n % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    const medianBucket = Math.floor(medianVal / bucketSize) * bucketSize;

    // 2. Calculate Mode (Stable Sort)
    const buckets: Record<string, number> = {};
    const firstSeen: Record<string, number> = {};

    pcts.forEach((v, idx) => {
        const b = (Math.floor(v / bucketSize) * bucketSize).toFixed(1);
        buckets[b] = (buckets[b] || 0) + 1;
        if (!(b in firstSeen)) firstSeen[b] = idx;
    });

    const entries = Object.entries(buckets);
    entries.sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return (firstSeen[a[0]] ?? 0) - (firstSeen[b[0]] ?? 0);
    });

    const modeBucket = parseFloat(entries[0][0]);

    // 3. Range Format (Highest to Lowest)
    const uMin = Math.min(modeBucket, medianBucket);
    const uMax = Math.max(modeBucket, medianBucket);

    return `${uMax.toFixed(1)}% to ${uMin.toFixed(1)}%`;
}

function calculateStreak(sessions: ProfilerSession[], targetSession: string, currentStatus: string): number {
    if (currentStatus === 'Pending' || currentStatus === 'Neutral') return 0;

    const filtered = sessions
        .filter(s => s.session === targetSession && s.status !== 'Pending' && s.status !== 'Neutral')
        .sort((a, b) => b.date.localeCompare(a.date));

    // Determine current streak type
    const isTrue = currentStatus.includes('True');
    const isFalse = currentStatus.includes('False');

    let streak = 0;
    for (const s of filtered) {
        // PERMITTED MATCH: Exact status match
        if (s.status === currentStatus) {
            streak++;
        } else {
            break;
        }
    }
    return streak;
}

function calculateGroupStreak(sessions: ProfilerSession[], targetSession: string, currentStatus: string): number {
    if (currentStatus === 'Pending' || currentStatus === 'Neutral') return 0;

    const filtered = sessions
        .filter(s => s.session === targetSession && s.status !== 'Pending' && s.status !== 'Neutral')
        .sort((a, b) => b.date.localeCompare(a.date));

    const targetType = currentStatus.includes('True') ? 'TRUE' : 'FALSE';

    let streak = 0;
    for (const s of filtered) {
        const sType = s.status.includes('True') ? 'TRUE' : 'FALSE';
        if (sType === targetType) {
            streak++;
        } else {
            break;
        }
    }
    return streak;
}

const getTrend = (status: string): 'Bullish' | 'Bearish' | 'Neutral' => {
    if (status === 'Long True' || status === 'Long (Pending)') return 'Bullish';
    if (status === 'Short True' || status === 'Short (Pending)') return 'Bearish';
    if (status === 'Long False') return 'Bearish'; // Breaks High then Low
    if (status === 'Short False') return 'Bullish'; // Breaks Low then High
    return 'Neutral';
};

// Map status strings to PineScript numeric codes for consistency
// 1=LT, 2=LF, 3=ST, 4=SF
function getStatusCode(status: string): number {
    if (status === 'Long True') return 1;
    if (status === 'Long False') return 2;
    if (status === 'Short True') return 3;
    if (status === 'Short False') return 4;

    // Map Pending variants to UNIQUE codes for explicit subset logic
    if (status === 'Long (Pending)') return 11;
    if (status === 'Short (Pending)') return 13;

    return 0; // Neutral/Pending
}

// --- Main Calculator ---

export async function calculateMissionMatrix(ticker: string, providedLevelData?: Record<string, any>, providedLiveStatus?: LiveStatus): Promise<MissionMatrixResponse> {
    const findDataFile = (name: string) => {
        const root = process.cwd();
        const testPaths = [
            path.join(root, 'data', name),
            path.join(root, '..', 'data', name),
        ];

        // Also check relative to __dirname as a fallback
        try {
            testPaths.push(path.join(__dirname, '..', '..', '..', '..', 'data', name));
        } catch (e) { }

        for (const p of testPaths) {
            if (existsSync(p)) return p;
        }
        return testPaths[0]; // Fallback to default
    };

    // 1. Load Primary Data
    const dataPath = findDataFile(`${ticker}_profiler.json`);
    const allSessions = await readJsonFile<ProfilerSession[]>(dataPath);

    if (!Array.isArray(allSessions) || allSessions.length === 0) {
        throw new Error(`Profiler data not found or invalid for ${ticker} at ${dataPath}`);
    }

    // 2. Load Level Data
    let levelData = providedLevelData;
    if (!levelData) {
        try {
            const levelsPath = findDataFile(`${ticker}_level_touches.json`);
            levelData = await readJsonFile<any>(levelsPath);
        } catch (e) {
            levelData = {};
        }
    }

    // 2.5 Load Daily HOD/LOD (Unadjusted)
    let dailyHodLod: Record<string, any> = {};
    try {
        const dailyPath = findDataFile(`${ticker}_daily_hod_lod.json`);
        dailyHodLod = await readJsonFile<Record<string, any>>(dailyPath);
    } catch (e) {
        console.warn(`[MissionMatrix] Failed to load daily HOD/LOD for ${ticker}`);
    }

    // 3. Load Current Context (Live)
    const liveStatusPath = findDataFile(`${ticker}_live_status.json`);
    let liveStatusMap: Record<string, any> = { Asia: 'Pending', London: 'Pending', NY1: 'Pending', NY2: 'Pending' };

    try {
        const liveData = providedLiveStatus || await readJsonFile<LiveStatus>(liveStatusPath);
        if (!providedLiveStatus) console.log(`[MissionMatrix] Read live status for ${ticker} from ${liveStatusPath}:`, liveData);

        if (liveData) {
            if (liveData.asia) liveStatusMap.Asia = liveData.asia.status;
            if (liveData.london) liveStatusMap.London = liveData.london.status;
            if (liveData.ny1) liveStatusMap.NY1 = liveData.ny1.status;
            if (liveData.ny2) liveStatusMap.NY2 = liveData.ny2.status;
            // Store broken bits
            liveStatusMap.asia_broken = liveData.asia?.broken || false;
            liveStatusMap.london_broken = liveData.london?.broken || false;
            liveStatusMap.ny1_broken = liveData.ny1?.broken || false;
            liveStatusMap.ny2_broken = liveData.ny2?.broken || false;

            // Store broken_final bits (manual injection support)
            (liveStatusMap as any).asia_broken_final = (liveData.asia as any)?.broken_final;
            (liveStatusMap as any).london_broken_final = (liveData.london as any)?.broken_final;
            (liveStatusMap as any).ny1_broken_final = (liveData.ny1 as any)?.broken_final;
            (liveStatusMap as any).ny2_broken_final = (liveData.ny2 as any)?.broken_final;
        }
    } catch (e) {
        console.warn(`[MissionMatrix] Failed to read live status for ${ticker} at ${liveStatusPath}:`, e);
        // Fallback to latest in file if live is missing
    }

    const latestDate = Array.from(new Set(allSessions.map(s => s.date))).sort().reverse()[0] || '';
    const todaySessions = allSessions.filter(s => s.date === latestDate);
    const asiaSession = todaySessions.find(s => s.session === 'Asia');
    const londonSession = todaySessions.find(s => s.session === 'London');
    const ny1Session = todaySessions.find(s => s.session === 'NY1');
    const ny2Session = todaySessions.find(s => s.session === 'NY2');

    const currentAsiaStatus = liveStatusMap.Asia || (asiaSession?.status || 'Pending');
    const currentLondonStatus = liveStatusMap.London || (londonSession?.status || 'Pending');
    const currentNY1Status = liveStatusMap.NY1 || (ny1Session?.status || 'Pending');
    const currentNY2Status = liveStatusMap.NY2 || (ny2Session?.status || 'Pending');

    // Filter streak calculation: Only calculate streak if the status is NOT Pending
    const getStreak = (hist: any[], session: string, status: string) => {
        if (status === 'Pending' || status === 'Neutral') return 0;
        return calculateStreak(hist, session, status);
    };

    const asiaTrend = getTrend(currentAsiaStatus);
    const londonTrend = getTrend(currentLondonStatus);
    const ny1Trend = getTrend(currentNY1Status);
    const ny2Trend = getTrend(currentNY2Status);

    // --- 4. Determine Phase & Session Targeting (EST) ---
    const now = new Date();
    const estTimeStr = now.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false });
    const [h, m] = estTimeStr.split(':').map(Number);
    const estTotalMin = h * 60 + m;

    // Transitions at Status Window ENDS (EST)
    // 18:00 - 02:30: Asia Outcomes (Predicting Asia)
    // 02:30 - 07:30: London Outcomes (Predicting London)
    // 07:30 - 11:30: NY1 Outcomes (Predicting NY1)
    // 11:30 - 18:00: NY2 Outcomes (Predicting NY2)

    let phase_idx = 0;
    let phase_name = "Asia Outcomes";
    let targetSessionName: 'Asia' | 'London' | 'NY1' | 'NY2' = "Asia";

    if (estTotalMin >= 150 && estTotalMin < 450) {
        phase_idx = 1; phase_name = "London Outcomes"; targetSessionName = "London";
    } else if (estTotalMin >= 450 && estTotalMin < 690) {
        phase_idx = 2; phase_name = "NY1 Outcomes"; targetSessionName = "NY1";
    } else if (estTotalMin >= 690 && estTotalMin < 1080) {
        phase_idx = 3; phase_name = "NY2 Outcomes"; targetSessionName = "NY2";
    } else {
        phase_idx = 0; phase_name = "Asia Outcomes"; targetSessionName = "Asia";
    }

    let overnightBias: MissionMatrixContext['overnight_bias'] = 'Neutral';
    if (asiaTrend === londonTrend && asiaTrend !== 'Neutral') overnightBias = asiaTrend;
    else if (asiaTrend !== 'Neutral' && londonTrend !== 'Neutral') overnightBias = 'Mixed';
    else if (asiaTrend === 'Neutral' && londonTrend !== 'Neutral') overnightBias = londonTrend;
    else if (londonTrend === 'Neutral' && asiaTrend !== 'Neutral') overnightBias = asiaTrend;
    else overnightBias = asiaTrend;

    // Identify which session is currently "Active" (Target)
    const sessionFinished = [
        estTotalMin >= 150 && estTotalMin < 1080, // Asia done after 02:30
        estTotalMin >= 450 && estTotalMin < 1080, // London done after 07:30
        estTotalMin >= 690 && estTotalMin < 1080, // NY1 done after 11:30
        estTotalMin >= 1080 || estTotalMin < 150   // NY2 done after 18:00
    ];

    const isTargetActive = !sessionFinished[phase_idx];

    // 4.2 Helper for Base Probabilities (Historical average for the card)
    const calcBaseProbs = (sessionName: string) => {
        const hist = allSessions.filter(s => s.session === sessionName && s.status !== 'Pending' && s.status !== 'Neutral');
        const total = hist.length;
        const probs: Record<string, number> = {};
        OUTCOMES.forEach(o => {
            const count = hist.filter(s => s.status === o).length;
            probs[o] = total > 0 ? (count / total) * 100 : 0;
        });
        return probs;
    };

    const context: MissionMatrixContext = {
        asia: {
            status: currentAsiaStatus,
            trend: asiaTrend,
            streak: getStreak(allSessions.filter(s => s.date !== latestDate), 'Asia', currentAsiaStatus) + (sessionFinished[0] && currentAsiaStatus !== 'Pending' ? 1 : 0),
            broken: liveStatusMap.asia_broken || false,
            probabilities: calcBaseProbs('Asia')
        },
        london: {
            status: currentLondonStatus,
            trend: londonTrend,
            streak: getStreak(allSessions.filter(s => s.date !== latestDate), 'London', currentLondonStatus) + (sessionFinished[1] && currentLondonStatus !== 'Pending' ? 1 : 0),
            broken: liveStatusMap.london_broken || false,
            probabilities: calcBaseProbs('London')
        },
        ny1: {
            status: currentNY1Status,
            trend: ny1Trend,
            streak: getStreak(allSessions.filter(s => s.date !== latestDate), 'NY1', currentNY1Status) + (sessionFinished[2] && currentNY1Status !== 'Pending' ? 1 : 0),
            broken: liveStatusMap.ny1_broken || false,
            probabilities: calcBaseProbs('NY1')
        },
        ny2: {
            status: currentNY2Status,
            trend: ny2Trend,
            streak: getStreak(allSessions.filter(s => s.date !== latestDate), 'NY2', currentNY2Status) + (sessionFinished[3] && currentNY2Status !== 'Pending' ? 1 : 0),
            broken: liveStatusMap.ny2_broken || false,
            probabilities: calcBaseProbs('NY2')
        },
        overnight_bias: overnightBias,
        status_streaks: {
            Asia: {
                current: calculateStreak(allSessions.filter(s => s.date !== latestDate), 'Asia', currentAsiaStatus) + (sessionFinished[0] && currentAsiaStatus !== 'Pending' ? 1 : 0),
                group: calculateGroupStreak(allSessions.filter(s => s.date !== latestDate), 'Asia', currentAsiaStatus) + (sessionFinished[0] && currentAsiaStatus !== 'Pending' ? 1 : 0)
            },
            London: {
                current: calculateStreak(allSessions.filter(s => s.date !== latestDate), 'London', currentLondonStatus) + (sessionFinished[1] && currentLondonStatus !== 'Pending' ? 1 : 0),
                group: calculateGroupStreak(allSessions.filter(s => s.date !== latestDate), 'London', currentLondonStatus) + (sessionFinished[1] && currentLondonStatus !== 'Pending' ? 1 : 0)
            },
            NY1: {
                current: calculateStreak(allSessions.filter(s => s.date !== latestDate), 'NY1', currentNY1Status) + (sessionFinished[2] && currentNY1Status !== 'Pending' ? 1 : 0),
                group: calculateGroupStreak(allSessions.filter(s => s.date !== latestDate), 'NY1', currentNY1Status) + (sessionFinished[2] && currentNY1Status !== 'Pending' ? 1 : 0)
            },
            NY2: {
                current: calculateStreak(allSessions.filter(s => s.date !== latestDate), 'NY2', currentNY2Status) + (sessionFinished[3] && currentNY2Status !== 'Pending' ? 1 : 0),
                group: calculateGroupStreak(allSessions.filter(s => s.date !== latestDate), 'NY2', currentNY2Status) + (sessionFinished[3] && currentNY2Status !== 'Pending' ? 1 : 0)
            }
        }
    };

    // 4.1 Consistent Outcome Matching Logic (PRECISE)
    const isConsistent = (
        hist_s: number,
        hist_b: boolean,
        live_s: number,
        live_b: boolean,
        isPrior: boolean
    ): boolean => {
        // Pending/Neutral sessions (0) don't filter anything unless they are "Developing"
        if (live_s === 0) return true;

        if (isPrior) {
            // PRIOR SESSIONS: Strict Status, Adaptive Broken
            if (hist_s !== live_s) return false;

            if (live_b) {
                return hist_b === true; // If live is broken, history must be broken
            }
            return true; // If live is not broken, history can be either (Adaptive)
        } else {
            // CURRENT SESSION: Developing Aware, Loose Broken
            // 11 = Long Pending -> Matches Hist Long True (1) OR Long False (2)
            if (live_s === 11) return (hist_s === 1 || hist_s === 2);
            // 13 = Short Pending -> Matches Hist Short True (3) OR Short False (4)
            if (live_s === 13) return (hist_s === 3 || hist_s === 4);

            // If it's already confirmed (LF/ST/SF/LT), match exactly
            if (hist_s !== live_s) return false;

            return true; // Always ignore broken for current session
        }
    };

    const currentStatuses = [
        getStatusCode(currentAsiaStatus),
        getStatusCode(currentLondonStatus),
        getStatusCode(currentNY1Status),
        getStatusCode(currentNY2Status)
    ];

    const currentBrokens = [
        liveStatusMap.asia_broken || false,
        liveStatusMap.london_broken || false,
        liveStatusMap.ny1_broken || false,
        liveStatusMap.ny2_broken || false
    ];

    const currentStatusStrings = [
        currentAsiaStatus,
        currentLondonStatus,
        currentNY1Status,
        currentNY2Status
    ];

    // Identify which session is CURRENT (the first one that is "Pending" or "Developing")
    // Use the existing phase_idx as our active index for the matrix display
    const activeSessionIdx = phase_idx;

    // 5. Filter Historical Days
    const matchedDates: string[] = [];

    // Group sessions by date for intersection logic
    const dayPivots: Record<string, Record<string, ProfilerSession>> = {};
    allSessions.forEach(s => {
        if (!dayPivots[s.date]) dayPivots[s.date] = {};
        dayPivots[s.date][s.session] = s;
    });

    Object.entries(dayPivots).forEach(([date, sessions]) => {
        if (date === latestDate) return;

        let ok = true;
        // Check consistency up to the target/active session
        for (let i = 0; i <= activeSessionIdx; i++) {
            const sessName = SESSION_ORDER[i];
            const hist = sessions[sessName];
            if (!hist) { ok = false; break; }

            const isPrior = i < activeSessionIdx;
            if (!isConsistent(getStatusCode(hist.status), hist.broken, currentStatuses[i], currentBrokens[i], isPrior)) {
                ok = false;
                break;
            }
        }

        if (ok) matchedDates.push(date);
    });

    // 6. Generate Outcome Matrix
    const totalSamples = matchedDates.length;
    const matrix: OutcomeStats[] = OUTCOMES.map(scenario => {
        // Filter matched days for this specific target outcome
        const scenarioDays = matchedDates.filter(date => {
            const target = dayPivots[date]?.[targetSessionName];
            return target?.status === scenario;
        });

        const count = scenarioDays.length;
        const probability = totalSamples > 0 ? (count / totalSamples) * 100 : 0;

        // Helper to convert HH:MM or ISO to relative minutes from 18:00 (Trading Day)
        const getRelMins = (timeStr: string | null) => {
            if (!timeStr) return -1;
            const timePart = timeStr.includes('T') ? timeStr.split('T')[1].substring(0, 5) : timeStr;
            const [h, m] = timePart.split(':').map(Number);
            if (isNaN(h) || isNaN(m)) return -1;
            const total = h * 60 + m;
            return (total - 1080 + 1440) % 1440;
        };

        // Calculate hit rates: Counts touches occurring AT OR AFTER matched target session start
        const checkHit = (date: string, key: string) => {
            const dayLevels = (levelData as any)[date];
            const targetSess = dayPivots[date]?.[targetSessionName];
            if (!dayLevels || !dayLevels[key] || !targetSess) return false;

            const sessStartRel = getRelMins(targetSess.start_time);
            const touchTimesRel = (dayLevels[key].touch_times || []).map((t: string) => getRelMins(t));

            return touchTimesRel.some((t: number) => t >= sessStartRel);
        };

        const calcRate = (key: string) => count > 0 ? (scenarioDays.filter(d => checkHit(d, key)).length / count) * 100 : 0;

        // Collect stats
        const sampleSessions = scenarioDays.map(d => dayPivots[d][targetSessionName]);
        const dailySamples = scenarioDays.map(d => dailyHodLod[d]).filter(d => !!d);

        // Price Percentages: Unadjusted Daily
        const highPcts = dailySamples.map(s => ((s.daily_high - s.daily_open) / s.daily_open) * 100);
        const lowPcts = dailySamples.map(s => ((s.daily_low - s.daily_open) / s.daily_open) * 100);

        return {
            scenario,
            probability,
            count,
            bias: (scenario.includes('Long') ? 'Bullish' : 'Bearish') as 'Bullish' | 'Bearish',
            avg_hod_pct: highPcts.length ? highPcts.reduce((a, b) => a + b, 0) / count : 0,
            avg_lod_pct: lowPcts.length ? lowPcts.reduce((a, b) => a + b, 0) / count : 0,
            // Times: Unadjusted Daily (matching Dashboard)
            hod_time_mode: calculateModeTime(dailySamples.map(s => s.hod_time)),
            lod_time_mode: calculateModeTime(dailySamples.map(s => s.lod_time)),
            // Bucketing matches indicator (0.2 step)
            hod_pct_display: calculateModePct(highPcts, 0.1),
            lod_pct_display: calculateModePct(lowPcts, 0.1),
            pdh_hit_rate: Math.round(calcRate('pdh')),
            pdl_hit_rate: Math.round(calcRate('pdl')),
            pdm_hit_rate: Math.round(calcRate('pdm')),
            p12h_hit_rate: Math.round(calcRate('p12h')),
            p12l_hit_rate: Math.round(calcRate('p12l')),
            p12m_hit_rate: Math.round(calcRate('p12m')),
            asia_mid_hit_rate: Math.round(calcRate('asia_mid')),
            london_mid_hit_rate: Math.round(calcRate('london_mid')),
            ny1_mid_hit_rate: Math.round(calcRate('ny1_mid')),
            midnight_open_hit_rate: Math.round(calcRate('midnight_open')),
            open_0730_hit_rate: Math.round(calcRate('open_0730')),
            key_level_hits: []
        };
    }).filter(m => m.count > 0);


    const dominant = matrix.reduce((prev, curr) => (curr.probability > prev.probability ? curr : prev), matrix[0]!);

    return {
        context,
        matrix,
        dominant_scenario: dominant.scenario,
        total_samples: totalSamples,
        target_session: targetSessionName,
        target_phase_name: phase_name
    };
}
