"use client";

import React from "react";

type State = "loading" | "error" | "empty" | "degraded";

type Props = {
  state: State;
  moduleName?: string;
  message?: string;
  warnings?: string[];
};

export function ModuleEmptyBanner({ state, moduleName, message, warnings = [] }: Props) {
  if (state === "loading") {
    return (
      <div className="flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950 py-12">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-400" />
          <span className="text-sm text-zinc-500">
            {moduleName ? `Loading ${moduleName}…` : "Loading…"}
          </span>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="rounded-xl border border-rose-900/70 bg-rose-950/20 p-6">
        <div className="flex items-start gap-3">
          <span className="text-xl">⚠</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-rose-300">
              {moduleName ? `${moduleName} failed to load` : "Module load error"}
            </p>
            {message && (
              <p className="mt-1 break-all font-mono text-xs text-rose-400">{message}</p>
            )}
            <p className="mt-2 text-xs text-rose-500">
              Data may be stale. Refresh the page or check the pipeline logs.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (state === "degraded") {
    return (
      <div className="rounded-xl border border-amber-900/60 bg-amber-950/10 p-4">
        <div className="flex items-start gap-3">
          <span className="text-base">⚡</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-amber-300">
              {moduleName ? `${moduleName} — partial data` : "Partial data"}
            </p>
            {warnings.length > 0 && (
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-amber-400">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    );
  }

  // empty
  return (
    <div className="flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950 py-12">
      <div className="flex flex-col items-center gap-2">
        <span className="text-2xl text-zinc-700">—</span>
        <span className="text-sm text-zinc-500">
          {message ?? (moduleName ? `No ${moduleName} data available` : "No data available")}
        </span>
      </div>
    </div>
  );
}
