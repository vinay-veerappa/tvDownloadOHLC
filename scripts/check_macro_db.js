const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const snapshots = await prisma.macroSnapshot.findMany({
    select: { ticker: true, timestamp: true },
    orderBy: { timestamp: 'desc' },
    take: 20
  });
  console.log('Recent Macro Snapshots:');
  console.table(snapshots);
  
  const nq_d = await prisma.macroSnapshot.findFirst({
    where: { ticker: '/NQ[D]' }
  });
  console.log('/NQ[D] exists:', !!nq_d);
}

main()
  .catch(e => console.error(e))
  .finally(async () => await prisma.$disconnect());
