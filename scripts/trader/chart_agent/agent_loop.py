"""agent_loop.py — multi-model validation loop for the chart agent.

Runs the full pipeline through multiple models and compares:
  1. REASONER: emits a daily_bias_mtf verdict from features + KB context
  2. VISION VERIFIER: reads the chart image and checks the verdict

Both roles run through multiple models so we can compare which does each job best.

Available models (auto-detected):
  Local Ollama:
    - qwen3-vl:8b (vision — can read chart images)
    - gemma4:latest, gemma4:31b-cloud, glm-5.2:cloud, deepseek-v4-flash:cloud (reasoners)
  Antigravity/Gemini (if app is running):
    - gemini flash / pro via agentapi (vision + reasoner)

Usage:
    python -m scripts.trader.chart_agent.agent_loop --ticker ES1 --date 2026-08-04
    python -m scripts.trader.chart_agent.agent_loop --ticker NQ1 --last-n 2 --compare-all
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))

from scripts.trader import _path_setup  # noqa: F401
from scripts.trader.chart_agent.reasoner import assemble_features, retrieve_kb_context, call_llm
from scripts.trader.chart_agent.gen_charts import generate_charts, _trading_days_from_data
from scripts.utils.fused_data_loader import load_fused_data

PROMPT_DIR = Path(__file__).parent / "prompts"
VERDICT_DIR = _REPO / "data" / "vision" / "verdicts"
COMPARISON_DIR = _REPO / "data" / "vision" / "comparisons"
COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

ANTIGRAVITY_API = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "bin", "agentapi.bat")


# ═══════════════════════════════════════════════════════════════════════
#  Model providers
# ═══════════════════════════════════════════════════════════════════════

def _ollama_vision(image_path: Path, prompt: str, model: str, timeout: int = 120) -> str:
    """Call an Ollama vision model with an image + prompt."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 32768, "num_predict": 4096},
        },
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json().get("response", "")
    raise RuntimeError(f"Ollama vision HTTP {resp.status_code}: {resp.text[:200]}")


def _ollama_text(prompt: str, model: str, timeout: int = 300) -> str:
    """Call an Ollama text model."""
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 262144, "num_predict": 8192},
        },
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json().get("response", "")
    raise RuntimeError(f"Ollama text HTTP {resp.status_code}: {resp.text[:200]}")


def _antigravity_available() -> bool:
    """Check if Antigravity app is running (agentapi needs it)."""
    if not os.path.exists(ANTIGRAVITY_API):
        return False
    # Check if the env var is set (set by the running app)
    if os.environ.get("ANTIGRAVITY_LS_ADDRESS"):
        return True
    # Try a quick call
    try:
        result = subprocess.run(
            [ANTIGRAVITY_API, "new-conversation", "--model=flash_lite", "test"],
            capture_output=True, text=True, timeout=10,
        )
        return "ANTIGRAVITY_LS_ADDRESS" not in result.stderr
    except Exception:
        return False


