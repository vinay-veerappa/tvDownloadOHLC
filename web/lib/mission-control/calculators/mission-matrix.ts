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

// --- Helper Functions ---

async function readJsonFile<T>(filePath: string): Promise<T> {
    try {
        const raw = await fs.readFile(filePath, 'utf-8');
        return JSON.parse(raw);
    } catch (error) {
        throw error;
    }
}

// Convert "HH:MM" (EST) to minutes from 18:00 Prev Day
function getMinutesFrom1800(timeStr: string): number {
    if (!timeStr) return 0;
    const [h, m] = timeStr.split(':').map(Number);
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
    const TOTAL_BUCKETS = 96; // 1440 / 15
    const buckets = new Array(TOTAL_BUCKETS).fill(0);

    validTimes.forEach(t => {
        const m = getMinutesFrom1800(t);
        const bIdx = Math.min(Math.floor(m / BUCKET_SIZE), TOTAL_BUCKETS - 1);
        buckets[bIdx]++;
    });

    let maxCount = 0;
    let maxB = 0;
    for (let i = 0; i < TOTAL_BUCKETS; i++) {
        if (buckets[i] > maxCount) {
            maxCount = buckets[i];
            maxB = i;
        }
    }

    const startT = maxB * BUCKET_SIZE;
    const endT = (startT + BUCKET_SIZE) % 1440;
    return `${formatMinutesToHHMM(startT)}-${formatMinutesToHHMM(endT)}`;
}

