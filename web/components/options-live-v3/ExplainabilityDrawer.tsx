"use client";

import React, { useEffect, useState } from "react";

type ExplainResponse = {
  success: boolean;
  data: {
    snapshotId: string;
    rules: Array<{ name: string; description: string }>;
    outputs: Record<string, number | null>;
    sources: { pipelineStatePresent: boolean; dailyLevelsPresent: boolean };
  } | null;
  warnings: string[];
  error: string | null;
};

type Props = {
  symbol: string;
  snapshotId: string | null;
  isOpen: boolean;
  onClose: () => void;
};

function fmt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "-";
  return v.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

export function ExplainabilityDrawer({ symbol, snapshotId, isOpen, onClose }: Props) {
  const [payload, setPayload] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !snapshotId) return;
    const currentSnapshotId = snapshotId;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const res = await fetch(`/api/options-live/v3/explain?symbol=${encodeURIComponent(symbol)}&snapshotId=${encodeURIComponent(currentSnapshotId)}`);
        const json = (await res.json()) as ExplainResponse;
        if (!cancelled) setPayload(json);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [isOpen, snapshotId, symbol]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm">
      <div className="h-full w-full max-w-lg overflow-y-auto border-l border-zinc-800 bg-zinc-950 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Why This Score?</h2>
            <p className="text-xs text-zinc-500">{symbol} • {snapshotId ?? "-"}</p>
          </div>
          <button onClick={onClose} className="rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">✕</button>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-zinc-500">Loading explainability data…</p>
        ) : payload?.error ? (
          <p className="mt-4 rounded border border-rose-900/70 bg-rose-950/30 p-3 text-sm text-rose-200">{payload.error}</p>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs uppercase tracking-wider text-zinc-500">Outputs</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                {Object.entries(payload?.data?.outputs ?? {}).map(([key, value]) => (
                  <div key={key} className="rounded border border-zinc-800 bg-zinc-950/60 px-3 py-2">
                    <p className="text-xs text-zinc-500">{key}</p>
                    <p className="font-mono text-zinc-100">{fmt(value)}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-xs uppercase tracking-wider text-zinc-500">Deterministic Rules</p>
              <div className="mt-2 space-y-2 text-sm text-zinc-300">
                {(payload?.data?.rules ?? []).map((rule) => (
                  <div key={rule.name} className="rounded border border-zinc-800 bg-zinc-950/60 px-3 py-2">
                    <p className="font-medium text-zinc-100">{rule.name}</p>
                    <p className="mt-1 text-zinc-400">{rule.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wider text-zinc-500">Source Integrity</p>
              <p className="mt-2">Pipeline state: {payload?.data?.sources.pipelineStatePresent ? "present" : "missing"}</p>
              <p>Daily levels: {payload?.data?.sources.dailyLevelsPresent ? "present" : "missing"}</p>
              {(payload?.warnings ?? []).length > 0 && (
                <div className="mt-2 rounded border border-amber-900/60 bg-amber-950/20 p-2 text-amber-200">
                  {(payload?.warnings ?? []).join(" | ")}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
