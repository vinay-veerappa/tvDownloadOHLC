/**
 * API Route: /api/em-levels
 * 
 * Serves Expected Move level data from the analysis CSVs
 * Supports SPY, ES, and SPX tickers
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

// Parse CSV helper
function parseCSV(content: string): any[] {
    const lines = content.trim().split('\n');
    if (lines.length < 2) return [];

    const headers = lines[0].split(',');
    const result: any[] = [];

    for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',');
        const row: any = {};
        for (let j = 0; j < headers.length; j++) {
            const val = values[j]?.trim();
            // Try to parse as number
            const numVal = parseFloat(val);
            row[headers[j].trim()] = isNaN(numVal) ? val : numVal;
        }
        result.push(row);
    }

    return result;
}

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('ticker')?.toUpperCase() || 'SPY';
    const method = searchParams.get('method'); // Optional filter
    const dateFrom = searchParams.get('from'); // Optional date filter
    const dateTo = searchParams.get('to');     // Optional date filter

    try {
        // Determine which CSV to read
        let csvPath = '';
        const basePath = path.join(process.cwd(), '..', 'docs', 'expected_moves', 'analysis_data');

        switch (ticker) {
            case 'ES':
            case '/ES':
                csvPath = path.join(basePath, 'em_daily_levels_ES.csv');
                break;
            case 'SPX':
            case '$SPX':
                csvPath = path.join(basePath, 'em_daily_levels_SPX.csv');
                break;
            case 'SPY':
            default:
                csvPath = path.join(basePath, 'em_daily_levels.csv');
                break;
        }

        // Check if file exists
        try {
            await fs.access(csvPath);
        } catch {
            return NextResponse.json({ error: `CSV not found for ticker ${ticker}` }, { status: 404 });
        }

        // Read and parse CSV
        const content = await fs.readFile(csvPath, 'utf-8');
        let data = parseCSV(content);

        // Apply filters
        if (method) {
            data = data.filter(row => row.method === method);
        }

        if (dateFrom) {
            data = data.filter(row => row.date >= dateFrom);
        }

        if (dateTo) {
            data = data.filter(row => row.date <= dateTo);
        }

        // Transform to expected format
        const result = data.map(row => ({
            date: row.date,
            method: row.method,
            anchor: row.anchor,
            em_value: row.em_value,
            multiple: row.multiple,
            level_upper: row.level_upper,
            level_lower: row.level_lower,
            prev_close: row.prev_close,
            open: row.open,
            high: row.high,
            low: row.low,
            close: row.close
        }));

        return NextResponse.json({
            ticker,
            count: result.length,
            data: result
        });

    } catch (error: any) {
        console.error('EM Levels API Error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
