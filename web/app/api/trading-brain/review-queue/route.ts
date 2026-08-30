/**
 * WS-4.5 Review Queue API (read): open unmatched links + catalog triage items.
 */

import { NextResponse } from 'next/server';
import { runBridgeHandler } from '@/lib/trading-brain-bridge';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sessionDate = searchParams.get('session_date') ?? undefined;

  try {
    const result = await runBridgeHandler('unmatched_links', {
      session_date: sessionDate,
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