'use server';

import prisma from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

export async function updateExpectedMoveEntry(
    ticker: string,
    date: string, // YYYY-MM-DD
    data: { price?: number; manualEm?: number; expiryDate?: string }
) {
    try {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // We need an expiry date. If updating existing, we assume it exists or passed.
        // For new manual rows, expiryDate is required.
        let expiry: Date;
        if (data.expiryDate) {
            expiry = new Date(data.expiryDate);
        } else {
            // Fallback or error if assumed existing?
            // Actually, the UI should pass the expiry date key.
            throw new Error("Expiry date required");
        }

        const rec = await prisma.expectedMove.upsert({
            where: {
                ticker_calculationDate_expiryDate: {
                    ticker,
                    calculationDate: today,
                    expiryDate: expiry
                }
            },
            update: {
                ...(data.price !== undefined && { price: data.price }),
                ...(data.manualEm !== undefined && { manualEm: data.manualEm })
            },
            create: {
                ticker,
                calculationDate: today,
                expiryDate: expiry,
                price: data.price || 0,
                manualEm: data.manualEm,
                straddle: 0,
                em365: 0,
                em252: 0,
                adjEm: 0
            }
        });

        revalidatePath('/tools/expected-move');
        return { success: true, data: rec };
    } catch (error: any) {
        console.error('Update Manual Entry Failed:', error);
        return { success: false, error: error.message };
    }
}