function calculateModePct(pcts: number[]): string {
    if (pcts.length === 0) return 'N/A';

    const STEP = 0.2;
    const NUM_BUCKETS = 120;
    const OFFSET = 6.0;

    const buckets = new Array(NUM_BUCKETS).fill(0);
    pcts.forEach(v => {
        const idx = Math.min(Math.max(Math.floor((v + OFFSET) / STEP), 0), NUM_BUCKETS - 1);
        buckets[idx]++;
    });

    let maxC = 0;
    let maxB = 0;
    for (let i = 0; i < NUM_BUCKETS; i++) {
        if (buckets[i] > maxC) {
            maxC = buckets[i];
            maxB = i;
        }
    }

    const modeS = (maxB * STEP) - OFFSET;
    const modeE = modeS + STEP;

    const sorted = [...pcts].sort((a, b) => a - b);
    const medIdx = Math.floor(sorted.length / 2);
    const medVal = sorted[medIdx] ?? 0;

    const medB = Math.min(Math.max(Math.floor((medVal + OFFSET) / STEP), 0), NUM_BUCKETS - 1);
    const medS = (medB * STEP) - OFFSET;
    const medE = medS + STEP;

    const uMin = Math.min(modeS, medS);
    const uMax = Math.max(modeE, medE);

    return `${uMin.toFixed(1)}% to ${uMax.toFixed(1)}%`;
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
    const isConsistent = (hist_s: number, hist_b: boolean, live_s: number, live_b: boolean): boolean => {
        // Precise matching: If today has a status, historical day MUST match exactly
        if (live_s === 0) return true; // Don't filter by Pending/Neutral sessions

        // Pending/Developing Logic (Subset Matching) using explicit codes 11/13
        // 11 = Long Pending -> Matches Hist Long True (1) OR Long False (2)
        if (live_s === 11 && (hist_s === 1 || hist_s === 2)) return true;

        // 13 = Short Pending -> Matches Hist Short True (3) OR Short False (4)
        if (live_s === 13 && (hist_s === 3 || hist_s === 4)) return true;

        // Status must match
        if (hist_s !== live_s) return false;

        // BROKEN LOGIC (Simplified per User Request)
        if (live_b) {
            // If Live IS broken, History MUST be broken (Strict)
            return hist_b === true;
        } else {
            // If Live is NOT broken (yet), History can be Broken or Not Broken (Loose)
            // This handles "Active Session" where it might break later.
            return true;
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

    // 5. Create Pivot Table for Historical Matching
    const dayPivots: Record<string, Record<string, ProfilerSession>> = {};
    allSessions.forEach(s => {
        if (!dayPivots[s.date]) dayPivots[s.date] = {};
        dayPivots[s.date][s.session] = s;
    });

    // 6. Filter History & Match Outcomes
    const matchingSessions: ProfilerSession[] = [];
    Object.entries(dayPivots).forEach(([date, sessions]) => {
        // EXCLUDE TODAY: Do not match today's developing day against the historical pool
        if (date === latestDate) return;

        let ok = true;
        // 1. Must match all PREVIOUSLY COMPLETED sessions exactly AND the current Target Status if available
        // User Requirement: "always apply all sessions status... when we confirm a false, we apply the filter immediately"
        for (let i = 0; i <= phase_idx; i++) {
            const sName = i === 0 ? 'Asia' : i === 1 ? 'London' : i === 2 ? 'NY1' : 'NY2';
            const hist = sessions[sName];

            if (!hist || !isConsistent(getStatusCode(hist.status), hist.broken, currentStatuses[i], currentBrokens[i])) {
                // DEBUG MISMATCHES: Only if Status Matches but Broken fails
                if (hist && getStatusCode(hist.status) === currentStatuses[i] && hist.broken !== currentBrokens[i]) {
                    if (targetSessionName === 'NY2') console.log(`[Reject] ${date} ${sName} Broken Mismatch: Hist(B:${hist.broken}) vs Live(B:${currentBrokens[i]})`);
                }
                ok = false; break;
            }
        }

        if (ok) {
            const target = sessions[targetSessionName];
            if (target && target.status !== 'Pending' && target.status !== 'Neutral') {
                matchingSessions.push(target);
            }
        }
    });

    // DEBUG: Count how many match if we IGNORE BROKEN (Deprecated)
    /*
    const looseCount = Object.entries(dayPivots).filter(([date, sessions]) => {
        if (date === latestDate) return false;
        for (let i = 0; i <= phase_idx; i++) {
            const sName = i === 0 ? 'Asia' : i === 1 ? 'London' : i === 2 ? 'NY1' : 'NY2';
            const hist = sessions[sName];
            // Pass hist.broken as the live_b constraint to force a match on broken
            if (!hist || !isConsistent(getStatusCode(hist.status), hist.broken, currentStatuses[i], hist.broken)) return false;
        }
        return true;
    }).length;

    console.log(`[MissionMatrix] Strict Matches: ${matchingSessions.length} | Loose (Ignore Broken) Matches: ${looseCount}`);
    */

    console.log(`[MissionMatrix] ${phase_name} | Target: ${targetSessionName} | Samples: ${matchingSessions.length} | Context Status: ${currentStatuses[0]}/${currentStatuses[1]} Context Broken: ${currentBrokens[0]}/${currentBrokens[1]}`);

    const totalSamples = matchingSessions.length;

    // 6. Generate Outcome Matrix
    const matrix: OutcomeStats[] = OUTCOMES.map(scenario => {
        const scenarioSessions = matchingSessions.filter(s => s.status === scenario);
        const count = scenarioSessions.length;
        const probability = totalSamples > 0 ? (count / totalSamples) * 100 : 0;

        const hods = scenarioSessions.map(s => s.high_pct);
        const lods = scenarioSessions.map(s => s.low_pct);

        const checkHit = (date: string, key: string) => {
            const dayLevels = (levelData as any)[date];
            return dayLevels?.[key]?.touched || false;
        };

        const calcRate = (hits: number) => count > 0 ? (hits / count) * 100 : 0;

        return {
            scenario,
            probability,
            count,
            bias: scenario.includes('Long') ? 'Bullish' : 'Bearish',
            avg_hod_pct: hods.length ? hods.reduce((a, b) => a + b, 0) / count : 0,
            avg_lod_pct: lods.length ? lods.reduce((a, b) => a + b, 0) / count : 0,
            hod_time_mode: calculateModeTime(scenarioSessions.map(s => s.high_time)),
            lod_time_mode: calculateModeTime(scenarioSessions.map(s => s.low_time)),
            hod_pct_display: calculateModePct(hods),
            lod_pct_display: calculateModePct(lods),
            pdh_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'pdh')).length),
            pdl_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'pdl')).length),
            pdm_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'pdm')).length),
            p12h_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'p12h')).length),
            p12l_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'p12l')).length),
            p12m_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'p12m')).length),
            asia_mid_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'asia_mid')).length),
            london_mid_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'london_mid')).length),
            ny1_mid_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'ny1_mid')).length),
            midnight_open_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'midnight_open')).length),
            open_0730_hit_rate: calcRate(scenarioSessions.filter(s => checkHit(s.date, 'open_0730')).length),
            key_level_hits: []
        };
    });

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
