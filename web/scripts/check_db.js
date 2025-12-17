
const { PrismaClient } = require('@prisma/client');
require('dotenv').config({ path: 'web/.env' }); // CWD is root
const prisma = new PrismaClient();

async function main() {
    console.log('DATABASE_URL:', process.env.DATABASE_URL);
    try {
        const count = await prisma.expectedMove.count();
        console.log(`Total ExpectedMove records: ${count}`);

        const records = await prisma.expectedMove.findMany({ take: 5 });
        console.log('Sample records:', JSON.stringify(records, null, 2));
    } catch (e) {
        console.error('DB Error:', e);
    } finally {
        await prisma.$disconnect();
    }
}

main();
