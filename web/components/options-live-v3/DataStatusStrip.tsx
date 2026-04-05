"use client";

import React from "react";

type Props = {
  asOf?: string | null;
  freshnessMs?: number | null;
  warnings?: string[];
  error?: string | null;
  staleThresholdMs?: number;
};

function ageLabel(freshnessMs: number | null | undefined): string {
  if (freshnessMs == null || !Number.isFinite(freshnessMs)) return "Age unavailable";
  const seconds = Math.round(freshnessMs / 1000);
  if (seconds < 60) return `${seconds}s old`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m old`;
  const hours = Math.round(minutes / 60);
  return `${hours}h old`;
}

export function DataStatusStrip({
  asOf,
  freshnessMs,
  warnings = [],
  error = null,
  staleThresholdMs = 120_000,
}: Props) {
  const isStale = typeof freshnessMs === "number" && freshnessMs > staleThresholdMs;
  const hasWarnings = warnings.length > 0;
  const degraded = Boolean(error) || hasWarnings;

  if (!asOf && freshnessMs == null && !degraded) return null;

  return (
    <div
      className={`rounded-xl border px-3 py-2 text-xs ${
        error
          ? "border-rose-900/70 bg-rose-950/30 text-rose-200"
          : isStale
          ? "border-amber-900/70 bg-amber-950/30 text-amber-200"
          : degraded
          ? "border-zinc-800 bg-zinc-900/60 text-zinc-200"
          : "border-emerald-900/60 bg-emerald-950/20 text-emerald-200"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold uppercase tracking-wider">
          {error ? "Degraded" : isStale ? "Stale" : degraded ? "Partial Data" : "Fresh"}
        </span>
        {asOf && <span>As of {asOf}</span>}
        <span>{ageLabel(freshnessMs)}</span>
        {hasWarnings && <span>{warnings.length} warning{warnings.length === 1 ? "" : "s"}</span>}
      </div>
      {(error || hasWarnings) && (
        <details className="mt-1">
          <summary className="cursor-pointer text-[11px] opacity-80">Details</summary>
          <div className="mt-1 space-y-1">
            {error && <p>{error}</p>}
            {warnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>{warning}</p>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
