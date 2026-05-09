import { PrismaClient } from '@prisma/client'
import 'dotenv/config'

const prisma = new PrismaClient()

async function main() {
  console.log('Querying ExpectedMove for SPY...')
  const count = await prisma.expectedMove.count({ where: { ticker: 'SPY' } })
  console.log(`Total SPY records: ${count}`)
  const ems = await prisma.expectedMove.findMany({
    where: { 
      ticker: 'SPY',
      calculationDate: {
        gte: new Date('2026-05-01')
      }
    },
    select: { calculationDate: true, adjEm: true, expiryDate: true },
    orderBy: { calculationDate: 'desc' }
  })
  console.log(JSON.stringify(ems, null, 2))
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
