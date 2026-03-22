# STARTUP GUIDE: Schwab Unified Hub

To run the system correctly, you must start the **Hub (Producer)** first, followed by any **Spokes (Consumers)**.

## 1. Start the Hub (Producer)
This process manages authentication and rate-limiting. It must be running for any other script to work.
```powershell
python scripts/streaming/schwab_hub.py
```
*Wait for: `✅ Producer Ready. Listening on 127.0.0.1:8000`*

## 2. Start the Spokes (Consumers)
In separate terminal windows, you can now start your specialized data processors:

### A. Charting & L1 Data
```powershell
python scripts/streaming/stream_chart.py
```

### B. L2 Bookmap Engine (mHVN Detection)
```powershell
python scripts/streaming/l2_processor_engine.py
```

## 3. Launch the Dashboard
To see the real-time Heatmap and GEX data:
```powershell
cd web
npm run dev
```
Navigate to: `http://localhost:3000/options-live` and select the **Bookmap** tab.

---

## 🔍 Verification
- **Hub Console**: Should show incoming Schwab events (L1, L2).
- **Spoke Consoles**: Should show `✅ Connected to Hub`.
- **Dashboard**: The orange "Bookmap" tab should start populating with the liquidity heatmap.
