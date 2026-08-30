'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Activity, Database, GitBranch, ScrollText } from 'lucide-react';

interface GovernanceData {
  models: Array<Record<string, unknown>>;
  deployments: Array<Record<string, unknown>>;
  shadow_findings: Array<Record<string, unknown>>;
  calibration: Record<string, unknown>;
}

function statusBadge(status: string | undefined) {
  if (!status) return null;
  const style =
    status === 'CHAMPION' || status === 'PROMOTED'
      ? 'text-emerald-500 border-emerald-500/40'
      : status === 'REJECTED' || status === 'DEMOTED'
        ? 'text-red-500 border-red-500/40'
        : status === 'INCONCLUSIVE_WAITING'
          ? 'text-amber-500 border-amber-500/40'
          : 'text-muted-foreground border-border';
  return (
    <Badge variant="outline" className={style}>
      {status}
    </Badge>
  );
}

export function GovernancePanel() {
  const [data, setData] = useState<GovernanceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/trading-brain/governance');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
      setData(json as GovernanceData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load governance data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Database className="h-4 w-4" /> Model Registry
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : data && data.models.length > 0 ? (
            data.models.map((m, i) => (
              <div key={i} className="rounded border border-border p-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs">{String(m.model_version_id)}</span>
                  {statusBadge(m.status as string)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {String(m.model_family)} · {String(m.version_tag)} · param {String(m.parameter_hash).slice(0, 18)}
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No registered models yet. Promotion requires prior registry rows (ADR-024).</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Activity className="h-4 w-4" /> Shadow Findings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : data && data.shadow_findings.length > 0 ? (
            data.shadow_findings.map((f, i) => {
              const ev = (f.evaluation_result ?? {}) as Record<string, unknown>;
              return (
                <div key={i} className="rounded border border-border p-2 text-sm space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs">{String(f.finding_id)}</span>
                    {statusBadge(f.pipeline_stage as string)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    power {Number(f.statistical_power ?? 0).toFixed(2)} · q {Number(f.fdr_q_value ?? 1).toFixed(4)}
                    {ev.meets_mde !== undefined && (ev.meets_mde ? ' · MDE met' : ' · MDE not met')}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-sm text-muted-foreground">No shadow findings yet. Preregister via the research CLI.</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <ScrollText className="h-4 w-4" /> Promotion Audit Trail
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : data && data.deployments.length > 0 ? (
            data.deployments.slice(0, 12).map((d, i) => (
              <div key={i} className="rounded border border-border p-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs truncate">{String(d.model_version_id)}</span>
                  {statusBadge(d.deployment_status as string)}
                </div>
                <div className="text-xs text-muted-foreground">
                  tier {String(d.tier)} · {String(d.event_timestamp_utc)?.slice(0, 16)} ·{' '}
                  {String(d.eval_metrics_json ?? '').includes('CALLER_ATTESTED') ? 'CALLER_ATTESTED' : ''}
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No deployment events recorded.</div>
          )}
          {data?.calibration && (
            <div className="pt-2 text-xs text-muted-foreground border-t border-border">
              Calibration: {String((data.calibration as { note?: string }).note ?? '')}
            </div>
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert className="lg:col-span-3">
          <AlertTitle>Governance data unavailable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}