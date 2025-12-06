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

    console.log({ defaultAccount })
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
