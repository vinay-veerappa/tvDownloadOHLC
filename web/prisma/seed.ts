import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
    // Create Default Account
    const defaultAccount = await prisma.account.upsert({
        where: { id: 'default-sim-account' },
        update: {},
        create: {
            id: 'default-sim-account',
            name: 'Simulated Account ($100k)',
            initialBalance: 100000,
            currentBalance: 100000,
            currency: 'USD',
            isDefault: true
        },
    })

    // Create Default Strategy
    await prisma.strategy.upsert({
        where: { id: 'default-strategy' },
        update: {},
        create: {
            id: 'default-strategy',
            name: 'General Trading',
            description: 'Default strategy for untagged trades',
            color: '#9E9E9E'
        }
    })

    // Create Tag Groups for journal categorization
    const tagGroups = [
        { id: 'group-mistake', name: 'mistake', color: '#ef4444' },
        { id: 'group-setup', name: 'setup', color: '#3b82f6' },
        { id: 'group-psychology', name: 'psychology', color: '#8b5cf6' },
        { id: 'group-strategy', name: 'strategy', color: '#10b981' },
        { id: 'group-event', name: 'event', color: '#f59e0b' }
    ]

    for (const group of tagGroups) {
        await prisma.tagGroup.upsert({
            where: { id: group.id },
            update: {},
            create: group
        })
    }

    console.log({ defaultAccount, tagGroups: tagGroups.length })
}

main()
    .then(async () => {
        await prisma.$disconnect()
    })
    .catch(async (e) => {
        console.error(e)
        await prisma.$disconnect()
        process.exit(1)
    })
