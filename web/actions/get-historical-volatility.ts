
'use server';

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export type HistoricalVolatilityData = {
    date: string; // YYYY-MM-DD
    iv: number;
    hv: number | null;
    closePrice: number | null;
};

export async function getHistoricalVolatility(ticker: string, startDate: Date, endDate: Date): Promise<HistoricalVolatilityData[]> {
    try {
        // Normalize Futures Tickers
        let dbTicker = ticker;
        const upper = ticker.toUpperCase();
        if (upper.startsWith('ES') || upper === 'ES1!') dbTicker = '/ES';
        if (upper.startsWith('NQ') || upper === 'NQ1!') dbTicker = '/NQ';
        if (upper.startsWith('RTY') || upper === 'RTI') dbTicker = '/RTY'; // RTY/RTI overlap
        if (upper.startsWith('M2K')) dbTicker = '/RTY'; // Proxy M2K -> RTY
        if (upper.startsWith('MES')) dbTicker = '/ES'; // Proxy MES -> ES
        if (upper.startsWith('MNQ')) dbTicker = '/NQ'; // Proxy MNQ -> NQ
        if (upper.startsWith('YM') || upper === 'YM1!') dbTicker = '/YM';
        if (upper.startsWith('MYM')) dbTicker = '/YM';

        const rows = await prisma.historicalVolatility.findMany({
            where: {
                ticker: dbTicker,
                date: {
                    gte: startDate,
                    lte: endDate
                }
            },
            orderBy: {
                date: 'asc'
            }
        });

        // Serialize dates
        return rows.map(r => ({
            date: r.date.toISOString().split('T')[0],
            iv: r.iv,
            hv: r.hv,
            closePrice: r.closePrice
        }));
    } catch (error) {
        console.error('Failed to fetch historical volatility:', error);
        return [];
    } finally {
        await prisma.$disconnect();
    }
}
