/**
 * WS-4.5 Review Queue API (write): catalog review transitions and unmatched-link
 * resolutions. Both delegate to governance services; the capability gate lives in
 * the python layer (ADR-024) - this route performs NORMAL application writes only.
 */

import { NextResponse } from 'next/server';
import { runBridgeHandler } from '@/lib/trading-brain-bridge';

export async function POST(request: Request) {
  try {
    const body = await request.json();

    if (body.kind === 'catalog_review') {
      if (!body.information_id || !body.review_state || !body.reviewer) {
        return NextResponse.json(
          { error: 'information_id, review_state and reviewer are required' },
          { status: 400 }
        );
      }
      const result = await runBridgeHandler('review', {
        information_id: body.information_id,
        review_state: body.review_state,
        reviewer: body.reviewer,
        review_notes: body.review_notes,
      });
      if ('error' in result) return NextResponse.json(result, { status: 500 });
      return NextResponse.json(result);
    }

    if (body.kind === 'unmatched_resolve') {
      if (!body.source_event_id || !body.actor) {
        return NextResponse.json(
          { error: 'source_event_id and actor are required' },
          { status: 400 }
        );
      }
      // candidate_event_id is optional; when present it must be a NON-EMPTY string -
      // a bare `undefined` would otherwise travel as the literal string "undefined"
      // into the bridge CLI and poison the ledger verification.
      if (body.candidate_event_id !== undefined && body.candidate_event_id !== null && String(body.candidate_event_id).trim() === '') {
        return NextResponse.json(
          { error: 'candidate_event_id must be a non-empty string when provided' },
          { status: 400 }
        );
      }
      const result = await runBridgeHandler('review_unmatched', {
        source_event_id: body.source_event_id,
        candidate_event_id: body.candidate_event_id != null && String(body.candidate_event_id).trim() !== '' ? String(body.candidate_event_id) : undefined,
        actor: body.actor,
        reason: body.reason,
      });
      if ('error' in result) return NextResponse.json(result, { status: 500 });
      return NextResponse.json(result);
    }

    return NextResponse.json({ error: `Unknown review kind '${body.kind}'` }, { status: 400 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}