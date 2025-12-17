'use server'; // Ensure directive is present

import { exec } from 'child_process';
import util from 'util';
import path from 'path';
import prisma from '@/lib/prisma'; // Default import

const execPromise = util.promisify(exec);

export async function getExpectedMoveData(tickers: string[], refresh: boolean = false) {
    try {
        // Determine Project Root (Parent of 'web')
        // note: process.cwd() in Next.js dev is typically the 'web' folder.
        // We want to run python from the root so it finds secrets.json.
        const projectRoot = path.resolve(process.cwd(), '..');

        // Absolute path to script
        const scriptPath = path.join(projectRoot, 'scripts', 'streaming', 'api_expected_move.py');

        let cmd = `python "${scriptPath}" --json`;
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
            return { success: false, error: 'Failed to parse JSON output from script. Check console for details.' };
        }

        // Validate rawData is an array
        if (!Array.isArray(rawData)) {
            // Check if it's an error object
            if (rawData && rawData.error) {
                return { success: false, error: `Script Error: ${rawData.error}` };
            }
            console.error('script returned non-array:', rawData);
            return { success: false, error: 'Script returned unexpected format (not an array).' };
        }

        try {
            // --- Sync to DB ---
            const dbData = [];
            const today = new Date();
            today.setHours(0, 0, 0, 0);

            for (const item of rawData) {
                for (const exp of item.expirations) {
                    // Upsert
                    const rec = await prisma.expectedMove.upsert({
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
                        },
                        create: {
                            ticker: item.ticker,
                            calculationDate: today,
                            expiryDate: new Date(exp.date),
                            price: item.price,
                            straddle: exp.straddle,
                            em365: exp.em_365,
                            em252: exp.em_252,
                            adjEm: exp.adj_em,
                            manualEm: null
                        }
                    });
                    dbData.push(rec);
                }
            }

            // Group by ticker for the UI
            const groupedData = new Map();
            for (const rec of dbData) {
                if (!groupedData.has(rec.ticker)) {
                    groupedData.set(rec.ticker, {
                        ticker: rec.ticker,
                        price: rec.price,
                        expirations: []
                    });
                }
                groupedData.get(rec.ticker).expirations.push({
                    id: rec.id,
                    date: rec.expiryDate.toISOString().split('T')[0],
                    dte: Math.ceil((new Date(rec.expiryDate).getTime() - Date.now()) / (1000 * 3600 * 24)),
                    straddle: rec.straddle,
                    em_365: rec.em365,
                    em_252: rec.em252,
                    adj_em: rec.adjEm,
                    manual_em: rec.manualEm
                });
            }

            const uiData = Array.from(groupedData.values());
            return { success: true, data: uiData };

        } catch (dbError: any) {
            console.error('DB Sync Error:', dbError);
            return { success: false, error: `DB Sync Failed: ${dbError.message}` };
        }

    } catch (error: any) {
        console.error('Server Action Error:', error);
        return { success: false, error: error.message };
    }
}
