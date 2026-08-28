# 🏛️ Mickey & Austin Wargaming & Reengineering System — Architecture & PRD

**Version:** 1.3 (Master Architecture with Verified Google Drive & NotebookLM Cloud IDs)  
**Status:** Approved for Implementation  
**Owner:** Quantitative Systems & Trading Architecture Team  
**Key References:** [daily_profiler_wargaming.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/profiler/daily_profiler_wargaming.md), [mickey_austin_master_methodology.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/profiler/mickey_austin_master_methodology.md), [wargaming_playlists.json](file:///c:/Users/vinay/tvDownloadOHLC/scripts/config/wargaming_playlists.json)

---

## 1. Verified Google Drive Vault Hierarchy

All transcripts, daily reports, and audio metadata are synced to your Google Drive account (`vinay.veerappa@gmail.com`) under:

| Folder Name | Google Drive ID | Direct URL | Purpose |
| :--- | :--- | :--- | :--- |
| **`Trading/PackVideos`** (Root) | `1yS14ZHL80G2yD3LbLjrsYEYMMQgBQNY1` | [Open Folder](https://drive.google.com/drive/folders/1yS14ZHL80G2yD3LbLjrsYEYMMQgBQNY1) | Master Cloud Vault |
| **`Wargaming`** | `1QlXsVisXx_p8W8hkE5nH6rEkWBt_t4yM` | [Open Folder](https://drive.google.com/drive/folders/1QlXsVisXx_p8W8hkE5nH6rEkWBt_t4yM) | Pre-Market Morning Transcripts |
| **`Reengineering`** | `1GWalYFmkxOsz0ZJOsVpok-VAMYTS6lfM` | [Open Folder](https://drive.google.com/drive/folders/1GWalYFmkxOsz0ZJOsVpok-VAMYTS6lfM) | EOD Post-Mortem Sessions |
| **`Bootcamp`** | `1UPUFw9OHHGu7EfHOtEa5W4b86c8v02d1` | [Open Folder](https://drive.google.com/drive/folders/1UPUFw9OHHGu7EfHOtEa5W4b86c8v02d1) | Classroom / Bootcamp Archives |
| **`DailyReports`** | `1DpoWwSg4sbEMrfotOID5-gLrdalYTFMJ` | [Open Folder](https://drive.google.com/drive/folders/1DpoWwSg4sbEMrfotOID5-gLrdalYTFMJ) | Standalone `.html` Charts & `.md` |

---

## 2. Google NotebookLM Master Knowledge Base Registry

| Notebook Title | Notebook ID | Sources | Web Link |
| :--- | :--- | :--- | :--- |
| **Pack Trading - Live Wargaming YouTube Transcripts** | `79bec20c-caf4-4271-8348-9426141103e1` | 68 sources | [Open Notebook](https://notebooklm.google.com/notebook/79bec20c-caf4-4271-8348-9426141103e1) |
| **Pack Trading Reengineering Q2 2026** | `ef6358af-5096-4427-87fd-93ed015416c6` | 52 sources | [Open Notebook](https://notebooklm.google.com/notebook/ef6358af-5096-4427-87fd-93ed015416c6) |
| **Pack Oct Bootcamp** | `1689f881-6486-4b05-9fd4-f3a3d7f4af31` | 72 sources | [Open Notebook](https://notebooklm.google.com/notebook/1689f881-6486-4b05-9fd4-f3a3d7f4af31) |
| **TCM Notes** | `34ff4525-621a-441c-adf2-1d665996099a` | 279 sources | [Open Notebook](https://notebooklm.google.com/notebook/34ff4525-621a-441c-adf2-1d665996099a) |
| **0930 All Day ORB Data Analysis** | `d86e9c4d-5645-47b2-9ccb-29bd58fdfc22` | 257 sources | [Open Notebook](https://notebooklm.google.com/notebook/d86e9c4d-5645-47b2-9ccb-29bd58fdfc22) |
| **0-5 Box Strategy** | `f95ef291-d156-4119-aab1-e4d73c86efeb` | 11 sources | [Open Notebook](https://notebooklm.google.com/notebook/f95ef291-d156-4119-aab1-e4d73c86efeb) |
| **C1 C2 C3 Candle Pattern Analysis** | `77f2f1d0-d367-4523-8175-50d596a1d33b` | 11 sources | [Open Notebook](https://notebooklm.google.com/notebook/77f2f1d0-d367-4523-8175-50d596a1d33b) |

---

## 3. Auditable 3-Way Cloud-Local Synchronization

```
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │                         DATA SYNCHRONIZATION & TRANSCRIPT LAYER                         │
  │                                                                                         │
  │   Google NotebookLM Cloud                              Google Drive Cloud Vault         │
  │   • Live Wargaming (68 sources)              ◄───►     • My Drive/Trading/PackVideos/   │
  │   • Reengineering (52 sources)                         • Wargaming/ & Reengineering/   │
  │                                                                                         │
  │                                            ▲                                            │
  │                                            │                                            │
  │                                2-Way Sync Engine (MCP & API)                            │
  │                                            │                                            │
  │                                            ▼                                            │
  │                               Local Auditable Storage                                   │
  │                               • data/wargaming/transcripts/raw/                         │
  │                               • data/wargaming/db/mickey_ground_truth.sqlite            │
  └────────────────────────────────────────────┬────────────────────────────────────────────┘
                                               │
                                               ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │                           PRE-MARKET & EOD EXECUTION ENGINES                            │
  │                                                                                         │
  │   [06:00 / 08:30 Pre-Market]                           [16:00 EOD Reengineering]        │
  │   • generate_daily_wargame.py                          • reconcile_wargame.py           │
  │   • P12 High/Mid/Low Directional Switch                • 3-Way Drift Comparator         │
  │   • Candle Science Target Boxes (P30-P70)              • AI vs Mickey vs Tape Actuals   │
  │   • Pack Trading Brackets (+10 bps Queen)              • DPO / SFT Dataset Generator    │
  └────────────────────────────────────────────┬────────────────────────────────────────────┘
                                               │
                                               ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │                             OUTPUT & DISPATCH LAYER                                     │
  │   • Discord Webhook Embeds (🔴 Red False / 🟢 Green True)                               │
  │   • Responsive Dark-Mode HTML Email Templates                                           │
  │   • Interactive Standalone HTML Candlestick Charts (Lightweight Charts)                 │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Universal Basis Points (bps) Standards

| Ticker | Instrument Name | Tick Size | Point Value | Momentum Filter (10 bps) | Cover The Queen (+10 bps) | Runner (+30 bps) | Stop Ceiling (12 bps) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NQ1** | Nasdaq 100 E-mini | 0.25 | $20.00 | ~29.60 pts | **+29.60 pts** | **+88.80 pts** | 35.50 pts |
| **ES1** | S&P 500 E-mini | 0.25 | $50.00 | ~7.74 pts | **+7.74 pts** | **+23.20 pts** | 9.30 pts |
| **YM1** | Dow Jones E-mini | 1.00 | $5.00 | ~53.70 pts | **+53.70 pts** | **+161.00 pts** | 64.40 pts |
| **RTY1** | Russell 2000 E-mini | 0.10 | $50.00 | ~3.02 pts | **+3.02 pts** | **+9.06 pts** | 3.60 pts |
| **GC1** | Gold Futures | 0.10 | $100.00 | ~4.66 pts | **+4.66 pts** | **+13.98 pts** | 5.60 pts |
| **CL1** | Crude Oil Futures | 0.01 | $1,000.00 | ~0.08 pts | **+0.08 pts** | **+0.25 pts** | 0.10 pts |
