import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import fs from 'fs/promises';
import path from 'path';

const prisma = new PrismaClient();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    // 1. Fetch Run Metadata from DB
    const run = await prisma.researchRun.findUnique({
      where: { id },
      select: { equityCurvePath: true }
    });

    if (!run || !run.equityCurvePath) {
      return NextResponse.json({ error: 'Run not found or curve path missing' }, { status: 404 });
    }

    // 2. Read the 1m granularity JSON from the file system
    // The path is absolute (e.g. C:/Users/vinay/tvDownloadOHLC/results/RESEARCH/...)
    const fileContent = await fs.readFile(run.equityCurvePath, 'utf-8');
    const data = JSON.parse(fileContent);

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading 1m equity curve:', error);
    return NextResponse.json({ error: 'Failed to load high-fidelity data' }, { status: 500 });
  }
}
