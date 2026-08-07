"""Historical day replay harness for KB narrative + confluence.

Phase B implementation from docs/architecture/KB_NARRATIVE_REPLAY_ROADMAP.md.

Usage:
    python -m scripts.knowledge_bridge.historical_replay --date 2026-07-16 --ticker ES1

Outputs are written to:
    logs/replay/{date}_{ticker}/
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pytz

from scripts.knowledge_bridge.confluence_engine import ConfluenceEngine
from scripts.knowledge_bridge.kb_context import fetch_kb_context
from scripts.libs_py.risk.narrative import insert_risk_params
from scripts.trader.briefing_core import REPO_ROOT, build_premarket_context, get_dataloader
from scripts.trader.trader_narrative import DEFAULT_MODEL, call_ollama, load_prompt_template
from scripts.utils.fused_data_loader import load_fused_data

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

ET = pytz.timezone("America/New_York")


def _to_jsonable(value: Any) -> Any:
    """Best-effort conversion for JSON serialization."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _micro_instrument(ticker: str) -> str:
    mapping = {"NQ1": "MNQ", "ES1": "MES"}
    return mapping.get(ticker.upper(), ticker.upper())


def _load_session_1m_csv(ticker: str, target_date: date, output_path: Path) -> int:
    """Write session 1m bars (RTH 09:30-16:00 ET) for replay day."""
    df = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df is None or df.empty:
        output_path.write_text("", encoding="utf-8")
        return 0

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(ET)
    else:
        df.index = df.index.tz_convert(ET)

    day_df = df[df.index.date == target_date]
    if day_df.empty:
        output_path.write_text("", encoding="utf-8")
        return 0

    start = ET.localize(datetime.combine(target_date, time(9, 30)))
    end = ET.localize(datetime.combine(target_date, time(16, 0)))
    session_df = day_df[(day_df.index >= start) & (day_df.index <= end)].copy()

    if session_df.empty:
        output_path.write_text("", encoding="utf-8")
        return 0

    session_df = session_df.reset_index()
    first_col = session_df.columns[0]
    session_df = session_df.rename(columns={first_col: "timestamp_et"})
    session_df["timestamp_et"] = session_df["timestamp_et"].astype(str)
    session_df.to_csv(output_path, index=False)
    return len(session_df)


def run_historical_replay(
    target_date: date,
    ticker: str,
    *,
    model: str,
    kb_api_url: str,
    with_llm: bool,
) -> dict[str, Any]:
    """Run one historical day replay and persist all artifacts."""
    run_id = f"{target_date.isoformat()}_{ticker}"
    output_dir = REPO_ROOT / "logs" / "replay" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_dt = ET.localize(datetime.combine(target_date, time(9, 30)))
    loader = get_dataloader(lookback_days=5)

    # 1) Build premarket cheat sheet for the historical day.
    cheat_sheet = build_premarket_context(loader=loader, nq_ticker=ticker, target_date=target_date)
    (output_dir / "cheatsheet.txt").write_text(cheat_sheet, encoding="utf-8")
    log.info("Saved cheat sheet (%d chars)", len(cheat_sheet))

    # 2) Retrieve KB context separately for replay traceability.
    kb_context = fetch_kb_context(cheat_sheet, kb_api_url=kb_api_url)
    (output_dir / "kb_context.txt").write_text(kb_context, encoding="utf-8")
    if kb_context:
        log.info("Saved KB context (%d chars)", len(kb_context))
    else:
        log.info("KB context empty (API unreachable or no matches)")

    # 3) Confluence run in historical mode.
    engine = ConfluenceEngine(kb_api_url=kb_api_url)
    confluence = engine.run(ticker=ticker, target_date=target_date, now_et=sim_dt)
    confluence_dict = confluence.to_dict()
    (output_dir / "confluence.json").write_text(
        json.dumps(_to_jsonable(confluence_dict), indent=2), encoding="utf-8"
    )
    (output_dir / "trade_plan.json").write_text(
        json.dumps(_to_jsonable(confluence_dict.get("trade_plan")), indent=2), encoding="utf-8"
    )
    log.info("Saved confluence output and trade plan")

    # 4) LLM narrative from KB-aware premarket prompt.
    prompt_template = load_prompt_template("premarket")
    final_cheat_sheet = cheat_sheet
    if kb_context and "# ICT KNOWLEDGE BASE CONTEXT" not in cheat_sheet:
        final_cheat_sheet = cheat_sheet + "\n\n" + kb_context

    prompt = prompt_template.replace("{{INSERT_CHEAT_SHEET}}", final_cheat_sheet)
    prompt = insert_risk_params(prompt, instruments=[_micro_instrument(ticker)])

    if with_llm:
        narrative = call_ollama(prompt, model)
    else:
        narrative = (
            "LLM generation skipped (--no-llm).\n\n"
            "This replay still produced cheat sheet, KB context, confluence, trade plan, and session bars."
        )
    (output_dir / "narrative.md").write_text(narrative, encoding="utf-8")
    log.info("Saved narrative (%d chars)", len(narrative))

    # 5) Save 1m bars for the replay date.
    bars_count = _load_session_1m_csv(ticker, target_date, output_dir / "session_1m.csv")
    log.info("Saved session_1m.csv (%d rows)", bars_count)

    replay_meta = {
        "run_id": run_id,
        "ticker": ticker,
        "target_date": target_date.isoformat(),
        "sim_dt_et": sim_dt.isoformat(),
        "model": model,
        "with_llm": with_llm,
        "kb_api_url": kb_api_url,
        "kb_context_chars": len(kb_context),
        "cheat_sheet_chars": len(cheat_sheet),
        "narrative_chars": len(narrative),
        "session_bars": bars_count,
        "limitations": [
            "Historical replay skips live GEX signal (no dated historical GEX snapshots yet).",
            "Historical ICT features require dated files in data/derived; missing dates are skipped gracefully.",
            "Calendar/news context may not be fully historical for all providers.",
        ],
        "confluence_summary": confluence.summary(),
        "output_dir": str(output_dir),
    }
    (output_dir / "replay_meta.json").write_text(
        json.dumps(_to_jsonable(replay_meta), indent=2), encoding="utf-8"
    )

    return replay_meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Historical day replay harness (Phase B).")
    parser.add_argument("--date", required=True, help="Replay date YYYY-MM-DD")
    parser.add_argument("--ticker", default="ES1", help="Ticker symbol (default ES1)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM model for narrative")
    parser.add_argument("--kb-url", default="http://127.0.0.1:8900", help="KB API URL")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM call and save deterministic artifacts only")
    args = parser.parse_args()

    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    ticker = args.ticker.upper()
    short_map = {"NQ": "NQ1", "ES": "ES1", "YM": "YM1", "RTY": "RTY1"}
    ticker = short_map.get(ticker, ticker)

    meta = run_historical_replay(
        target_date=target_date,
        ticker=ticker,
        model=args.model,
        kb_api_url=args.kb_url,
        with_llm=not args.no_llm,
    )

    print("\n" + "=" * 70)
    print("HISTORICAL REPLAY COMPLETE")
    print("=" * 70)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
