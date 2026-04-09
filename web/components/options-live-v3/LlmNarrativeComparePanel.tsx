"use client";

import React, { useEffect, useState } from "react";

type CompareResponse = {
  success: boolean;
  data?: {
    baseline: {
      model: string;
      provider: "system";
      output: string;
      error?: string | null;
    };
    comparisons: Array<{
      model: string;
      provider: "ollama";
      output: string;
      latencyMs?: number;
      error?: string | null;
    }>;
    availableModels: string[];
  };
  warnings?: string[];
  error?: string | null;
};

type Props = {
  symbol: string;
  expiryScope: string;
};

export function LlmNarrativeComparePanel({ symbol, expiryScope }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CompareResponse | null>(null);

  useEffect(() => {
    setResponse(null);
    setError(null);
  }, [symbol, expiryScope]);

  async function loadComparison() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/options-live/v3/llm-compare?symbol=${encodeURIComponent(symbol)}&expiryScope=${encodeURIComponent(expiryScope)}`, {
        cache: "no-store",
      });
      const data = (await res.json()) as CompareResponse;
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to load LLM comparison");
      }
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const cards = response?.data ? [response.data.baseline, ...response.data.comparisons] : [];

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">Local LLM Narrative Compare</h3>
          <p className="text-xs text-zinc-500">Compare the current deterministic output with local Ollama models before promoting any model-generated narrative.</p>
        </div>
        <button
          onClick={loadComparison}
          disabled={loading}
          className="rounded-lg border border-indigo-700 bg-indigo-900/40 px-3 py-1.5 text-sm font-medium text-indigo-300 transition-colors hover:bg-indigo-900/70 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Comparing..." : response ? "Refresh Compare" : "Run Compare"}
        </button>
      </div>

      {!response && !loading && !error && (
        <p className="text-sm text-zinc-400">Runs Gemma4 plus the installed fallback local models and shows their trader-facing narrative beside the current system output.</p>
      )}

      {error && (
        <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      {response?.warnings && response.warnings.length > 0 && (
        <div className="mb-3 rounded-lg border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
          {response.warnings.join(" ")}
        </div>
      )}

      {cards.length > 0 && (
        <div className="grid gap-3 xl:grid-cols-2">
          {cards.map((card) => (
            <div key={card.model} className="rounded-lg border border-zinc-800 bg-black p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${card.provider === "system" ? "border-zinc-700 bg-zinc-900 text-zinc-300" : "border-emerald-700/60 bg-emerald-900/20 text-emerald-300"}`}>
                    {card.provider === "system" ? "Current" : "Ollama"}
                  </span>
                  <span className="text-sm font-medium text-zinc-100">{card.model}</span>
                </div>
                {('latencyMs' in card) && typeof card.latencyMs === "number" && (
                  <span className="text-[11px] text-zinc-500">{(card.latencyMs / 1000).toFixed(1)}s</span>
                )}
              </div>
              {card.error ? (
                <p className="text-sm text-rose-300">{card.error}</p>
              ) : (
                <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-zinc-300">{card.output}</pre>
              )}
            </div>
          ))}
        </div>
      )}

      {response?.data?.availableModels && response.data.availableModels.length > 0 && (
        <p className="mt-3 text-xs text-zinc-500">Installed local models: {response.data.availableModels.join(", ")}</p>
      )}
    </div>
  );
}