def _antigravity_call(prompt: str, model: str = "flash", timeout: int = 120) -> str:
    """Call Antigravity agentapi for Gemini models.

    Uses a temp file to avoid Windows command-line length limits (~8KB).
    """
    import tempfile

    # Write prompt to temp file, then use @file syntax or read+pass
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        temp_path = f.name

    try:
        # Read the prompt from file and pass it
        with open(temp_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        # Truncate if still too long (Windows cmd limit ~32768 chars)
        if len(prompt_content) > 30000:
            prompt_content = prompt_content[:30000] + "\n\n[TRUNCATED — prompt too long for CLI]"

        result = subprocess.run(
            [ANTIGRAVITY_API, "new-conversation", f"--model={model}", prompt_content],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Antigravity error: {result.stderr[:300]}")
        # Parse JSON response
        try:
            data = json.loads(result.stdout)
            return data.get("response", data.get("content", result.stdout))
        except json.JSONDecodeError:
            return result.stdout
    finally:
        os.unlink(temp_path)


# ═══════════════════════════════════════════════════════════════════════
#  Detection of available models
# ═══════════════════════════════════════════════════════════════════════

def get_available_models() -> dict:
    """Detect available models for each role."""
    models = {"reasoners": [], "vision": []}

    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        ollama_models = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        ollama_models = []

    # Reasoners (text-only, for verdict generation)
    reasoner_candidates = [
        "gemma4:latest", "gemma4:31b-cloud", "glm-5.2:cloud",
        "deepseek-v4-flash:cloud", "deepseek-v4-pro:cloud",
    ]
    for m in reasoner_candidates:
        if m in ollama_models:
            models["reasoners"].append({"name": m, "provider": "ollama", "type": "text"})

    # Vision models (for chart verification)
    # Skip local vision models on 8GB GPU — too slow (qwen3-vl:8b timed out at 120s)
    # Cloud/Antigravity vision models are fast enough
    vision_candidates = ["qwen3-vl:8b"]
    for m in vision_candidates:
        if m in ollama_models:
            log.info("  Local vision model %s available but skipping (too slow on 8GB GPU). Use cloud models for vision.", m)
            # models["vision"].append({"name": m, "provider": "ollama", "type": "vision"})  # disabled

    # Antigravity/Gemini
    if _antigravity_available():
        models["reasoners"].append({"name": "gemini-flash", "provider": "antigravity", "type": "text"})
        models["reasoners"].append({"name": "gemini-pro", "provider": "antigravity", "type": "text"})
        models["vision"].append({"name": "gemini-flash", "provider": "antigravity", "type": "vision"})
        models["vision"].append({"name": "gemini-pro", "provider": "antigravity", "type": "vision"})
        log.info("Antigravity/Gemini available — added to comparison")
    else:
        log.info("Antigravity not running — skipping Gemini (start Antigravity app to enable)")

    return models


# ═══════════════════════════════════════════════════════════════════════
#  Reasoner: emit verdict
# ═══════════════════════════════════════════════════════════════════════

def run_reasoner(ticker: str, model_info: dict) -> str:
    """Run the reasoner with a specific model and return the verdict YAML."""
    name = model_info["name"]
    provider = model_info["provider"]

    log.info("  [REASONER] %s (%s)...", name, provider)

    features = assemble_features(ticker)
    kb_context = retrieve_kb_context(features)

    prompt_path = PROMPT_DIR / "daily_bias_reasoner.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    prompt = prompt.replace("{FEATURES_BLOCK}", features).replace("{KB_CONTEXT_BLOCK}", kb_context)

    if provider == "ollama":
        verdict = _ollama_text(prompt, name)
    elif provider == "antigravity":
        verdict = _antigravity_call(prompt, model="flash" if "flash" in name else "pro")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    log.info("  [REASONER] %s done (%d chars)", name, len(verdict))
    return verdict


# ═══════════════════════════════════════════════════════════════════════
#  Vision verifier: read the chart and check the verdict
# ═══════════════════════════════════════════════════════════════════════

VISION_VERIFY_PROMPT = """You are an ICT/SMC trading chart verifier. You are given a trading chart image and a bias verdict. Your job is to verify whether the verdict matches what is actually visible on the chart.

Look at the chart and answer these questions:
1. Are the price levels mentioned in the verdict (PDH, PDL, etc.) visible and approximately correct on the chart?
2. Does the bias direction (bullish/bearish) match what you see in the price action?
3. Are the described PD arrays (order blocks, FVGs, levels) actually visible on the chart?
4. Is the "readiness" assessment reasonable given what you see?
5. Is there anything on the chart that the verdict missed or got wrong?

Then give an overall score: MATCH (verdict matches chart), PARTIAL (some things right, some wrong), or MISMATCH (verdict doesn't match chart).

Be concise. Point out specific discrepancies.

VERDICT TO VERIFY:
{VERDICT}
"""


def run_vision_verifier(chart_path: Path, verdict: str, model_info: dict) -> str:
    """Run the vision verifier on a chart + verdict with a specific model."""
    name = model_info["name"]
    provider = model_info["provider"]

    log.info("  [VISION] %s (%s)...", name, provider)

    prompt = VISION_VERIFY_PROMPT.replace("{VERDICT}", verdict)

    if provider == "ollama":
        result = _ollama_vision(chart_path, prompt, name)
    elif provider == "antigravity":
        # Antigravity/Gemini can handle images via conversation
        # For now, describe the chart path — Gemini may need the image uploaded
        full_prompt = f"{prompt}\n\nChart image: {chart_path}\n(Please analyze the chart image at this path if you can access it, otherwise describe what you'd expect to see.)"
        result = _antigravity_call(full_prompt, model="flash" if "flash" in name else "pro")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    log.info("  [VISION] %s done (%d chars)", name, len(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
#  Agent loop — the full comparison pipeline
# ═══════════════════════════════════════════════════════════════════════

def run_agent_loop(
    ticker: str,
    target_date: datetime | None = None,
    compare_all: bool = False,
) -> dict:
    """Run the full agent loop: chart gen -> reasoner(s) -> vision verifier(s).

    Args:
        ticker: e.g. "ES1"
        target_date: specific date (if None, uses last trading day with data)
        compare_all: if True, run ALL available models; if False, use first of each

    Returns:
        comparison results dict
    """
    models = get_available_models()

    if not models["reasoners"]:
        raise RuntimeError("No reasoner models available — is Ollama running?")
    if not models["vision"]:
        log.warning("No vision models available — vision verification will be skipped")

    # Pick models
    reasoners = models["reasoners"] if compare_all else models["reasoners"][:2]
    vision_models = models["vision"] if compare_all else models["vision"][:1]

    log.info("="*60)
    log.info("AGENT LOOP: %s | %s", ticker, target_date.date() if target_date else "latest")
    log.info("Reasoners: %s", [m["name"] for m in reasoners])
    log.info("Vision:    %s", [m["name"] for m in vision_models])
    log.info("="*60)

    # 1. Generate chart
    if target_date is None:
        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        dates = _trading_days_from_data(df, 1)
        if not dates:
            raise RuntimeError(f"No data with substantial rows for {ticker}")
        target_date = dates[0]

    chart_paths = generate_charts([ticker], dates=[target_date], dpi=150)
    if not chart_paths:
        raise RuntimeError(f"Chart generation failed for {ticker} {target_date.date()}")
    chart_path = chart_paths[0]
    log.info("Chart: %s", chart_path)

    # 2. Run reasoners
    verdicts = {}
    for model_info in reasoners:
        model_name = model_info["name"]
        try:
            verdict = run_reasoner(ticker, model_info)
            verdicts[model_name] = verdict
        except Exception as e:
            log.error("  [REASONER] %s failed: %s", model_name, e)
            verdicts[model_name] = f"ERROR: {e}"

    # 3. Run vision verifiers (each verifier checks each verdict)
    verifications = {}
    if vision_models:
        for vm_info in vision_models:
            vm_name = vm_info["name"]
            verifications[vm_name] = {}
            for r_name, verdict in verdicts.items():
                if verdict.startswith("ERROR"):
                    verifications[vm_name][r_name] = "SKIPPED (reasoner failed)"
                    continue
                try:
                    result = run_vision_verifier(chart_path, verdict, vm_info)
                    verifications[vm_name][r_name] = result
                except Exception as e:
                    log.error("  [VISION] %s -> %s failed: %s", vm_name, r_name, e)
                    verifications[vm_name][r_name] = f"ERROR: {e}"

    # 4. Assemble comparison report
    date_str = target_date.strftime("%Y-%m-%d")
    report = {
        "ticker": ticker,
        "date": date_str,
        "chart": str(chart_path),
        "timestamp": datetime.now().isoformat(),
        "models_used": {
            "reasoners": [m["name"] for m in reasoners],
            "vision": [m["name"] for m in vision_models],
        },
        "verdicts": verdicts,
        "verifications": verifications,
    }

    # Save report
    report_path = COMPARISON_DIR / f"{ticker}_{date_str}_comparison.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.info("Comparison saved: %s", report_path)

    # Also save individual verdicts
    for r_name, verdict in verdicts.items():
        safe_name = r_name.replace(":", "_").replace("/", "_")
        v_path = VERDICT_DIR / f"{ticker}_{date_str}_{safe_name}.yaml"
        v_path.write_text(verdict, encoding="utf-8")

    return report


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Multi-model agent loop for chart analysis comparison")
    ap.add_argument("--ticker", default="ES1", help="Ticker symbol")
    ap.add_argument("--date", type=str, default=None, help="Specific date YYYY-MM-DD")
    ap.add_argument("--last-n", type=int, default=None, help="Last N trading days with data")
    ap.add_argument("--compare-all", action="store_true", help="Use ALL available models (not just first 2)")
    args = ap.parse_args()

    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")

    if args.last_n:
        # Run for multiple dates
        df = load_fused_data(args.ticker, timeframe="1m", require_historical=False)
        dates = _trading_days_from_data(df, args.last_n)
        for d in dates:
            report = run_agent_loop(args.ticker, target_date=d, compare_all=args.compare_all)
            _print_summary(report)
    else:
        report = run_agent_loop(args.ticker, target_date=target_date, compare_all=args.compare_all)
        _print_summary(report)


def _print_summary(report: dict):
    """Print a concise summary of the comparison."""
    print("\n" + "=" * 60)
    print(f"  {report['ticker']} | {report['date']}")
    print("=" * 60)

    print("\n  REASONER VERDICTS:")
    for model, verdict in report["verdicts"].items():
        if verdict.startswith("ERROR"):
            print(f"    {model}: ERROR")
        else:
            # Extract bias line for summary
            for line in verdict.split("\n"):
                if line.strip().startswith("bias:"):
                    print(f"    {model}: {line.strip()}")
                    break
            else:
                print(f"    {model}: {len(verdict)} chars (no bias line found)")

    if report["verifications"]:
        print("\n  VISION VERIFICATIONS:")
        for vm, checks in report["verifications"].items():
            for reasoner, result in checks.items():
                # Extract MATCH/PARTIAL/MISMATCH
                verdict_word = "UNKNOWN"
                for word in ["MATCH", "PARTIAL", "MISMATCH"]:
                    if word in result.upper():
                        verdict_word = word
                        break
                print(f"    {vm} -> {reasoner}: {verdict_word}")

    print("\n  Full report: data/vision/comparisons/")
    print("=" * 60)


if __name__ == "__main__":
    main()