import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export async function GET() {
  try {
    // 1. Fetch Strategies and their Runs, sorted by latest first
    const strategies = await prisma.researchStrategy.findMany({
      include: {
        runs: {
          orderBy: { createdAt: 'desc' },
          take: 12 // Limit to recent runs for dashboard performance
        }
      },
      orderBy: { name: 'asc' }
    });

    return NextResponse.json(strategies);
  } catch (error) {
    console.error('Error fetching research strategies:', error);
    return NextResponse.json({ error: 'Failed to load research hierarchy' }, { status: 500 });
  }
}
