import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const run = await prisma.researchRun.findUnique({
      where: { id },
      include: { strategy: true }
    });

    if (!run) {
      return NextResponse.json({ error: 'Research run not found' }, { status: 404 });
    }

    return NextResponse.json(run);
  } catch (error) {
    console.error('Error fetching research run:', error);
    return NextResponse.json({ error: 'Failed to load research data' }, { status: 500 });
  }
}
