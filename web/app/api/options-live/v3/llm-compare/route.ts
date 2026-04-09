import { NextRequest } from "next/server";
import { buildLevels, buildNarrative, buildSummary } from "@/lib/options-live-v3/adapters";
import { ok, readStringParam, readSymbol, serverError } from "@/lib/options-live-v3/http";

const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";
const DEFAULT_MODEL_PREFERENCE = ["gemma4:26b", "qwen3:latest", "mistral:latest", "llama3.2:latest"];

type CompareCard = {
  model: string;
  provider: "system" | "ollama";
  output: string;
  latencyMs?: number;
  error?: string | null;
};

function buildDeterministicBaseline(input: {
  symbol: string;
  spot: number | null;
  regime: string | null;
  directionalBias: string | null;
  gammaFlip: number | null;
  callWall: number | null;
  putWall: number | null;
  expectedMoveWidth: number | null;
  coach: string[];
  tactical: string[];
  perspectives: Array<{ mode: string; scope: string; bias: string; tacticalScore?: number }>;
}): string {
  const fmt = (v: number | null | undefined, digits = 2) =>
    typeof v === "number" && Number.isFinite(v)
      ? v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
      : "-";

  const lines = [
    `- ${input.symbol} spot ${fmt(input.spot)} with ${input.regime ?? "unknown"} regime and ${input.directionalBias ?? "neutral"} directional bias.`,
    `- Gamma flip ${fmt(input.gammaFlip)}, call wall ${fmt(input.callWall)}, put wall ${fmt(input.putWall)}${input.expectedMoveWidth !== null ? `, expected move ±${fmt(input.expectedMoveWidth)}` : ""}.`,
    input.perspectives.length > 0
      ? `- Best current lens: ${input.perspectives.map((p) => `${p.mode}/${p.scope.toUpperCase()} ${p.bias}${typeof p.tacticalScore === "number" ? ` (${p.tacticalScore}/100)` : ""}`).join(" | ")}.`
      : "- Multi-timeframe tactical view is unavailable.",
    `- Current system guidance: ${[...input.coach.slice(0, 2), ...input.tactical.slice(0, 2)].join(" ") || "No narrative guidance available."}`,
  ];
  return lines.join("\n");
}

function buildPrompt(input: {
  symbol: string;
  expiryScope: string;
  summary: Awaited<ReturnType<typeof buildSummary>>["data"];
  levels: Awaited<ReturnType<typeof buildLevels>>["data"];
  narrative: Awaited<ReturnType<typeof buildNarrative>>["data"];
}): string {
  const context = {
    symbol: input.symbol,
    expiryScope: input.expiryScope,
    spot: input.summary.spot,
    totalGex: input.summary.gex.total,
    regime: input.summary.gex.regimeLabel ?? input.summary.gex.regime,
    directionalBias: input.summary.gex.directionalBias,
    levels: input.levels.levels,
    integrityTier: input.narrative.integrityTier,
    dataSourceLabel: input.narrative.dataSourceLabel,
    screener: input.narrative.screener,
    signals: input.narrative.signals,
    perspectives: input.narrative.perspectives ?? [],
   // coachNotes: input.narrative.notes?.coach ?? input.levels.notes.coach,
    tacticalNotes: input.narrative.notes?.tactical ?? input.levels.notes.tactical,
  };

  return [
    "You are an intraday options-flow trading assistant for the tvDownloadOHLC options-live-v3 dashboard.",
    "Use the provided market context only. Do not invent data.",
    "Prioritize day-trading usefulness over explanation.",
    "Return as bullet points:",
    "1. Bias and regime in plain trader language",
    "2. Key levels and what matters first intraday",
    "3. Which timeframe lens matters most right now (Scalper, Intraday, or Swing) and why",
    "4. Tactical guidance with invalidation or caution",
    "Keep the whole answer under 200 words. No intro, no disclaimer, no markdown headings.",
    "",
    JSON.stringify(context, null, 2),
  ].join("\n");
}

async function listOllamaModels(): Promise<string[]> {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/tags`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = (await res.json()) as { models?: Array<{ name?: string }> };
    return (data.models ?? []).map((m) => m.name).filter((name): name is string => Boolean(name));
  } catch {
    return [];
  }
}

async function runOllamaCompare(model: string, prompt: string): Promise<CompareCard> {
  const started = Date.now();
  try {
    const res = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        stream: false,
        messages: [
          {
            role: "system",
            content:
              "You are a concise institutional trading coach. Be concrete, level-aware, and execution-focused.",
          },
          { role: "user", content: prompt },
        ],
      }),
    });

    if (!res.ok) {
      return { model, provider: "ollama", output: "", latencyMs: Date.now() - started, error: `HTTP ${res.status}` };
    }

    const data = (await res.json()) as { message?: { content?: string } };
    return {
      model,
      provider: "ollama",
      output: data.message?.content?.trim() || "",
      latencyMs: Date.now() - started,
      error: null,
    };
  } catch (error) {
    return {
      model,
      provider: "ollama",
      output: "",
      latencyMs: Date.now() - started,
      error: String(error),
    };
  }
}

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  const expiryScope = readStringParam(req, "expiryScope", "all");
  const requestedModels = readStringParam(req, "models", DEFAULT_MODEL_PREFERENCE.join(","))
    .split(",")
    .map((model) => model.trim())
    .filter(Boolean);

  try {
    const [summaryResult, levelsResult, narrativeResult, availableModels] = await Promise.all([
      buildSummary(symbol),
      buildLevels(symbol),
      buildNarrative(symbol, expiryScope),
      listOllamaModels(),
    ]);

    const selectedModels = requestedModels.filter((model) => availableModels.includes(model)).slice(0, 3);
    const prompt = buildPrompt({
      symbol,
      expiryScope,
      summary: summaryResult.data,
      levels: levelsResult.data,
      narrative: narrativeResult.data,
    });

    const warnings = [
      ...summaryResult.warnings,
      ...levelsResult.warnings,
      ...narrativeResult.warnings,
    ];

    const baseline = buildDeterministicBaseline({
      symbol,
      spot: summaryResult.data.spot,
      regime: summaryResult.data.gex.regimeLabel,
      directionalBias: summaryResult.data.gex.directionalBias,
      gammaFlip: levelsResult.data.levels.gammaFlip,
      callWall: levelsResult.data.levels.callWall,
      putWall: levelsResult.data.levels.putWall,
      expectedMoveWidth: levelsResult.data.levels.expectedMoveWidth ?? null,
      coach: narrativeResult.data.notes?.coach ?? levelsResult.data.notes.coach,
      tactical: narrativeResult.data.notes?.tactical ?? levelsResult.data.notes.tactical,
      perspectives: (narrativeResult.data.perspectives ?? []).map((row) => ({
        mode: row.mode,
        scope: row.scope,
        bias: row.bias,
        tacticalScore: row.tacticalScore,
      })),
    });

    if (selectedModels.length === 0) {
      warnings.push("No requested Ollama models are currently installed; showing baseline only.");
    }

    const comparisons = await Promise.all(selectedModels.map((model) => runOllamaCompare(model, prompt)));

    return ok(
      {
        implemented: true,
        module: "llm-compare",
        symbol,
        expiryScope,
        baseline: {
          model: "current-system",
          provider: "system",
          output: baseline,
          error: null,
        },
        comparisons,
        availableModels,
      },
      symbol,
      warnings
    );
  } catch (error) {
    return serverError(`Failed to compare LLM outputs: ${String(error)}`, symbol);
  }
}