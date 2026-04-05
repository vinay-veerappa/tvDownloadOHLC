"use client";

import React, { useCallback, useEffect, useState } from "react";

type AlertRule = {
  ruleName: string;
  symbol: string;
  cron: string;
  mode: string;
  channel: string;
  updatedAt: string;
};

type Props = {
  symbol: string;
};

export function AlertRulesPanel({ symbol }: Props) {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingRule, setDeletingRule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/options-live/v3/publish/event-rule?symbol=${encodeURIComponent(symbol)}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as { data?: { rules?: AlertRule[] } };
      setRules(json?.data?.rules ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  const deleteRule = useCallback(
    async (ruleName: string) => {
      setDeletingRule(ruleName);
      try {
        const res = await fetch(
          `/api/options-live/v3/publish/event-rule?ruleName=${encodeURIComponent(ruleName)}`,
          { method: "DELETE" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setRules((prev) => prev.filter((r) => r.ruleName !== ruleName));
      } catch {
        // silently swallow — rule list will be refreshed
      } finally {
        setDeletingRule(null);
      }
    },
    []
  );

  const symbolRules = rules.filter((r) => r.symbol === symbol);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Alert Rules</h3>
        <button
          onClick={() => void fetchRules()}
          disabled={loading}
          className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && (
        <p className="mb-2 text-xs text-rose-400">{error}</p>
      )}

      {!loading && symbolRules.length === 0 ? (
        <p className="text-xs text-zinc-500">No alert rules for {symbol}. Use "Set Alert" on a level above.</p>
      ) : (
        <div className="space-y-1.5">
          {symbolRules.map((rule) => (
            <div
              key={rule.ruleName}
              className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-zinc-200">{rule.ruleName}</p>
                <p className="mt-0.5 truncate text-zinc-500">
                  <span className="text-zinc-400">{rule.channel}</span>
                  {" · "}
                  <code className="font-mono text-[10px] text-indigo-300">{rule.cron}</code>
                  {" · "}
                  <span className="text-zinc-500">
                    {rule.updatedAt ? new Date(rule.updatedAt).toLocaleString() : "—"}
                  </span>
                </p>
              </div>
              <button
                onClick={() => void deleteRule(rule.ruleName)}
                disabled={deletingRule === rule.ruleName}
                className="shrink-0 rounded border border-rose-900/60 bg-rose-950/30 px-2 py-1 text-rose-400 hover:bg-rose-950/60 disabled:opacity-40"
              >
                {deletingRule === rule.ruleName ? "…" : "Delete"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
