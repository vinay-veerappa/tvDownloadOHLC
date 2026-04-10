import { NextResponse } from 'next/server';
import prisma from '@/lib/prisma';

type GapRow = {
  start: Date;
  end: Date;
  days: number;
};

function computeGaps(datesAsc: Date[], thresholdDays: number): GapRow[] {
  const out: GapRow[] = [];
  for (let i = 1; i < datesAsc.length; i++) {
    const prev = datesAsc[i - 1];
    const curr = datesAsc[i];
    const days = (curr.getTime() - prev.getTime()) / (24 * 60 * 60 * 1000);
    if (days >= thresholdDays) {
      out.push({ start: prev, end: curr, days });
    }
  }
  return out;
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const thresholdDays = Number(searchParams.get('thresholdDays') ?? '14');
    const threshold = Number.isFinite(thresholdDays) ? thresholdDays : 14;

    const total = await prisma.economicEvent.count();

    const first = await prisma.economicEvent.findFirst({
      orderBy: { datetime: 'asc' },
      select: { datetime: true, name: true }
    });

    const last = await prisma.economicEvent.findFirst({
      orderBy: { datetime: 'desc' },
      select: { datetime: true, name: true }
    });

    const rows = await prisma.economicEvent.findMany({
      orderBy: { datetime: 'asc' },
      select: { datetime: true }
    });

    const dates = rows.map(r => r.datetime);
    const gaps = computeGaps(dates, threshold)
      .sort((a, b) => b.days - a.days)
      .slice(0, 10)
      .map(g => ({
        start: g.start.toISOString(),
        end: g.end.toISOString(),
        days: Number(g.days.toFixed(2))
      }));

    const nowMs = Date.now();
    const freshnessDays = last
      ? Math.floor((last.datetime.getTime() - nowMs) / (24 * 60 * 60 * 1000))
      : null;

    return NextResponse.json({
      success: true,
      summary: {
        total,
        first: first ? { datetime: first.datetime.toISOString(), name: first.name } : null,
        last: last ? { datetime: last.datetime.toISOString(), name: last.name } : null,
        freshnessDays,
        thresholdDays: threshold,
        gapsFound: gaps.length
      },
      gaps
    });
  } catch (error) {
    return NextResponse.json({ success: false, error: 'Failed to compute economic-event coverage' }, { status: 500 });
  }
}
