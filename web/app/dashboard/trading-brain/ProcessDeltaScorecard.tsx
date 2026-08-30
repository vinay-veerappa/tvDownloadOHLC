'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { RefreshCw, AlertTriangle, CheckCircle2, XCircle, Scale } from 'lucide-react';

interface ProcessDeltaResponse {
  session_date: string;
  ticker: string;
  plan_compliant: boolean;
  bias_direction_respected: boolean;
  permitted_strategies_respected: boolean;
  risk_budget_respected: boolean;
  risk_assessment_state: 'VERIFIED' | 'RISK_UNASSESSABLE';
  process_outcome_quadrant: string;
  plan: {
    plan_found: boolean;
    primary_bias: string | null;
    max_intended_risk_bps: number | null;
    permitted_strategies: string[];
    amendment_count: number;
    provenance_class: string | null;
  };
  forecast: {
    forecast_found: boolean;
    forecast_mode: string | null;
    predicted_bias: string | null;
    prob_distribution: Record<string, number>;
    abstain_flag: boolean;
    session_brier_loss: number | null;
    scored_for_calibration: boolean;
  };
  execution: {
    total_opportunities: number;
    executed_count: number;
    passed_count: number;
    missed_count: number;
    offline_count: number;
    unmatched_execution_count: number;
    total_executions: number;
    interventions_count: number;
    net_position: number;
    avg_slippage_bps: number | null;
    opportunities: Array<Record<string, unknown>>;
  };
  tape: {
    tape_found: boolean;
    session_open: number;
    session_high: number;
    session_low: number;
    session_close: number;
    session_range_bps: number;
    realized_day_type: string;
    quality_state: string;
  } | null;
}

const QUADRANT_STYLES: Record<string, { label: string; className: string }> = {
  GOOD_PROCESS_GOOD_OUTCOME: { label: 'Good Process · Good Outcome', className: 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30' },
  GOOD_PROCESS_BAD_OUTCOME: { label: 'Good Process · Bad Outcome', className: 'bg-amber-500/15 text-amber-500 border-amber-500/30' },
  BAD_PROCESS_GOOD_OUTCOME: { label: 'Bad Process · Good Outcome', className: 'bg-orange-500/15 text-orange-500 border-orange-500/30' },
  BAD_PROCESS_BAD_OUTCOME: { label: 'Bad Process · Bad Outcome', className: 'bg-red-500/15 text-red-500 border-red-500/30' },
};

function QuadrantCard({ scorecard }: { scorecard: ProcessDeltaResponse }) {
  const style = QUADRANT_STYLES[scorecard.process_outcome_quadrant] ?? {
    label: scorecard.process_outcome_quadrant,
    className: 'bg-muted text-muted-foreground border-border',
  };
  const checks = [
    { name: 'Bias Direction', ok: scorecard.bias_direction_respected },
    { name: 'Permitted Strategies', ok: scorecard.permitted_strategies_respected },
    { name: 'Risk Budget', ok: scorecard.risk_budget_respected, unassessable: scorecard.risk_assessment_state === 'RISK_UNASSESSABLE' },
  ];
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Process Outcome Quadrant</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Badge variant="outline" className={`text-sm px-3 py-1 ${style.className}`}>{style.label}</Badge>
        <div className="space-y-2">
          {checks.map((c) => (
            <div key={c.name} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{c.name}</span>
              {c.unassessable ? (
                <Badge variant="outline" className="text-yellow-600 border-yellow-600/40">RISK_UNASSESSABLE</Badge>
              ) : c.ok ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function ProcessDeltaScorecard() {
  const [sessionDate, setSessionDate] = useState(new Date().toISOString().slice(0, 10));
  const [ticker, setTicker] = useState('NQ1');
  const [data, setData] = useState<ProcessDeltaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/trading-brain/process-delta?session_date=${sessionDate}&ticker=${ticker}`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
      setData(json as ProcessDeltaResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scorecard');
    } finally {
      setLoading(false);
    }
  }, [sessionDate, ticker]);

  useEffect(() => {
    void load();
  }, [load]);

  const brier = useMemo(() => data?.forecast?.session_brier_loss ?? null, [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Ticker</label>
          <Input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="w-24 h-8" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Session Date</label>
          <Input type="date" value={sessionDate} onChange={(e) => setSessionDate(e.target.value)} className="w-40 h-8" />
        </div>
        <Button size="sm" variant="outline" onClick={() => void load()} disabled={loading} className="h-8">
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Scorecard unavailable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && !data && <Skeleton className="h-64 w-full" />}

      {data && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <QuadrantCard scorecard={data} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Plan (Ex-Ante)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {data.plan.plan_found ? (
                <>
                  <div className="flex justify-between"><span className="text-muted-foreground">Bias</span><Badge variant="outline">{data.plan.primary_bias}</Badge></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Max Risk</span><span>{data.plan.max_intended_risk_bps?.toFixed(1) ?? '—'} bps</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Provenance</span><span className="text-xs">{data.plan.provenance_class}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Amendments</span><span>{data.plan.amendment_count}</span></div>
                </>
              ) : (
                <span className="text-sm text-muted-foreground">No eligible ex-ante plan resolved for this session.</span>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Forecast (Day Type)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {data.forecast.forecast_found ? (
                <>
                  <div className="flex justify-between"><span className="text-muted-foreground">Mode</span><Badge variant="outline">{data.forecast.forecast_mode}</Badge></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Predicted Bias</span><span>{data.forecast.predicted_bias ?? '—'}</span></div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Session Brier</span>
                    {brier !== null ? <Badge variant="outline">{brier.toFixed(4)}</Badge> : <span className="text-xs text-muted-foreground">not scored</span>}
                  </div>
                  {data.forecast.abstain_flag && (
                    <div className="text-xs text-muted-foreground">ABSTAIN — directional levels only, no calibrated 5-class model.</div>
                  )}
                </>
              ) : (
                <span className="text-sm text-muted-foreground">No forecast registered.</span>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Tape Actuals & Execution</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {data.tape?.tape_found ? (
                <>
                  <div className="flex justify-between"><span className="text-muted-foreground">Realized Day Type</span><Badge variant="outline">{data.tape.realized_day_type}</Badge></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Range</span><span>{data.tape.session_range_bps.toFixed(1)} bps</span></div>
                </>
              ) : (
                <div className="text-muted-foreground">No tape actuals.</div>
              )}
              <div className="flex justify-between"><span className="text-muted-foreground">Opportunities</span><span>{data.execution.total_opportunities}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Executed / Missed</span><span>{data.execution.executed_count} / {data.execution.missed_count}</span></div>
              {data.execution.unmatched_execution_count > 0 && (
                <div className="flex justify-between text-orange-500"><span>Unmatched Executions</span><span>{data.execution.unmatched_execution_count}</span></div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}