# tvDownloadOHLC - Trading Platform

## 📂 Project Structure

*   **`web/`**: **[NEW]** The main Next.js Trading Platform (Chart, Journal, Backtest).
    *   Stack: Next.js 14, TypeScript, Shadcn/UI, Prisma, Lightweight Charts.
    *   Run: `cd web && npm run dev`
*   **`data/`**: Historical OHLC data (Parquet/CSV).
*   **`scripts/`**: Python scripts for data downloading and processing.
*   **`legacy_chart_ui/`**: **[DEPRECATED]** The original Vanilla JS Chart Viewer. Kept for reference.

## 🚀 Getting Started (New Platform)

1.  Navigate to the web app:
    ```bash
    cd web
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```
4.  Open [http://localhost:3000](http://localhost:3000)

## 🐍 Data Scripts (Python)

To run data processing scripts:
```bash
python scripts/process_data.py
```
