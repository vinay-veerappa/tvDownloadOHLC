"use client";

import React, { useEffect, useMemo, useState } from "react";

type Level = {
  label: string;
  value: number | null;
  color: string; // Tailwind bg class
  textColor: string; // Tailwind text class
  isSpot?: boolean;
};

type Props = {
  spot: number | null;
  gammaFlip: number | null;
  callWall: number | null;
  secondaryCallWall?: number | null;
  putWall: number | null;
  secondaryPutWall?: number | null;
  gammaMagnet: number | null;
  pinStrike: number | null;
  expectedMoveUpper?: number | null;
  expectedMoveLower?: number | null;
  expectedMoveWidth?: number | null;
  symbol?: string;
  selectedLevel?: number | null;
  onSelectLevel?: (level: number) => void;
};

function pct(value: number, spot: number): string {
  const d = ((value - spot) / spot) * 100;
  const sign = d >= 0 ? "+" : "";
  return `${sign}${d.toFixed(2)}%`;
}

export function LiveLevelsLadder({
  spot,
  gammaFlip,
  callWall,
  secondaryCallWall = null,
  putWall,
  secondaryPutWall = null,
  gammaMagnet,
  pinStrike,
  expectedMoveUpper = null,
  expectedMoveLower = null,
  expectedMoveWidth = null,
  symbol = "SPY",
  selectedLevel = null,
  onSelectLevel,
}: Props) {
  const [alertBandPct, setAlertBandPct] = useState("0.50");
  const [savingLevel, setSavingLevel] = useState<string | null>(null);
  const [activeRuleNames, setActiveRuleNames] = useState<Set<string>>(new Set());

  const makeRuleName = (levelLabel: string): string =>
    `${symbol}-${levelLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}-prox`;

  useEffect(() => {
    let cancelled = false;
    async function loadRules() {
      try {
        const res = await fetch(`/api/options-live/v3/publish/event-rule?symbol=${encodeURIComponent(symbol)}`);
        if (!res.ok) return;
        const json = (await res.json()) as { data?: { rules?: Array<{ ruleName?: string }> } };
        const names = new Set(
          (json?.data?.rules ?? [])
            .map((r) => r.ruleName)
            .filter((n): n is string => typeof n === "string" && n.length > 0)
        );
        if (!cancelled) setActiveRuleNames(names);
      } catch {
        // keep existing optimistic state
      }
    }
    void loadRules();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Build sorted level list
  const rawLevels: Level[] = [
    { label: "Call Wall", value: callWall, color: "bg-emerald-900/60", textColor: "text-emerald-300" },
    { label: "Call Wall 2", value: secondaryCallWall, color: "bg-emerald-900/35", textColor: "text-emerald-200" },
    { label: "EM High", value: expectedMoveUpper, color: "bg-teal-900/45", textColor: "text-teal-200" },
    { label: "Gamma Flip", value: gammaFlip, color: "bg-violet-900/60", textColor: "text-violet-300" },
    { label: "Spot", value: spot, color: "bg-zinc-700", textColor: "text-zinc-100", isSpot: true },
    { label: "Γ Magnet", value: gammaMagnet, color: "bg-amber-900/60", textColor: "text-amber-300" },
    { label: "Pin Strike", value: pinStrike, color: "bg-sky-900/60", textColor: "text-sky-300" },
    { label: "EM Low", value: expectedMoveLower, color: "bg-teal-900/45", textColor: "text-teal-200" },
    { label: "Put Wall 2", value: secondaryPutWall, color: "bg-rose-900/35", textColor: "text-rose-200" },
    { label: "Put Wall", value: putWall, color: "bg-rose-900/60", textColor: "text-rose-300" },
  ];

  // Filter nulls then sort descending (highest price at top) and remove duplicate prices
  const levels = rawLevels
    .filter((l) => l.value !== null)
    .sort((a, b) => (b.value as number) - (a.value as number));

  const dedupedLevels = useMemo(() => {
    const seen = new Set<string>();
    const out: Level[] = [];
    for (const lvl of levels) {
      const key = `${(lvl.value as number).toFixed(4)}:${lvl.isSpot ? "spot" : "regular"}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(lvl);
    }
    return out;
  }, [levels]);

  if (dedupedLevels.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Key Levels Ladder</h2>
        <p className="text-sm text-zinc-500">No level data available.</p>
      </div>
    );
  }

  const min = dedupedLevels[dedupedLevels.length - 1].value as number;
  const max = dedupedLevels[0].value as number;
  const range = max - min || 1;

  async function saveAlertRule(levelLabel: string, levelValue: number) {
    setSavingLevel(levelLabel);
    const ruleName = makeRuleName(levelLabel);
    try {
      const res = await fetch("/api/options-live/v3/publish/event-rule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          channel: "alerts",
          ruleName,
          mode: "full",
          cron: `proximity<=${alertBandPct}%@${levelValue}`,
        }),
      });
      if (res.ok) {
        setActiveRuleNames((prev) => {
          const next = new Set(prev);
          next.add(ruleName);
          return next;
        });
      }
    } finally {
      setSavingLevel(null);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-200">Key Levels Ladder</h2>
        <div className="flex items-center gap-2 text-xs">
          {expectedMoveWidth !== null && (
            <span className="rounded border border-teal-800/60 bg-teal-950/30 px-2 py-0.5 text-teal-300">
              EM ±{expectedMoveWidth.toFixed(2)}
            </span>
          )}
          <span className="text-zinc-500">Alert band %</span>
          <input
            value={alertBandPct}
            onChange={(e) => setAlertBandPct(e.target.value)}
            className="h-7 w-16 rounded border border-zinc-700 bg-zinc-900 px-2 text-zinc-200"
          />
        </div>
      </div>
      <div className="relative">
        {/* Rail line */}
        <div className="absolute left-[7.5rem] top-0 bottom-0 w-px bg-zinc-700" />

        <div className="space-y-1">
          {dedupedLevels.map((lvl, idx) => {
            const posPct = ((lvl.value as number) - min) / range; // 0=bottom, 1=top
            const distLabel =
              spot && !lvl.isSpot ? ` (${pct(lvl.value as number, spot)})` : "";

            const ruleName = makeRuleName(lvl.label);
            const isRuleSet = activeRuleNames.has(ruleName);

            // Connectors between levels
            const nextLvl = dedupedLevels[idx + 1];
            const gap = nextLvl
              ? ((lvl.value as number) - (nextLvl.value as number)) / range
              : null;

            return (
              <React.Fragment key={lvl.label}>
                <button
                  type="button"
                  onClick={() => {
                    if (lvl.value != null) onSelectLevel?.(lvl.value);
                  }}
                  className={`flex items-center gap-3 rounded-lg px-3 py-1.5 ${
                    lvl.isSpot || selectedLevel === lvl.value ? "ring-1 ring-emerald-500/50" : ""
                  } ${lvl.color}`}
                >
                  {/* Label area */}
                  <span
                    className={`w-28 shrink-0 text-right text-xs font-medium ${lvl.textColor}`}
                  >
                    {lvl.label}
                  </span>

                  {/* Dot on rail */}
                  <div className="relative flex h-4 w-4 shrink-0 items-center justify-center">
                    <div
                      className={`h-2.5 w-2.5 rounded-full ${
                        lvl.isSpot ? "bg-emerald-400 ring-2 ring-emerald-400/30" : "bg-zinc-500"
                      }`}
                    />
                  </div>

                  {/* Value */}
                  <span className="font-mono text-sm text-zinc-100">
                    {lvl.value?.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>

                  {/* Distance from spot */}
                  {distLabel ? (
                    <span className="ml-auto text-xs text-zinc-400">{distLabel}</span>
                  ) : null}
                  {!lvl.isSpot && lvl.value != null && (
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        void saveAlertRule(lvl.label, lvl.value as number);
                      }}
                      className={`rounded border px-2 py-0.5 text-[10px] ${
                        isRuleSet
                          ? "border-emerald-700/70 bg-emerald-950/40 text-emerald-300"
                          : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
                      }`}
                    >
                      {savingLevel === lvl.label ? "Saving…" : isRuleSet ? "Alert Set" : "Set Alert"}
                    </span>
                  )}
                </button>

                {/* Gap bar between levels */}
                {gap !== null && gap > 0.03 && (
                  <div className="ml-[8.25rem] h-px border-t border-dashed border-zinc-800 my-0.5 opacity-50" />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
