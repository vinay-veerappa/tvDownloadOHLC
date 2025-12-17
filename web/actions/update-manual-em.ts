'use server';

import prisma from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

export async function updateManualEm(id: number, manualEm: number | null) {
    try {
        const updated = await prisma.expectedMove.update({
            where: { id },
            data: { manualEm },
        });

        // revalidatePath('/tools/expected-move'); // Not strictly needed if using client state but good practice
        return { success: true, data: updated };
    } catch (error: any) {
        console.error("Failed to update manual EM:", error);
        return { success: false, error: error.message };
    }
}
