"use server";

import prisma from "@/lib/prisma";

export async function getTickerHistory(ticker: string) {
    try {
        const history = await prisma.expectedMove.findMany({
            where: { ticker },
            orderBy: { calculationDate: 'desc' },
            take: 30 // Last 30 entries
        });

        // Serialize dates
        const data = history.map(rec => ({
            ...rec,
            calculationDate: rec.calculationDate.toISOString(),
            expiryDate: rec.expiryDate.toISOString(),
            createdAt: rec.createdAt.toISOString(),
            updatedAt: rec.updatedAt.toISOString(),
        }));

        return { success: true, data };
    } catch (error: any) {
        console.error("Failed to fetch history:", error);
        return { success: false, error: error.message };
    }
}
