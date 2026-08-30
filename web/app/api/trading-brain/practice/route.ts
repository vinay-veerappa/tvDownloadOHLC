/**
 * WS-4.3 Deliberate Practice Terminal API.
 *
 * GET  -> generate the next blinded drill (server seals answers; client receives
 *         only blinded bars + custody token).
 * POST -> commit-before-reveal submission (DrillDeclaration; double-submit locks).
 *
 * Custody: ASSESSMENT drills require a signed custody token server-side (HMAC key
 * from TRADING_BRAIN_DRILL_HMAC_KEY). Synthetic drills are barred from ASSESSMENT
 * in the python layer (ADR-024 §5).
 */

import { NextResponse } from 'next/server';
import { runBridgeHandler } from '@/lib/trading-brain-bridge';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sessionDate = searchParams.get('session_date');
  const ticker = searchParams.get('ticker') ?? 'NQ1';
  const drillType = searchParams.get('drill_type') ?? 'RECOGNITION';
  const datasetSplit = searchParams.get('dataset_split') ?? 'TRAINING';
  const synthetic = searchParams.get('synthetic') === 'true';

  if (!sessionDate && !synthetic) {
    return NextResponse.json(
      { error: 'session_date is required for authentic drills (or pass synthetic=true)' },
      { status: 400 }
    );
  }

  try {
    const result = await runBridgeHandler('drill_next', {
      drill_type: drillType,
      dataset_split: datasetSplit,
      session_date: sessionDate ?? new Date().toISOString().slice(0, 10),
      ticker,
    });
    if ('error' in result) return NextResponse.json(result, { status: 500 });
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const required = ['drill_id', 'declared_bias', 'declared_setup', 'declared_entry_price', 'declared_stop_bps', 'declared_target_bps'];
    for (const key of required) {
      if (body[key] === undefined || body[key] === null) {
        return NextResponse.json({ error: `Missing required field '${key}'` }, { status: 400 });
      }
    }
    const result = await runBridgeHandler('drill_submit', {
      drill_id: body.drill_id,
      declared_bias: body.declared_bias,
      declared_setup: body.declared_setup,
      declared_entry_price: String(body.declared_entry_price),
      declared_stop_bps: String(body.declared_stop_bps),
      declared_target_bps: String(body.declared_target_bps),
      latency_ms: body.latency_ms ? String(body.latency_ms) : undefined,
    });
    if ('error' in result) return NextResponse.json(result, { status: 500 });
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}