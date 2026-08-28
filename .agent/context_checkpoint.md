# Context Checkpoint: Mickey & Austin Wargaming, Google Drive Cloud Sync & 3-Way Reconciler
*Timestamp: 2026-08-28T12:39:30-07:00*

## 1. Executive Summary
Successfully designed, implemented, verified, and committed the multi-ticker **Pre-Market Wargaming & EOD Reengineering System** with automated Google Drive cloud backup, NotebookLM synchronization, isolated 3-bank SQLite databases (`mickey_ground_truth.sqlite`, `system_wargames.sqlite`, `market_actuals.sqlite`), an interactive Lightweight Charts HTML renderer, a multi-channel dispatcher (Discord & Email), and a 3-way daily drift reconciler with DPO preference generation.

---

## 2. Key Files & State

### Core Execution Engines
- [`scripts/wargaming/generate_daily_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/generate_daily_wargame.py): Multi-ticker CLI engine generating canonical 6-section wargaming playbooks with P12 directional switches, Candle Science target boxes, and Pack Trading brackets (+10 bps Queen / +30 bps Runner) for `NQ1`, `ES1`, `CL1`, `GC1`, `YM1`, `RTY1`. Auto-saves predictions to `system_wargames.sqlite`.
- [`scripts/wargaming/wargame_db.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/wargame_db.py): Isolated 3-bank SQLite database manager (`mickey_ground_truth.sqlite`, `system_wargames.sqlite`, `market_actuals.sqlite`).
- [`scripts/wargaming/gdrive_sync.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/gdrive_sync.py): Google Drive v3 REST API synchronizer for `My Drive/Trading/PackVideos/` (`Wargaming`, `Reengineering`, `Bootcamp`, `DailyReports`).
- [`scripts/wargaming/youtube_wargame_miner.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/youtube_wargame_miner.py): Scrapes spoken transcripts from active YouTube playlists and pushes them to Google Drive + SQLite.
- [`scripts/wargaming/standardize_and_sync_all_wargames.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/standardize_and_sync_all_wargames.py): Enforces canonical date-based naming `YYYY-MM-DD_{stream_type}_{clean_topic}.txt` across local, Drive, and DB.
- [`scripts/wargaming/render_wargame_chart.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/render_wargame_chart.py): Self-contained single-file HTML reports with TradingView Lightweight Charts, session boxes, P12 rays, target boxes, and execution brackets.
- [`scripts/wargaming/dispatch_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/dispatch_wargame.py): Formats structured Discord embed cards and HTML email templates with interactive chart attachments.
- [`scripts/wargaming/reconcile_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/reconcile_wargame.py): Post-market 16:15 EST 3-way drift comparator (`[AI Prediction]` vs `[Mickey Ground Truth]` vs `[Realized Tape Actuals]`), evaluating the 4-Step Reversal Counter and writing DPO training pairs (`data/wargaming/training/dpo_preference_pairs.jsonl`).

### Configuration & Documentation
- [`scripts/config/wargaming_playlists.json`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/config/wargaming_playlists.json): Registry of Google Drive folder IDs, active YouTube playlists (`PLNsd-wh14sP4`, `PLNfg4GdZd0J-bHFVZRHwD23wP5BM8npwz`), and NotebookLM notebooks.
- [`docs/architecture/WARGAMING_SYSTEM_PRD_AND_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/WARGAMING_SYSTEM_PRD_AND_ARCHITECTURE.md): Master PRD & Architecture specification (v1.3).
- [`.agent/skills/pack_wargaming/SKILL.md`](file:///c:/Users/vinay/tvDownloadOHLC/.agent/skills/pack_wargaming/SKILL.md): Antigravity Skill.
- [`.agents/AGENTS.md`](file:///c:/Users/vinay/tvDownloadOHLC/.agents/AGENTS.md): Repository rule enforcing the 6-section format and banning EOD day-type prediction in morning wargames.

---

## 3. Verified Cloud & Local IDs

### Google Drive Vault (`vinay.veerappa@gmail.com`)
- Root: `1yS14ZHL80G2yD3LbLjrsYEYMMQgBQNY1` (`My Drive/Trading/PackVideos`)
- Wargaming: `1QlXsVisXx_p8W8hkE5nH6rEkWBt_t4yM`
- Reengineering: `1GWalYFmkxOsz0ZJOsVpok-VAMYTS6lfM`
- Bootcamp: `1UPUFw9OHHGu7EfHOtEa5W4b86c8v02d1`
- DailyReports: `1DpoWwSg4sbEMrfotOID5-gLrdalYTFMJ`

### NotebookLM Master Notebooks
- Live Wargaming (68 sources): `79bec20c-caf4-4271-8348-9426141103e1`
- Reengineering Q2/Q3 2026 (52+ sources): `ef6358af-5096-4427-87fd-93ed015416c6`

---

## 4. Critical Invariants & Rules
1. **Never Predict EOD Day Types in the Morning**: R1, R2, DNP, and DWP are 16:00 EST post-mortem diagnostic classifications. Morning objectives focus strictly on If-Then Scenario Cards (True Continuation vs. False Reversion) with 09:45 and 10:15 statistical cutoffs.
2. **Universal Basis Points (bps) Standard**: All risk stops, excursion metrics, and profit targets are strictly calibrated in basis points (1 bps = 0.01%). Target 1 ("Cover The Queen") is +10.0 bps (50% scale-out + breakeven lock). Target 2 ("Runner") is +30.0 bps. Stop Ceiling is max 12.0 bps.
3. **Date-Based Naming Standard**: All transcripts are named `YYYY-MM-DD_{stream_type}_{clean_topic}.txt`.
4. **Isolated 3-Bank Database Rule**: Never mix pre-market AI predictions with Mickey expert ground truth or mechanical tape actuals.

---

## 5. Next Actions
1. Execute daily morning wargames (`python scripts/wargaming/generate_daily_wargame.py --ticker NQ1 --html`) before 08:30 EST.
2. Run daily post-market drift reconciliation (`python scripts/wargaming/reconcile_wargame.py --ticker NQ1`) after 16:15 EST.
3. Automatically fine-tune the local LoRA model on accumulated DPO pairs in `data/wargaming/training/dpo_preference_pairs.jsonl`.
