"use client";

import React, { useState } from "react";

type ScreenerFactor = {
  name: string;
  value: number; // 0-100 contribution to score
  label?: string; // human-readable description
};

type ScreenerData = {
  probabilityScore?: number | null;
  setup?: string | null;
  confidence?: string | null;
  factors?: ScreenerFactor[];
  summary?: string | null;
};

type Props = {
  screener: ScreenerData | null | undefined;
  isLoading?: boolean;
};

function confidenceColor(confidence: string | null | undefined): string {
  switch (confidence?.toLowerCase()) {
    case "high":
      return "text-emerald-400 bg-emerald-900/30 border-emerald-800";
    case "medium":
      return "text-amber-400 bg-amber-900/30 border-amber-800";
    case "low":
      return "text-rose-400 bg-rose-900/30 border-rose-800";
    default:
      return "text-zinc-400 bg-zinc-900/30 border-zinc-800";
  }
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-zinc-300";
  if (score >= 75) return "text-emerald-300";
  if (score >= 50) return "text-amber-300";
  return "text-rose-300";
}

function scoreGradient(score: number): string {
  if (score >= 75) return "from-emerald-700 to-emerald-500";
  if (score >= 50) return "from-amber-700 to-amber-500";
  return "from-rose-700 to-rose-500";
}

export function SqueezeScreenerCard({ screener, isLoading }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 animate-pulse">
        <div className="h-4 w-32 rounded bg-zinc-800" />
        <div className="mt-2 h-8 w-20 rounded bg-zinc-800" />
      </div>
    );
  }

  const score = screener?.probabilityScore ?? null;
  const confidence = screener?.confidence ?? null;
  const setup = screener?.setup ?? "No setup";
  const factors = screener?.factors ?? [];
  const summary = screener?.summary ?? null;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-400">Squeeze Screener</p>
          <h3 className="mt-0.5 text-base font-semibold text-zinc-100">{setup}</h3>
          {summary && <p className="mt-1 text-xs text-zinc-400 leading-relaxed">{summary}</p>}
        </div>
        <div className="text-right shrink-0">
          <p className={`text-3xl font-bold tabular-nums ${scoreColor(score)}`}>
            {score != null ? score : "—"}
          </p>
          <p className="text-xs text-zinc-500">/100</p>
        </div>
      </div>

      {/* Score bar */}
      {score != null && (
        <div className="h-2 w-full rounded-full bg-zinc-800 overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${scoreGradient(score)} transition-all duration-500`}
            style={{ width: `${score}%` }}
          />
        </div>
      )}

      {/* Confidence badge */}
      {confidence && (
        <span
          className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase tracking-wider ${confidenceColor(confidence)}`}
        >
          {confidence}
        </span>
      )}

      {/* Why this score? expandable */}
      {factors.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <span className="font-medium">{expanded ? "▾" : "▸"} Why this score?</span>
            <span className="text-zinc-600">({factors.length} factors)</span>
          </button>

          {expanded && (
            <div className="mt-2 space-y-1.5">
              {factors.map((factor, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="w-36 shrink-0 text-xs text-zinc-400 truncate">{factor.name}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-violet-600 transition-all duration-300"
                      style={{ width: `${Math.min(100, factor.value)}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs font-mono text-zinc-300 shrink-0">
                    {factor.value.toFixed(0)}
                  </span>
                  {factor.label && (
                    <span className="text-xs text-zinc-500 truncate max-w-[100px]">{factor.label}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Fallback when no factors */}
      {factors.length === 0 && score == null && (
        <p className="text-sm text-zinc-500">No screener data available.</p>
      )}
    </div>
  );
}
