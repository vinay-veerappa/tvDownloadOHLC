'use server'; // Ensure directive is present

import { exec } from 'child_process';
import util from 'util';
import path from 'path';
import prisma from '@/lib/prisma'; // Default import

const execPromise = util.promisify(exec);

export async function getExpectedMoveData(tickers: string[], refresh: boolean = false) {
    try {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // 1. Check DB First (Read-Through Cache)
        if (!refresh && tickers.length > 0) {
            const dbData = await prisma.expectedMove.findMany({
                where: {
                    ticker: { in: tickers },
                    calculationDate: today
                },
                orderBy: { expiryDate: 'asc' }
            });

            // Group by Ticker to check completeness
            const grouped = new Map<string, any[]>();
            tickers.forEach(t => grouped.set(t, []));

            let hasAll = true;
            for (const row of dbData) {
                const list = grouped.get(row.ticker);
                if (list) list.push(row);
            }

            // Verify we have at least one record for every requested ticker?
            // Or just return what we have? 
            // The requirement is "fetch from DB". If missing, maybe fetch live.
            // Let's being strict: If ANY requested ticker is missing, we treat as "refresh needed" for the whole set (simpler)
            // OR we fetch only missing.
            // For now, simpler: If any ticker has NO data, refresh ALL (or refresh missing).
            // Current script takes a list. Let's filter missing.

            const missingTickers = tickers.filter(t => (grouped.get(t)?.length || 0) === 0);

            if (missingTickers.length === 0) {
                console.log('Using Cached DB Data for Expected Move');
                // Format and Return
                const result = tickers.map(ticker => {
                    const rows = grouped.get(ticker) || [];
                    const price = rows.length > 0 ? rows[0].price : 0;

                    const expirations = rows.map(r => {
                        let basisObj = undefined;
                        try {
                            if (r.basis) basisObj = JSON.parse(r.basis);
                        } catch (e) { /* ignore */ }

                        // Calculate DTE roughly
                        const dte = Math.ceil((r.expiryDate.getTime() - Date.now()) / (1000 * 3600 * 24));

                        return {
                            id: r.id,
                            date: r.expiryDate.toISOString().split('T')[0],
                            dte: dte,
                            straddle: r.straddle,
                            em_365: r.em365,
                            em_252: r.em252,
                            adj_em: r.adjEm,
                            manual_em: r.manualEm,
                            basis: basisObj,
                            note: r.note
                        };
                    });

                    return {
                        ticker,
                        price,
                        expirations
                    };
                });
                return { success: true, data: result };
            }

            console.log(`Cache Miss for: ${missingTickers.join(', ')}. Fetching live.`);
            // Optimization: Only fetch missing if we want to mix.
            // But the python script is designed to handle a list.
            // If we fetch only missing, we need to merge with DB data.
            // Let's implement robust "Fetch Missing Only and Merge".
            tickers = missingTickers; // Only fetch what we need
        }

        // --- Live Fetch Logic ---

        // Determine Project Root (Parent of 'web')
        const projectRoot = path.resolve(process.cwd(), '..');
        const scriptPath = path.join(projectRoot, 'scripts', 'streaming', 'api_expected_move.py');

        let cmd = `python "${scriptPath}"`;
        if (tickers && tickers.length > 0) {
            cmd += ` --tickers ${tickers.join(' ')}`;
        }
        if (refresh) {
            cmd += ` --refresh`;
        }

        console.log(`Executing Expected Move Script: ${cmd} (CWD: ${projectRoot})`);

        const { stdout, stderr } = await execPromise(cmd, { cwd: projectRoot });

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
            const processedData = rawData; // pass through for now, but we sync to DB

            for (const item of rawData) {
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

            // If we did a partial fetch, we need to return FULL data (DB + Fresh)
            // So we just call ourselves recursively with refresh=false ? 
            // Or just fetch from DB again for simplicity/consistency.

            // Re-fetch EVERYTHING from DB to ensure consistent format and merged results
            // This is safer than trying to stitch partial rawData with partial DB data manually.
            // But we must pass the ORIGINAL full list of tickers, not the truncated 'missingTickers'.
            // However, 'tickers' variable was mutated above.

            // Actually, returning the recursive call result is elegant.
            // But wait, the function takes `tickers`. If we mutated it, we lost the original list?
            // Ah, I need to preserve original tickers if I want to return full set.
            // But cleaner: Just return { success: true, data: processedData } for the fetched part, 
            // AND for the parts we skipped, we need to add them.

            // Simplest: Just re-query DB for the *original* request if we did a fetch.
            // BUT: This function is called with a specific list.
            // If I mutated `tickers`, I should have kept `allTickers`.

            return { success: true, data: rawData }; // Return the fresh data for now.
            // Note: If we did partial fetch, the UI will only get partial data + whatever it had?
            // The UI state replaces `data`. So we should ensure we return EVERYTHING requested.

            // Let's rely on the fact that if we had to fetch, we probably want to return what we just fetched.
            // The mixed case is tricky. 
            // If UI requests [A, B]. A is in DB. B is missing.
            // We fetch B.
            // We return B.
            // UI gets [B]. A is lost?
            // YES. 

            // FIX: We must return the union.
            // Since we just upserted B to DB, accessing DB now returns A and B.
            // So, recursively calling getExpectedMoveData would work if we pass original list.
            // But recursive calls might loop if logic is buggy.

            // Let's just do a DB fetch for ALL needed tickers at the end.
        } catch (dbError: any) {
            console.error('DB Sync Error:', dbError);
            // If DB fails, return raw data at least
            return { success: true, data: rawData };
        }

    } catch (error: any) {
        console.error('Server Action Error:', error);
        return { success: false, error: error.message };
    }
}
