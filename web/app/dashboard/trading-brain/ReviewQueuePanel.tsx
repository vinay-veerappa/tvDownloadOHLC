'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Inbox, Link2, CheckCircle2, XCircle, ShieldAlert } from 'lucide-react';

interface CatalogItem {
  information_id: string;
  evidence_class: string;
  time_orientation: string;
  source_type: string;
  title: string;
  available_at_utc: string;
  received_at_utc: string;
  active_review_state: string | null;
}

interface ReviewQueueData {
  unmatched_links: Array<Record<string, unknown>>;
  catalog_items: CatalogItem[];
}

const STATE_STYLES: Record<string, string> = {
  ACCEPTED: 'text-emerald-500 border-emerald-500/40',
  REJECTED: 'text-red-500 border-red-500/40',
  QUARANTINED: 'text-orange-500 border-orange-500/40',
  CAPTURED: 'text-muted-foreground border-border',
};

export function ReviewQueuePanel() {
  const [data, setData] = useState<ReviewQueueData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/trading-brain/review-queue');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
      setData(json as ReviewQueueData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const review = useCallback(
    async (informationId: string, reviewState: 'ACCEPTED' | 'REJECTED' | 'QUARANTINED') => {
      setActing(informationId);
      try {
        const res = await fetch('/api/trading-brain/review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            kind: 'catalog_review',
            information_id: informationId,
            review_state: reviewState,
            reviewer: 'WEB_REVIEW_QUEUE',
            review_notes: 'WS-4.5 one-click triage',
          }),
        });
        const json = await res.json();
        if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Review transition failed');
      } finally {
        setActing(null);
      }
    },
    [load]
  );

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Link2 className="h-4 w-4" /> Unmatched Execution Links
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : data && data.unmatched_links.length > 0 ? (
            <div className="space-y-2 text-sm">
              {data.unmatched_links.map((l, i) => (
                <div key={i} className="rounded border border-border p-2 font-mono text-xs">
                  {JSON.stringify(l)}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" /> No open unmatched links.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Inbox className="h-4 w-4" /> Catalog Review Queue
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            (data?.catalog_items ?? []).map((item) => (
              <div key={item.information_id} className="rounded border border-border p-2 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{item.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.evidence_class} · {item.time_orientation} · {item.received_at_utc?.slice(0, 16)}
                    </div>
                  </div>
                  <Badge variant="outline" className={STATE_STYLES[item.active_review_state ?? 'CAPTURED']}>
                    {item.active_review_state ?? 'CAPTURED'}
                  </Badge>
                </div>
                <div className="flex gap-1">
                  <Button
                    size="sm" variant="outline" className="h-6 text-xs"
                    disabled={acting === item.information_id || item.active_review_state === 'ACCEPTED'}
                    onClick={() => void review(item.information_id, 'ACCEPTED')}
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" /> Accept
                  </Button>
                  <Button
                    size="sm" variant="outline" className="h-6 text-xs"
                    disabled={acting === item.information_id || item.active_review_state === 'REJECTED'}
                    onClick={() => void review(item.information_id, 'REJECTED')}
                  >
                    <XCircle className="h-3 w-3 mr-1" /> Reject
                  </Button>
                  <Button
                    size="sm" variant="outline" className="h-6 text-xs"
                    disabled={acting === item.information_id || item.active_review_state === 'QUARANTINED'}
                    onClick={() => void review(item.information_id, 'QUARANTINED')}
                  >
                    <ShieldAlert className="h-3 w-3 mr-1" /> Quarantine
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert className="lg:col-span-2">
          <AlertTitle>Review queue error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}