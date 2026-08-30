/**
 * WS-4.4 Model Governance & Calibration API: model registry, deployment events,
 * shadow findings, and the calibration snapshot.
 */

import { NextResponse } from 'next/server';
import { runBridgeHandler } from '@/lib/trading-brain-bridge';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sessionDate = searchParams.get('session_date') ?? new Date().toISOString().slice(0, 10);
  const ticker = searchParams.get('ticker') ?? 'NQ1';

  try {
    const governance = await runBridgeHandler('governance', {});
    if ('error' in governance) {
      return NextResponse.json(governance, { status: 500 });
    }
    const calibration = await runBridgeHandler('calibration', {
      session_date: sessionDate,
      ticker,
    });
    return NextResponse.json({ ...governance, calibration });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}