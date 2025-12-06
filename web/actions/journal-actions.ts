'use server'

import prisma from "@/lib/prisma"
import { revalidatePath } from "next/cache"

// --- Accounts ---

export async function getAccounts() {
    try {
        const accounts = await prisma.account.findMany({
            orderBy: { createdAt: 'desc' }
        })
        return { success: true, data: accounts }
    } catch (e) {
        return { success: false, error: "Failed to fetch accounts" }
    }
}

export async function createAccount(data: { name: string, initialBalance: number, currency?: string }) {
    try {
        const account = await prisma.account.create({
            data: {
                name: data.name,
                initialBalance: data.initialBalance,
                currentBalance: data.initialBalance,
                currency: data.currency || "USD",
                isDefault: false
            }
        })
        revalidatePath('/')
        return { success: true, data: account }
    } catch (e) {
        return { success: false, error: "Failed to create account" }
    }
}

export async function deleteAccount(id: string) {
    try {
        await prisma.account.delete({ where: { id } })
        revalidatePath('/')
        return { success: true }
    } catch (e) {
        return { success: false, error: "Failed to delete account" }
    }
}

export async function resetAccount(id: string) {
    try {
        const account = await prisma.account.findUnique({ where: { id } })
        if (!account) throw new Error("Account not found")

        // Delete all trades for this account
        await prisma.trade.deleteMany({ where: { accountId: id } })

        // Reset balance
        await prisma.account.update({
            where: { id },
            data: { currentBalance: account.initialBalance }
        })

        revalidatePath('/')
        return { success: true }
    } catch (e) {
        return { success: false, error: "Failed to reset account" }
    }
}

// --- Strategies ---

export async function getStrategies() {
    try {
        const strategies = await prisma.strategy.findMany({
            orderBy: { name: 'asc' }
        })
        return { success: true, data: strategies }
    } catch (e) {
        return { success: false, error: "Failed to fetch strategies" }
    }
}

export async function createStrategy(data: { name: string, description?: string, color?: string }) {
    try {
        const strategy = await prisma.strategy.create({
            data: {
                name: data.name,
                description: data.description,
                color: data.color || "#2962FF"
            }
        })
        revalidatePath('/')
        return { success: true, data: strategy }
    } catch (e) {
        return { success: false, error: "Failed to create strategy" }
    }
}
