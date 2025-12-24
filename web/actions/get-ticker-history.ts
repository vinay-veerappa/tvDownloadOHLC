"use server";

import prisma from "@/lib/prisma";

export async function getTickerHistory(ticker: string) {
    try {
        // Switch to the Unified History table (cleaner, no duplicates)
        const history = await prisma.expectedMoveHistory.findMany({
            where: { ticker },
            orderBy: { date: 'desc' },
            take: 90 // Increased history depth
        });

        // Map History fields to View fields
        const data = history.map(rec => ({
            id: rec.id,
            ticker: rec.ticker,
            // Map date -> calculationDate AND expiryDate (since history summarizes the day's outlook)
            calculationDate: rec.date.toISOString(),
            expiryDate: rec.date.toISOString(),

            // Map metrics
            price: rec.closePrice,
            straddle: rec.straddlePrice || 0,
            adjEm: rec.emStraddle || 0, // Using emStraddle which is typically Straddle * 0.85
            manualEm: null,

            createdAt: rec.createdAt.toISOString(),
            updatedAt: rec.updatedAt.toISOString(),
        }));

        return { success: true, data };
    } catch (error: any) {
        console.error("Failed to fetch history:", error);
        return { success: false, error: error.message };
    }
}
