
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
    const today = new Date()
    const startOfDay = new Date(today.setHours(0, 0, 0, 0))
    const endOfDay = new Date(today.setHours(23, 59, 59, 999))

    console.log(`Checking events for: ${startOfDay.toISOString()} to ${endOfDay.toISOString()}`)

    const events = await prisma.economicEvent.findMany({
        where: {
            datetime: {
                gte: startOfDay,
                lte: endOfDay
            }
        },
        orderBy: { datetime: 'asc' }
    })

    console.log(`Found ${events.length} events.`)
    events.forEach(e => {
        console.log(`- [${e.impact}] ${e.datetime.toISOString().split('T')[1].substring(0, 5)} ${e.name}`)
    })
}

main()
    .catch(e => console.error(e))
    .finally(async () => await prisma.$disconnect())
