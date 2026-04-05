"use client";

import React, { useState, useCallback } from "react";

const CHANNELS = [
  { id: "test_channel", label: "Test Channel", desc: "Safe test destination" },
  { id: "option-levels", label: "#option-levels", desc: "Daily levels broadcast" },
  { id: "alerts", label: "#alerts", desc: "Active signal alerts" },
  { id: "macro-alerts", label: "#macro-alerts", desc: "Macro / regime alerts" },
];

type PreviewEmbed = {
  title: string;
  description: string;
  fields: Array<{ name: string; value: string; inline: boolean }>;
  footer: string;
};

type PreviewData = {
  text: string;
  embed: PreviewEmbed;
  mode: string;
  previewToken?: string;
};

type SendStatus =
  | { state: "idle" }
  | { state: "sending" }
  | { state: "sent"; message: string; dryRun: boolean }
  | { state: "error"; message: string };

type Props = {
  symbol: string;
  isOpen: boolean;
  onClose: () => void;
};

export function DiscordPublishDrawer({ symbol, isOpen, onClose }: Props) {
  const [channel, setChannel] = useState("test_channel");
  const [dryRun, setDryRun] = useState(true);
  const [publishMode, setPublishMode] = useState<"spot" | "full" | "heatmap-pack">("spot");
  const [triggerMode, setTriggerMode] = useState<"manual" | "scheduled" | "event">("manual");
  const [scheduleCron, setScheduleCron] = useState("0 9 * * 1-5");
  const [eventRuleName, setEventRuleName] = useState("");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<SendStatus>({ state: "idle" });

  const fetchPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    try {
      const res = await fetch("/api/options-live/v3/publish/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, mode: publishMode === "heatmap-pack" ? "full" : publishMode }),
      });
      const json = await res.json();
      if (!res.ok) {
        setPreviewError(json?.meta?.message ?? `Preview failed (${res.status})`);
        return;
      }
      setPreview(json?.data ?? null);
    } catch (err: unknown) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [symbol, publishMode]);

  const handleSaveRule = useCallback(async () => {
    const ruleName = eventRuleName.trim() || `${symbol}-${triggerMode}-${channel}`;
    setSendStatus({ state: "sending" });
    try {
      const res = await fetch("/api/options-live/v3/publish/event-rule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          channel,
          ruleName,
          mode: publishMode === "heatmap-pack" ? "full" : publishMode,
          cron: scheduleCron,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setSendStatus({ state: "error", message: json?.meta?.message ?? `HTTP ${res.status}` });
        return;
      }
      setSendStatus({ state: "sent", message: `Rule saved: ${ruleName}`, dryRun: false });
    } catch (err: unknown) {
      setSendStatus({ state: "error", message: err instanceof Error ? err.message : "Rule save failed" });
    }
  }, [eventRuleName, symbol, triggerMode, channel, publishMode, scheduleCron]);

  const handleSend = useCallback(async () => {
    setSendStatus({ state: "sending" });
    const idempotencyKey = `${symbol}-${channel}-${Date.now()}`;
    try {
      const res = await fetch("/api/options-live/v3/publish/discord", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          channel,
          idempotencyKey,
          dryRun,
          previewToken: preview?.previewToken ?? "",
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setSendStatus({ state: "error", message: json?.meta?.message ?? `HTTP ${res.status}` });
        return;
      }
      const msg = json?.data?.message ?? json?.data?.status ?? "Sent.";
      setSendStatus({ state: "sent", message: msg, dryRun });
    } catch (err: unknown) {
      setSendStatus({ state: "error", message: err instanceof Error ? err.message : "Send failed" });
    }
  }, [symbol, channel, dryRun, preview]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-950 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Discord Publish</h2>
            <p className="text-xs text-zinc-400">{symbol} — send GEX update to Discord</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">Publish Scope</p>
              <select
                value={publishMode}
                onChange={(e) => setPublishMode(e.target.value as "spot" | "full" | "heatmap-pack")}
                className="h-9 w-full rounded border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-200"
              >
                <option value="spot">Active Chart Only</option>
                <option value="full">Full Tab Summary</option>
                <option value="heatmap-pack">Multi-Chart Pack</option>
              </select>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">Trigger</p>
              <select
                value={triggerMode}
                onChange={(e) => setTriggerMode(e.target.value as "manual" | "scheduled" | "event")}
                className="h-9 w-full rounded border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-200"
              >
                <option value="manual">Manual Publish</option>
                <option value="scheduled">Scheduled Interval</option>
                <option value="event">Event Driven</option>
              </select>
            </div>
          </div>

          {triggerMode !== "manual" && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Automation Rule</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  value={eventRuleName}
                  onChange={(e) => setEventRuleName(e.target.value)}
                  placeholder="Rule name"
                  className="h-9 rounded border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-200"
                />
                <input
                  value={scheduleCron}
                  onChange={(e) => setScheduleCron(e.target.value)}
                  placeholder="Cron (e.g. 0 9 * * 1-5)"
                  className="h-9 rounded border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-200"
                />
              </div>
              <button
                onClick={handleSaveRule}
                className="rounded border border-indigo-700 bg-indigo-900/40 px-3 py-1.5 text-xs font-semibold text-indigo-300 hover:bg-indigo-900/60"
              >
                Save Automation Rule
              </button>
            </div>
          )}

          {/* Channel selector */}
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">Channel</p>
            <div className="grid grid-cols-2 gap-2">
              {CHANNELS.map((ch) => (
                <button
                  key={ch.id}
                  onClick={() => setChannel(ch.id)}
                  className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                    channel === ch.id
                      ? "border-emerald-700 bg-emerald-900/30 text-emerald-300"
                      : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800"
                  }`}
                >
                  <p className="text-sm font-medium">{ch.label}</p>
                  <p className="text-xs text-zinc-500">{ch.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Dry run toggle */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2">
            <div>
              <p className="text-sm text-zinc-200">Dry Run</p>
              <p className="text-xs text-zinc-500">Simulate send without posting to Discord</p>
            </div>
            <button
              onClick={() => setDryRun((v) => !v)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                dryRun ? "bg-amber-600" : "bg-emerald-700"
              }`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  dryRun ? "left-0.5" : "left-5"
                }`}
              />
            </button>
          </div>

          {/* Preview section */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Preview</p>
              <button
                onClick={fetchPreview}
                disabled={previewLoading}
                className="rounded px-2.5 py-1 text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors disabled:opacity-50"
              >
                {previewLoading ? "Loading…" : "Load Preview"}
              </button>
            </div>

            {previewError && (
              <p className="rounded-lg border border-rose-900/70 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">
                {previewError}
              </p>
            )}

            {preview && (
              <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 space-y-2">
                <div className="text-sm font-semibold text-indigo-300 border-l-4 border-indigo-500 pl-2">
                  {preview.embed.title}
                </div>
                <p className="text-xs text-zinc-300 whitespace-pre-wrap">{preview.embed.description}</p>
                {preview.embed.fields.length > 0 && (
                  <div className="grid grid-cols-2 gap-1 pt-1">
                    {preview.embed.fields.map((f, idx) => (
                      <div key={idx} className="rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1">
                        <p className="text-xs font-medium text-zinc-400">{f.name}</p>
                        <p className="text-xs text-zinc-200">{f.value}</p>
                      </div>
                    ))}
                  </div>
                )}
                {preview.embed.footer && (
                  <p className="text-xs text-zinc-500 pt-1">{preview.embed.footer}</p>
                )}
              </div>
            )}
          </div>

          {/* Send status */}
          {sendStatus.state === "sent" && (
            <div className={`rounded-lg border px-3 py-2 text-sm ${
              sendStatus.dryRun
                ? "border-amber-800 bg-amber-950/30 text-amber-300"
                : "border-emerald-800 bg-emerald-950/30 text-emerald-300"
            }`}>
              {sendStatus.dryRun ? "📋 Dry run — " : "✓ Sent — "}
              {sendStatus.message}
            </div>
          )}
          {sendStatus.state === "error" && (
            <div className="rounded-lg border border-rose-800 bg-rose-950/30 px-3 py-2 text-sm text-rose-300">
              ✗ {sendStatus.message}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            <button
              onClick={handleSend}
              disabled={sendStatus.state === "sending" || triggerMode !== "manual"}
              className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-colors ${
                dryRun
                  ? "bg-amber-700 hover:bg-amber-600 text-white disabled:opacity-50"
                  : "bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50"
              }`}
            >
              {triggerMode !== "manual"
                ? "Use Save Automation Rule"
                : sendStatus.state === "sending"
                ? "Sending…"
                : dryRun
                ? "Dry Run Send"
                : `Send to ${CHANNELS.find((c) => c.id === channel)?.label ?? channel}`}
            </button>
            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
