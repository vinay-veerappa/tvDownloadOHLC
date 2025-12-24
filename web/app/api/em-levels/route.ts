/**
 * API Route: /api/em-levels
 * 
 * Serves Expected Move level data from the database (ExpectedMoveHistory & RthExpectedMove)
 * Supports all tickers available in DB.
 * 
 * Query Params:
 * - ticker: string (default: SPY)
 * - from: string (YYYY-MM-DD)
 * - to: string (YYYY-MM-DD)
 * - days: number (Last N days, overrides from/to if present)
 */

import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma'; // Default import

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    let ticker = searchParams.get('ticker')?.toUpperCase() || 'SPY';

    // Normalize ticker (e.g., /ES -> ES)
    if (ticker.startsWith('/')) ticker = ticker.substring(1);
    if (ticker === '$SPX') ticker = 'SPX';

    // Parse filters
    const daysParam = searchParams.get('days');
    const dateFromParam = searchParams.get('from');
    const dateToParam = searchParams.get('to');

    // Calculate Date Range
    let dateFilter: any = {};

    if (daysParam) {
        const days = parseInt(daysParam);
        if (!isNaN(days) && days > 0) {
            const startDate = new Date();
            startDate.setDate(startDate.getDate() - days);
            dateFilter = {
                gte: startDate
            };
        }
    } else {
        if (dateFromParam) {
            dateFilter.gte = new Date(dateFromParam);
        }
        if (dateToParam) {
            dateFilter.lte = new Date(dateToParam);
        }
    }

    try {
        // 1. Fetch Close-Anchored Data (History)
        const historyData = await prisma.expectedMoveHistory.findMany({
            where: {
                ticker,
                date: dateFilter
            },
            orderBy: { date: 'asc' }
        });

        // 2. Fetch Open-Anchored Data (RTH Open)
        const rthData = await prisma.rthExpectedMove.findMany({
            where: {
                ticker,
                date: dateFilter
            },
            orderBy: { date: 'asc' }
        });

        const results: any[] = [];

        // Helper to format date
        const toDateStr = (d: Date) => d.toISOString().split('T')[0];

        // Process History (Close-Anchored)
        // emStraddle in DB is usually stored as the 0.85x value (checking schema comments)
        for (const row of historyData) {
            const dateStr = toDateStr(row.date);

            // Straddle 0.85x Use direct value
            if (row.emStraddle) {
                results.push({
                    date: dateStr,
                    method: 'straddle_085_close',
                    anchor: row.closePrice, // Close-anchored
                    em_value: row.emStraddle,
                    anchor_type: 'close'
                });

                // Estimate 1.0x back from 0.85x
                results.push({
                    date: dateStr,
                    method: 'straddle_100_close',
                    anchor: row.closePrice,
                    em_value: row.emStraddle / 0.85,
                    anchor_type: 'close'
                });
            }

            if (row.em365) {
                results.push({
                    date: dateStr,
                    method: 'iv365_close',
                    anchor: row.closePrice,
                    em_value: row.em365,
                    anchor_type: 'close'
                });
            }

            if (row.em252) {
                results.push({
                    date: dateStr,
                    method: 'iv252_close',
                    anchor: row.closePrice,
                    em_value: row.em252,
                    anchor_type: 'close'
                });
            }
        }

        // Process RTH Data (Open-Anchored)
        for (const row of rthData) {
            if (!row.openPrice) continue; // Need an anchor
            const dateStr = toDateStr(row.date);

            // Straddle (Open)
            if (row.emStraddle) {
                results.push({
                    date: dateStr,
                    method: 'straddle_085_open',
                    anchor: row.openPrice,
                    em_value: row.emStraddle, // Already calculated as EM (likely with multiplier)
                    anchor_type: 'open'
                });

                // Estimate 1.0x back from 0.85x
                results.push({
                    date: dateStr,
                    method: 'straddle_100_open',
                    anchor: row.openPrice,
                    em_value: row.emStraddle / 0.85,
                    anchor_type: 'open'
                });
            }

            // RTH VIX (Replaces Synth VIX)
            if (row.emVix) {
                results.push({
                    date: dateStr,
                    method: 'rth_vix_open',
                    anchor: row.openPrice,
                    em_value: row.emVix, // Already calculated
                    anchor_type: 'open'
                });
            }
        }

        return NextResponse.json({
            ticker,
            count: results.length,
            data: results
        });

    } catch (error: any) {
        console.error('EM Levels API Error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
