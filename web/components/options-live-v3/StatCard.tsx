import React from "react";

type StatCardProps = {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "negative";
  subValue?: string;
};

export function StatCard({ label, value, tone = "neutral", subValue }: StatCardProps) {
  const toneClass =
    tone === "positive"
      ? "text-emerald-400"
      : tone === "negative"
      ? "text-rose-400"
      : "text-zinc-100";

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${toneClass}`}>{value}</div>
      {subValue ? <div className="mt-1 text-xs text-zinc-400">{subValue}</div> : null}
    </div>
  );
}
