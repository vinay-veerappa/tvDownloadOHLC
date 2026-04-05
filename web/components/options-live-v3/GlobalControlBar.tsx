"use client";

import React, { useEffect, useRef, useState } from "react";

export type GexTabId =
  | "daily-gex"
  | "by-strike"
  | "by-expiry"
  | "integrated"
  | "largest"
  | "levels"
  | "spot-gamma"
  | "heatmap"
  | "flow";

export type MetricFamily = "GEX" | "DEX" | "VANNA" | "CHARM";

const STRIKE_PRESETS = [5, 10, 15, 20, 30, 50] as const;

const TABS: { id: GexTabId; label: string }[] = [
  { id: "daily-gex", label: "Daily GEX" },
  { id: "by-strike", label: "By Strike" },
  { id: "by-expiry", label: "By Expiry" },
  { id: "integrated", label: "Integrated" },
  { id: "largest", label: "Largest" },
  { id: "levels", label: "Levels" },
  { id: "spot-gamma", label: "Spot Γ" },
  { id: "heatmap", label: "Heatmap" },
  { id: "flow", label: "Flow" },
];

const METRIC_FAMILIES: MetricFamily[] = ["GEX", "DEX", "VANNA", "CHARM"];
const WORKFLOW_PRESETS = [
  { label: "Scalper", strikeCount: 10 },
  { label: "Intraday", strikeCount: 20 },
  { label: "Swing", strikeCount: 50 },
] as const;

type Props = {
  symbol: string;
  onSymbolChange: (s: string) => void;
  strikeCount: number;
  onStrikeCountChange: (n: number) => void;
  expiryScope: string;
  onExpiryScopeChange: (s: string) => void;
  metricFamily: MetricFamily;
  onMetricFamilyChange: (m: MetricFamily) => void;
  activeTab: GexTabId;
  onTabChange: (t: GexTabId) => void;
  isLoading: boolean;
  freshness?: string | null;
};

export function GlobalControlBar({
  symbol,
  onSymbolChange,
  strikeCount,
  onStrikeCountChange,
  expiryScope,
  onExpiryScopeChange,
  metricFamily,
  onMetricFamilyChange,
  activeTab,
  onTabChange,
  isLoading,
  freshness,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [customStrike, setCustomStrike] = useState<string>("");

  useEffect(() => {
    if (strikeCount > 0 && !STRIKE_PRESETS.includes(strikeCount as (typeof STRIKE_PRESETS)[number])) {
      setCustomStrike(String(strikeCount));
    }
  }, [strikeCount]);

  const handleSymbolCommit = () => {
    const val = inputRef.current?.value.trim().toUpperCase() ?? "";
    if (val && val !== symbol) onSymbolChange(val);
  };

  const applyCustomStrike = () => {
    const parsed = Number(customStrike);
    if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 200) {
      onStrikeCountChange(Math.round(parsed));
    }
  };

  return (
    <div className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
      {/* Upper row: symbol + controls */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-2">
        {/* Symbol input */}
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            defaultValue={symbol}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSymbolCommit();
            }}
            onBlur={handleSymbolCommit}
            className="h-8 w-28 rounded border border-zinc-700 bg-black px-2 text-sm font-mono text-zinc-100 focus:border-emerald-600 focus:outline-none"
            placeholder="SPY"
          />
          {isLoading ? (
            <span className="text-xs text-zinc-500 animate-pulse">loading…</span>
          ) : freshness ? (
            <span className="text-xs text-zinc-500">{freshness}</span>
          ) : null}
        </div>

        <div className="h-4 w-px bg-zinc-800" />

        {/* Strike count */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-zinc-500">Strikes:</span>
          {STRIKE_PRESETS.map((n) => (
            <button
              key={n}
              onClick={() => onStrikeCountChange(n)}
              className={`h-6 w-9 rounded text-xs font-medium transition-colors ${
                strikeCount === n
                  ? "bg-emerald-700 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
              }`}
            >
              {n}
            </button>
          ))}
          <button
            onClick={() => onStrikeCountChange(0)}
            className={`h-6 w-9 rounded text-xs font-medium transition-colors ${
              strikeCount === 0
                ? "bg-emerald-700 text-white"
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            }`}
          >
            All
          </button>
          <input
            value={customStrike}
            onChange={(e) => setCustomStrike(e.target.value.replace(/[^\d]/g, ""))}
            onKeyDown={(e) => {
              if (e.key === "Enter") applyCustomStrike();
            }}
            placeholder="Custom"
            className="h-6 w-16 rounded border border-zinc-700 bg-zinc-900 px-2 text-xs text-zinc-200 focus:outline-none"
            aria-label="Custom strikes"
          />
          <button
            onClick={applyCustomStrike}
            className="h-6 rounded bg-zinc-800 px-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700"
          >
            Apply
          </button>
        </div>

        <div className="h-4 w-px bg-zinc-800" />

        <div className="flex items-center gap-1">
          <span className="text-xs text-zinc-500">Preset:</span>
          {WORKFLOW_PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => onStrikeCountChange(preset.strikeCount)}
              className="h-6 rounded bg-zinc-800 px-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700"
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-zinc-800" />

        {/* Expiry scope */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-zinc-500">Expiry:</span>
          <select
            value={expiryScope}
            onChange={(e) => onExpiryScopeChange(e.target.value)}
            className="h-6 rounded border border-zinc-700 bg-zinc-900 px-1 text-xs text-zinc-200 focus:outline-none"
          >
            <option value="all">All</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="0dte">0DTE</option>
          </select>
        </div>

        <div className="h-4 w-px bg-zinc-800" />

        {/* Metric family */}
        <div className="flex items-center gap-1">
          {METRIC_FAMILIES.map((mf) => (
            <button
              key={mf}
              onClick={() => onMetricFamilyChange(mf)}
              className={`h-6 rounded px-2 text-xs font-medium transition-colors ${
                metricFamily === mf
                  ? "bg-violet-700 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
              }`}
            >
              {mf}
            </button>
          ))}
        </div>
      </div>

      {/* Tab row */}
      <div className="flex overflow-x-auto px-4 pb-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`relative flex-shrink-0 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "text-emerald-400 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-emerald-500"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
