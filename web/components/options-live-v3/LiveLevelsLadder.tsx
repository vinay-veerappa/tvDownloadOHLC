"use client";

import React from "react";

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
  putWall: number | null;
  gammaMagnet: number | null;
  pinStrike: number | null;
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
  putWall,
  gammaMagnet,
  pinStrike,
}: Props) {
  // Build sorted level list
  const rawLevels: Level[] = [
    { label: "Call Wall", value: callWall, color: "bg-emerald-900/60", textColor: "text-emerald-300" },
    { label: "Gamma Flip", value: gammaFlip, color: "bg-violet-900/60", textColor: "text-violet-300" },
    { label: "Spot", value: spot, color: "bg-zinc-700", textColor: "text-zinc-100", isSpot: true },
    { label: "Γ Magnet", value: gammaMagnet, color: "bg-amber-900/60", textColor: "text-amber-300" },
    { label: "Pin Strike", value: pinStrike, color: "bg-sky-900/60", textColor: "text-sky-300" },
    { label: "Put Wall", value: putWall, color: "bg-rose-900/60", textColor: "text-rose-300" },
  ];

  // Filter nulls then sort descending (highest price at top)
  const levels = rawLevels
    .filter((l) => l.value !== null)
    .sort((a, b) => (b.value as number) - (a.value as number));

  if (levels.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">Key Levels Ladder</h2>
        <p className="text-sm text-zinc-500">No level data available.</p>
      </div>
    );
  }

  const min = levels[levels.length - 1].value as number;
  const max = levels[0].value as number;
  const range = max - min || 1;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <h2 className="mb-3 text-sm font-semibold text-zinc-200">Key Levels Ladder</h2>
      <div className="relative">
        {/* Rail line */}
        <div className="absolute left-[7.5rem] top-0 bottom-0 w-px bg-zinc-700" />

        <div className="space-y-1">
          {levels.map((lvl, idx) => {
            const posPct = ((lvl.value as number) - min) / range; // 0=bottom, 1=top
            const distLabel =
              spot && !lvl.isSpot ? ` (${pct(lvl.value as number, spot)})` : "";

            // Connectors between levels
            const nextLvl = levels[idx + 1];
            const gap = nextLvl
              ? ((lvl.value as number) - (nextLvl.value as number)) / range
              : null;

            return (
              <React.Fragment key={lvl.label}>
                <div
                  className={`flex items-center gap-3 rounded-lg px-3 py-1.5 ${
                    lvl.isSpot ? "ring-1 ring-emerald-500/50" : ""
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
                </div>

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
