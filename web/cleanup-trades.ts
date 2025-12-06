import { PrismaClient } from "@prisma/client"

const prisma = new PrismaClient()

async function main() {
    console.log("Cleaning up trades...")
    // Delete positions first if they exist in a separate model, but here we only have Trade
    // If Tags relation exists, cascade delete might be needed or delete tags first
    // But usually Trade deletion cascades to Tags if configured, or we delete Tags

    // Check if Tags exist and rely on Trade
    // Schema says: tags Tag[]
    // Let's delete tags first just in case

    // Actually, Tag model might be separate.
    // Let's just delete Trade and see.
    const deleted = await prisma.trade.deleteMany({})
    console.log(`Deleted ${deleted.count} trades.`)
}

main()
    .catch((e) => {
        console.error(e)
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })
