/**
 * HOD/LOD Radar Calculator
 * 
 * Calculates statistical timing of High/Low of Day, 
 * filtered by overnight session behavior.
 */

import * as fs from 'fs';
import * as path from 'path';
import { getSessionConfig } from '@/config/sessions';

export interface HODLODTiming {
    time: string;
    count: number;
    probability: number;
}

export interface HODLODAnalysis {
    hod_distribution: HODLODTiming[];
    lod_distribution: HODLODTiming[];
    hod_mode: string;
    lod_mode: string;
    match_count: number;
    overnight_profile: string;
}

interface ProfilerSession {
    date: string;
    session: string;
    status: string;
    high_time: string;
    low_time: string;
    range_high: number;
    range_low: number;
}

/**
 * Calculate conditional HOD/LOD timing analysis
 */
export async function calculateHODLOD(
    ticker: string,
    overnightStatuses: { asia: string; london: string }
): Promise<HODLODAnalysis | null> {
    const dataPath = path.join(process.cwd(), '..', 'data', `${ticker}_profiler.json`);

    if (!fs.existsSync(dataPath)) {
        console.error(`Profiler data not found: ${dataPath}`);
        return null;
    }

    const rawData = fs.readFileSync(dataPath, 'utf-8');
    const profilerEntries: ProfilerSession[] = JSON.parse(rawData);

    // Group entries by date
    const byDate = new Map<string, ProfilerSession[]>();
    for (const entry of profilerEntries) {
        if (!byDate.has(entry.date)) byDate.set(entry.date, []);
        byDate.get(entry.date)!.push(entry);
    }

    // Terminology map: 'LONG_TRUE' -> 'Long True'
    const normalizeStatus = (s: string) => s.replace('_', ' ').toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.substring(1)).join(' ');

    const targetAsia = normalizeStatus(overnightStatuses.asia);
    const targetLondon = normalizeStatus(overnightStatuses.london);

    // Identify matching historical dates
    const matchingDates = new Set<string>();

    // Pass 1: Look for exact dual match (Asia AND London)
    for (const [date, sessions] of byDate.entries()) {
        const asia = sessions.find(s => s.session === 'Asia');
        const london = sessions.find(s => s.session === 'London');

        if (asia && london && asia.status === targetAsia && london.status === targetLondon) {
            matchingDates.add(date);
        }
    }

    // Pass 2: Fallback to London only if no dual match (London is usually more significant for NY prep)
    let profileDesc = `${targetAsia} + ${targetLondon}`;
    if (matchingDates.size < 5) {
        matchingDates.clear();
        for (const [date, sessions] of byDate.entries()) {
            const london = sessions.find(s => s.session === 'London');
            if (london && london.status === targetLondon) {
                matchingDates.add(date);
            }
        }
        profileDesc = `${targetLondon} (London Only)`;
    }

    // Pass 3: Fallback to all dates if still no match
    if (matchingDates.size === 0) {
        for (const date of byDate.keys()) matchingDates.add(date);
        profileDesc = "All Samples (No Match)";
    }

    const hodCounts: Record<string, number> = {};
    const lodCounts: Record<string, number> = {};

    for (const date of matchingDates) {
        const sessions = byDate.get(date)!;
        let dayHigh = -Infinity;
        let dayLow = Infinity;
        let dayHighTime = '';
        let dayLowTime = '';

        for (const s of sessions) {
            if (s.range_high > dayHigh) {
                dayHigh = s.range_high;
                dayHighTime = s.high_time;
            }
            if (s.range_low < dayLow) {
                dayLow = s.range_low;
                dayLowTime = s.low_time;
            }
        }

        if (dayHighTime) {
            const bucket = bucketTime(dayHighTime);
            hodCounts[bucket] = (hodCounts[bucket] || 0) + 1;
        }
        if (dayLowTime) {
            const bucket = bucketTime(dayLowTime);
            lodCounts[bucket] = (lodCounts[bucket] || 0) + 1;
        }
    }

    const matchCount = matchingDates.size;

    return {
        hod_distribution: formatDistribution(hodCounts, matchCount),
        lod_distribution: formatDistribution(lodCounts, matchCount),
        hod_mode: getMode(hodCounts),
        lod_mode: getMode(lodCounts),
        match_count: matchCount,
        overnight_profile: profileDesc
    };
}

function bucketTime(timeStr: string): string {
    if (!timeStr) return '';
    const [h, m] = timeStr.split(':').map(Number);
    const totalMinutes = h * 60 + m;
    const bucketMinutes = Math.floor(totalMinutes / 30) * 30;
    const bh = Math.floor(bucketMinutes / 60);
    const bm = bucketMinutes % 60;
    return `${bh.toString().padStart(2, '0')}:${bm.toString().padStart(2, '0')}`;
}

function formatDistribution(counts: Record<string, number>, total: number): HODLODTiming[] {
    return Object.entries(counts)
        .map(([time, count]) => ({
            time,
            count,
            probability: (count / total) * 100
        }))
        .sort((a, b) => a.time.localeCompare(b.time));
}

function getMode(counts: Record<string, number>): string {
    let mode = '';
    let max = 0;
    for (const [time, count] of Object.entries(counts)) {
        if (count > max) {
            max = count;
            mode = time;
        }
    }
    return mode;
}
