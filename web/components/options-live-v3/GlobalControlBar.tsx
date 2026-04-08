"use client";

import React, { useEffect, useRef, useState } from "react";

export type GexTabId =
  | "daily-gex"
  | "by-strike"
  | "by-expiry"
  | "macro"
  | "ops"
  | "legacy-profile"
  | "integrated"
  | "largest"
  | "spot-gamma"
  | "heatmap"
  | "flow";

export type MetricFamily = "GEX" | "DEX" | "VANNA" | "CHARM";
export type WorkflowPresetId = "scalper" | "intraday" | "swing";

const STRIKE_PRESETS = [5, 10, 15, 20, 30, 50] as const;

const TABS: { id: GexTabId; label: string }[] = [
  { id: "daily-gex", label: "Daily GEX" },
  { id: "macro", label: "Macro" },
  { id: "ops", label: "Ops" },
  { id: "legacy-profile", label: "Legacy Profile" },
  { id: "by-strike", label: "By Strike" },
  { id: "by-expiry", label: "By Expiry" },
  { id: "spot-gamma", label: "Spot Γ" },
  { id: "heatmap", label: "Heatmap" },
  { id: "flow", label: "Flow" },
  { id: "largest", label: "Largest" },
  { id: "integrated", label: "Integrated" },
];

const METRIC_FAMILIES: MetricFamily[] = ["GEX", "DEX", "VANNA", "CHARM"];
const WORKFLOW_PRESETS: Array<{ id: WorkflowPresetId; label: string; strikeCount: number }> = [
  { id: "scalper", label: "Scalper", strikeCount: 10 },
  { id: "intraday", label: "Intraday", strikeCount: 20 },
  { id: "swing", label: "Swing", strikeCount: 50 },
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
  activeWorkflowPreset: WorkflowPresetId | null;
  onWorkflowPresetChange: (preset: WorkflowPresetId) => void;
  activeTab: GexTabId;
  onTabChange: (t: GexTabId) => void;
  isLoading: boolean;
  freshness?: string | null;
};

type SymbolLookupItem = {
  symbol: string;
  sources?: string[];
  name?: string | null;
  exchange?: string | null;
  type?: string | null;
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
  activeWorkflowPreset,
  onWorkflowPresetChange,
  activeTab,
  onTabChange,
  isLoading,
  freshness,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [customStrike, setCustomStrike] = useState<string>("");
  const [inputValue, setInputValue] = useState(symbol);
  const [lookupOpen, setLookupOpen] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupItems, setLookupItems] = useState<SymbolLookupItem[]>([]);
  const [activeLookupIndex, setActiveLookupIndex] = useState(-1);
  const customStrikeDisplay =
    customStrike.length > 0
      ? customStrike
      : strikeCount > 0 && !STRIKE_PRESETS.includes(strikeCount as (typeof STRIKE_PRESETS)[number])
        ? String(strikeCount)
        : "";

  useEffect(() => {
    setInputValue(symbol);
  }, [symbol]);

  useEffect(() => {
    const q = inputValue.trim().toUpperCase();
    if (!q) {
      setLookupItems([]);
      setLookupOpen(false);
      setLookupLoading(false);
      return;
    }

    const controller = new AbortController();
    const handle = window.setTimeout(async () => {
      setLookupLoading(true);
      try {
        const res = await fetch(`/api/options-live/v3/symbol-lookup?q=${encodeURIComponent(q)}&limit=10`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!res.ok) return;
        const payload = await res.json();
        const items = (payload?.data?.results ?? []) as SymbolLookupItem[];
        setLookupItems(items);
        setLookupOpen(items.length > 0);
        setActiveLookupIndex(items.length > 0 ? 0 : -1);
      } catch {
        // ignore transient lookup failures
      } finally {
        setLookupLoading(false);
      }
    }, 120);

    return () => {
      window.clearTimeout(handle);
      controller.abort();
    };
  }, [inputValue]);

  const handleSymbolCommit = (candidate?: string) => {
    const val = (candidate ?? inputValue).trim().toUpperCase();
    setInputValue(val);
    setLookupOpen(false);
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
        <div className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value.toUpperCase());
              setLookupOpen(true);
            }}
            onFocus={() => {
              if (lookupItems.length > 0) setLookupOpen(true);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                if (!lookupItems.length) return;
                setLookupOpen(true);
                setActiveLookupIndex((prev) => (prev + 1) % lookupItems.length);
                return;
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                if (!lookupItems.length) return;
                setLookupOpen(true);
                setActiveLookupIndex((prev) => (prev <= 0 ? lookupItems.length - 1 : prev - 1));
                return;
              }
              if (e.key === "Enter") {
                e.preventDefault();
                if (lookupOpen && activeLookupIndex >= 0 && lookupItems[activeLookupIndex]) {
                  handleSymbolCommit(lookupItems[activeLookupIndex].symbol);
                  return;
                }
                handleSymbolCommit();
                return;
              }
              if (e.key === "Escape") {
                setLookupOpen(false);
              }
            }}
            onBlur={() => {
              window.setTimeout(() => handleSymbolCommit(), 100);
            }}
            className="h-8 w-28 rounded border border-zinc-700 bg-black px-2 text-sm font-mono text-zinc-100 focus:border-emerald-600 focus:outline-none"
            placeholder="SPY"
          />
          {lookupOpen && lookupItems.length > 0 && (
            <div className="absolute left-0 top-9 z-50 w-72 overflow-hidden rounded-md border border-zinc-700 bg-zinc-950 shadow-2xl">
              {lookupItems.map((item, idx) => (
                <button
                  key={`${item.symbol}-${idx}`}
                  type="button"
                  className={`flex w-full items-start justify-between gap-2 px-2 py-1.5 text-left transition-colors ${
                    idx === activeLookupIndex ? "bg-zinc-800 text-zinc-100" : "text-zinc-300 hover:bg-zinc-900"
                  }`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSymbolCommit(item.symbol);
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-mono text-zinc-100">{item.symbol}</div>
                    {item.name ? <div className="truncate text-[11px] text-zinc-400">{item.name}</div> : null}
                  </div>
                  <div className="mt-[1px] text-right text-[10px] leading-4 text-zinc-500">
                    <div>{item.exchange ?? item.sources?.[0] ?? "lookup"}</div>
                    {item.type ? <div>{item.type}</div> : null}
                  </div>
                </button>
              ))}
            </div>
          )}
          {lookupLoading && <span className="text-[10px] text-zinc-500">lookup…</span>}
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
            value={customStrikeDisplay}
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
              key={preset.id}
              onClick={() => onWorkflowPresetChange(preset.id)}
              className={`h-6 rounded px-2 text-xs font-medium transition-colors ${
                activeWorkflowPreset === preset.id
                  ? "bg-emerald-700 text-white"
                  : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
              }`}
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
