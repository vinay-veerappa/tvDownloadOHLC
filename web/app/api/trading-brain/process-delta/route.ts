/**
 * WS-4.2 Daily Process Delta Scorecard API.
 *
 * Bridges to the canonical Trading Brain ledger through the python web bridge
 * (`scripts/trading_brain/web_bridge.py`). The bridge is the ONLY access path:
 * the scorecard logic (compliance fail-closed rules, RISK_UNASSESSABLE, scoring
 * gates) lives server-side in python and is never reimplemented in TypeScript.
 */

import { NextResponse } from 'next/server';
import { runBridgeHandler } from '@/lib/trading-brain-bridge';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sessionDate = searchParams.get('session_date') ?? new Date().toISOString().slice(0, 10);
  const ticker = searchParams.get('ticker') ?? 'NQ1';

  try {
    const result = await runBridgeHandler('process_delta', {
      session_date: sessionDate,
      ticker,
    });
    if ('error' in result) {
      return NextResponse.json(result, { status: 500 });
    }
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}