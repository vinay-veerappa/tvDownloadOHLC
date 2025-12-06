
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
    const deleted = await prisma.trade.deleteMany({})
    console.log(`Deleted ${deleted.count} trades. Database is clean.`)
}

main()
    .catch(e => {
        console.error(e)
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })
