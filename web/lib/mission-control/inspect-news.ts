import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const events = await prisma.economicEvent.findMany({
        take: 100,
        orderBy: { datetime: 'desc' }
    });
    console.log(JSON.stringify(events, null, 2));
}

main()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
