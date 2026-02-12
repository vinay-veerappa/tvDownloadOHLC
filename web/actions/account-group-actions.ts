"use server"

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getAccountGroups() {
    try {
        const groups = await prisma.accountGroup.findMany({
            include: { accounts: true },
            orderBy: { name: 'asc' }
        })
        return { success: true, data: groups }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function createAccountGroup(name: string, description?: string) {
    try {
        const group = await prisma.accountGroup.create({
            data: { name, description }
        })
        revalidatePath('/journal')
        return { success: true, data: group }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function addAccountToGroup(accountId: string, groupId: string) {
    try {
        await prisma.account.update({
            where: { id: accountId },
            data: { groupId }
        })
        revalidatePath('/journal')
        return { success: true }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function removeAccountFromGroup(accountId: string) {
    try {
        await prisma.account.update({
            where: { id: accountId },
            data: { groupId: null }
        })
        revalidatePath('/journal')
        return { success: true }
    } catch (e) {
        return { success: false, error: String(e) }
    }
}

export async function getGroupRiskStats(groupId: string) {
    try {
        const group = await prisma.accountGroup.findUnique({
            where: { id: groupId },
            include: { accounts: { include: { trades: {
                where: { status: "OPEN" }
            } } } }
        })

        if (!group) return { success: false, error: "Group not found" }

        let totalBalance = 0
        let totalOpenRisk = 0
        let totalOpenPnl = 0

        group.accounts.forEach(acc => {
            totalBalance += acc.currentBalance
            acc.trades.forEach(t => {
                totalOpenPnl += (t.pnl || 0)
                totalOpenRisk += (t.risk || 0)
            })
        })

        return {
            success: true,
            data: {
                name: group.name,
                accountCount: group.accounts.length,
                totalBalance,
                totalOpenRisk,
                totalOpenPnl,
                riskExposure: totalBalance > 0 ? (totalOpenRisk / totalBalance) * 100 : 0
            }
        }

    } catch (e) {
        return { success: false, error: String(e) }
    }
}
