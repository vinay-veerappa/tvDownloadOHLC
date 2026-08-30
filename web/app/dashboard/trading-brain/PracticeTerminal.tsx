'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Lock, LockOpen, Timer } from 'lucide-react';

interface DrillContext {
  drill_id: string;
  drill_type: string;
  dataset_split: string;
  custody_mode: string | null;
  custody_token: string | null;
  blinded_bars: Array<{
    bar_index: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

interface DrillFeedback {
  drill_id: string;
  process_adherence_score: number;
  true_bias: string;
  true_setup: string;
  notes?: string | null;
}

const BIAS_OPTIONS = ['BULLISH', 'BEARISH', 'NEUTRAL'] as const;

/** Renders blinded OHLC bars as a simple candle sketch (no answers leak). */
function BlindedBars({ bars }: { bars: DrillContext['blinded_bars'] }) {
  if (!bars.length) return <div className="text-sm text-muted-foreground">No bars.</div>;
  const min = Math.min(...bars.map((b) => b.low));
  const max = Math.max(...bars.map((b) => b.high));
  const span = max - min || 1;
  return (
    <div className="flex items-end gap-[2px] h-40">
      {bars.map((b) => {
        const bodyLow = ((Math.min(b.open, b.close) - min) / span) * 100;
        const bodyH = Math.max(1, (Math.abs(b.close - b.open) / span) * 100);
        const up = b.close >= b.open;
        return (
          <div key={b.bar_index} className="relative flex-1 h-full" title={`O ${b.open} H ${b.high} L ${b.low} C ${b.close}`}>
            <div
              className={`absolute w-full rounded-[1px] ${up ? 'bg-emerald-500/80' : 'bg-red-500/80'}`}
              style={{ bottom: `${bodyLow}%`, height: `${bodyH}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}

export function PracticeTerminal() {
  const [sessionDate, setSessionDate] = useState('2026-08-28');
  const [ticker, setTicker] = useState('NQ1');
  const [synthetic, setSynthetic] = useState(true);
  const [drill, setDrill] = useState<DrillContext | null>(null);
  const [feedback, setFeedback] = useState<DrillFeedback | null>(null);
  const [declaredBias, setDeclaredBias] = useState<string>('BULLISH');
  const [declaredSetup, setDeclaredSetup] = useState('ALN_LPEU');
  const [entry, setEntry] = useState('');
  const [stopBps, setStopBps] = useState('12');
  const [targetBps, setTargetBps] = useState('10');
  const [committed, setCommitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerStart = useRef<number | null>(null);

  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFeedback(null);
    setCommitted(false);
    timerStart.current = Date.now();
    try {
      const params = new URLSearchParams({ ticker, drill_type: 'RECOGNITION', dataset_split: 'TRAINING' });
      if (synthetic) params.set('synthetic', 'true');
      else params.set('session_date', sessionDate);
      const res = await fetch(`/api/trading-brain/practice?${params}`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
      setDrill(json as DrillContext);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate drill');
      setDrill(null);
    } finally {
      setLoading(false);
    }
  }, [sessionDate, ticker, synthetic]);

  useEffect(() => {
    void generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = useCallback(async () => {
    if (!drill) return;
    setLoading(true);
    try {
      const latency = timerStart.current ? Date.now() - timerStart.current : null;
      const res = await fetch('/api/trading-brain/practice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          drill_id: drill.drill_id,
          declared_bias: declaredBias,
          declared_setup: declaredSetup,
          declared_entry_price: Number(entry) || 0,
          declared_stop_bps: Number(stopBps),
          declared_target_bps: Number(targetBps),
          latency_ms: latency,
        }),
      });
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`);
      setFeedback(json as DrillFeedback);
      setCommitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setLoading(false);
    }
  }, [drill, declaredBias, declaredSetup, entry, stopBps, targetBps]);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <LockOpen className="h-4 w-4" /> Blinded Session Replay
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && (
            <Alert>
              <AlertTitle>Drill error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {loading && !drill && <Skeleton className="h-40 w-full" />}
          {drill && (
            <>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">{drill.drill_type}</Badge>
                <Badge variant="outline">{drill.dataset_split}</Badge>
                {drill.custody_mode && <Badge variant="outline">{drill.custody_mode}</Badge>}
                {committed ? <Lock className="h-3 w-3 text-emerald-500" /> : <Timer className="h-3 w-3" />}
              </div>
              <BlindedBars bars={drill.blinded_bars} />
            </>
          )}
          {feedback && (
            <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-3 space-y-1">
              <div className="text-sm font-medium">Adherence: {feedback.process_adherence_score.toFixed(1)}/100</div>
              <div className="text-xs text-muted-foreground">True bias: {feedback.true_bias} · True setup: {feedback.true_setup}</div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Commit Before Reveal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Ticker</Label>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="h-8" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Session</Label>
              <Input type="date" value={sessionDate} onChange={(e) => setSessionDate(e.target.value)} className="h-8" disabled={synthetic} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} /> synthetic proxy (mechanics practice)
          </label>
          <div className="space-y-1">
            <Label className="text-xs">Declared Bias</Label>
            <div className="flex gap-1">
              {BIAS_OPTIONS.map((b) => (
                <Button
                  key={b} size="sm" variant={declaredBias === b ? 'default' : 'outline'}
                  className="h-7 text-xs flex-1" disabled={committed}
                  onClick={() => setDeclaredBias(b)}
                >
                  {b}
                </Button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Setup</Label>
              <Input value={declaredSetup} onChange={(e) => setDeclaredSetup(e.target.value)} className="h-8" disabled={committed} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Entry</Label>
              <Input value={entry} onChange={(e) => setEntry(e.target.value)} placeholder="20000" className="h-8" disabled={committed} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Stop (bps)</Label>
              <Input value={stopBps} onChange={(e) => setStopBps(e.target.value)} className="h-8" disabled={committed} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Target (bps)</Label>
              <Input value={targetBps} onChange={(e) => setTargetBps(e.target.value)} className="h-8" disabled={committed} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="flex-1" onClick={() => void generate()} disabled={loading}>
              New Drill
            </Button>
            <Button size="sm" className="flex-1" onClick={() => void submit()} disabled={loading || !drill || committed}>
              {committed ? 'Committed' : 'Lock In'}
            </Button>
          </div>
          {committed && (
            <div className="text-xs text-muted-foreground">
              Commit-before-reveal locked: a second submission is refused by the sealed ledger.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}