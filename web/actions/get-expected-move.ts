'use server'; // Ensure directive is present

import { execFile } from 'child_process';
import util from 'util';
import path from 'path';
import prisma from '@/lib/prisma'; // Default import

const execFilePromise = util.promisify(execFile);

function isPositiveNumber(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

function hasUsableExpectedMove(exp: {
    straddle?: unknown;
    em_365?: unknown;
    em_252?: unknown;
    adj_em?: unknown;
    manual_em?: unknown;
}): boolean {
    return [exp.manual_em, exp.adj_em, exp.em_252, exp.em_365, exp.straddle].some(isPositiveNumber);
}

export async function getExpectedMoveData(tickers: string[], refresh: boolean = false) {
    try {
        const normalizedTickers = [...new Set(tickers.map((ticker) => ticker.trim().toUpperCase()).filter(Boolean))];
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const requestedTickers = [...normalizedTickers];

        const readFromDb = async (symbols: string[]) => {
            const dbDataRaw = await prisma.expectedMove.findMany({
                where: {
                    ticker: { in: symbols },
                    calculationDate: today
                },
                orderBy: [
                    { ticker: 'asc' },
                    { expiryDate: 'asc' }
                ]
            });
            const dbData = dbDataRaw.filter((row) => isPositiveNumber(row.price) && hasUsableExpectedMove({
                straddle: row.straddle,
                em_365: row.em365,
                em_252: row.em252,
                adj_em: row.adjEm,
                manual_em: row.manualEm,
            }));

            const grouped = new Map<string, any[]>();
            symbols.forEach((ticker) => grouped.set(ticker, []));
            for (const row of dbData) {
                const list = grouped.get(row.ticker);
                if (list) list.push(row);
            }

            const result = symbols.map((ticker) => {
                const rows = grouped.get(ticker) || [];
                const price = rows.length > 0 ? rows[0].price : null;

                const expirations = rows.map((r) => {
                    let basisObj = undefined;
                    try {
                        if (r.basis) basisObj = JSON.parse(r.basis);
                    } catch {
                        // ignore malformed basis payloads
                    }

                    const dte = Math.ceil((r.expiryDate.getTime() - Date.now()) / (1000 * 3600 * 24));

                    return {
                        id: r.id,
                        date: r.expiryDate.toISOString().split('T')[0],
                        dte,
                        straddle: r.straddle,
                        em_365: r.em365,
                        em_252: r.em252,
                        adj_em: r.adjEm,
                        manual_em: r.manualEm,
                        basis: basisObj,
                        note: r.note
                    };
                }).filter((exp) => hasUsableExpectedMove(exp));

                return {
                    ticker,
                    price,
                    expirations
                };
            }).filter((item) => isPositiveNumber(item.price) && item.expirations.length > 0);

            const missingTickers = symbols.filter((ticker) => !result.some((item) => item.ticker === ticker));
            return { result, missingTickers };
        };

        // 1. Check DB First (Read-Through Cache)
        let tickersToFetch = requestedTickers;
        if (!refresh && requestedTickers.length > 0) {
            const { result, missingTickers } = await readFromDb(requestedTickers);
            if (missingTickers.length === 0) {
                console.log('Using Cached DB Data for Expected Move');
                return { success: true, data: result };
            }

            console.log(`Cache Miss for: ${missingTickers.join(', ')}. Fetching live.`);
            tickersToFetch = missingTickers;
        }

        // --- Live Fetch Logic ---

        // Determine Project Root (Parent of 'web')
        const projectRoot = path.resolve(process.cwd(), '..');
        const scriptPath = path.join(projectRoot, 'scripts', 'streaming', 'api_expected_move.py');

        const args = [scriptPath];
        if (tickersToFetch.length > 0) {
            args.push('--tickers', ...tickersToFetch);
        }
        if (refresh) {
            args.push('--refresh');
        }

        console.log(`Executing Expected Move Script: python ${args.join(' ')} (CWD: ${projectRoot})`);

        const { stdout, stderr } = await execFilePromise('python', args, { cwd: projectRoot });

        if (stderr) {
            if (stderr.toLowerCase().includes('error')) {
                console.error('Script Error:', stderr);
            }
        }

        let rawData;
        try {
            rawData = JSON.parse(stdout);
        } catch (parseError) {
            console.error('JSON Parse Error:', parseError, stdout);
            return { success: false, error: 'Failed to parse JSON output from script.' };
        }

        if (!Array.isArray(rawData)) {
            if (rawData && rawData.error) return { success: false, error: rawData.error };
            return { success: false, error: 'Script returned unexpected format.' };
        }

        try {
            const processedData = rawData
                .map((item: any) => ({
                    ...item,
                    expirations: Array.isArray(item?.expirations)
                        ? item.expirations.filter((exp: any) => hasUsableExpectedMove(exp))
                        : [],
                }))
                .filter((item: any) => isPositiveNumber(item?.price) && item.expirations.length > 0);

            for (const item of processedData) {
                for (const exp of item.expirations) {
                    await prisma.expectedMove.upsert({
                        where: {
                            ticker_calculationDate_expiryDate: {
                                ticker: item.ticker,
                                calculationDate: today,
                                expiryDate: new Date(exp.date),
                            }
                        },
                        update: {
                            price: item.price,
                            straddle: exp.straddle,
                            em365: exp.em_365,
                            em252: exp.em_252,
                            adjEm: exp.adj_em,
                            basis: exp.basis ? JSON.stringify(exp.basis) : null,
                            note: exp.note
                        } as any,
                        create: {
                            ticker: item.ticker,
                            calculationDate: today,
                            expiryDate: new Date(exp.date),
                            price: item.price,
                            straddle: exp.straddle,
                            em365: exp.em_365,
                            em252: exp.em_252,
                            adjEm: exp.adj_em,
                            manualEm: null,
                            basis: exp.basis ? JSON.stringify(exp.basis) : null,
                            note: exp.note
                        } as any
                    });
                }
            }

            const { result } = await readFromDb(requestedTickers);
            return { success: true, data: result.length > 0 ? result : processedData };
        } catch (dbError: any) {
            console.error('DB Sync Error:', dbError);
            // If DB fails, return raw data at least
            const processedData = Array.isArray(rawData)
                ? rawData
                    .map((item: any) => ({
                        ...item,
                        expirations: Array.isArray(item?.expirations)
                            ? item.expirations.filter((exp: any) => hasUsableExpectedMove(exp))
                            : [],
                    }))
                    .filter((item: any) => isPositiveNumber(item?.price) && item.expirations.length > 0)
                : [];
            return { success: true, data: processedData };
        }

    } catch (error: any) {
        console.error('Server Action Error:', error);
        return { success: false, error: error.message };
    }
}
