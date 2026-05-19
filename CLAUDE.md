# tvDownloadOHLC Project Guidelines

## Core Commands
* **Start Next.js App**: `cd web && npm run dev`
* **Prisma Schema Update**: `cd web && npx prisma db push`
* **FastAPI Backend**: `start_api.bat`
* **Ollama LLM Server**: `start_llm.bat`
* **Run Options Levels**: `.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels`

## Workspace Context Anchors (Inspect ONLY when required)
* **Architectural Decisions**: [ADR.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ADR.md) (Timezones, normalization, vectorized models)
* **Trading Domain Rules**: [SecondBrain_Trading.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/SecondBrain_Trading.md) (ALN sessions, NQ personalities, IB probabilities)
* **Visual Compliance Standard**: [VISUAL_SYSTEM.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md) (Theme palette, scaling, label registry)
* **Options Infrastructure Inventory**: [OPTIONS_INVENTORY.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/OPTIONS_INVENTORY.md) (Schwab auth, Greeks engine, level scorer)
* **Database Schema Reference**: [PRISMA_DATABASE_SCHEMA.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/PRISMA_DATABASE_SCHEMA.md) (SQLite schema catalog)

## Development Workflow & Guardrails
* **Zero-Loop Constraint (ADR-017)**: All Python data engineering and trading strategies must use fully vectorized NumPy/Pandas models. No `for` loops in calculation paths.
* **Visual Compliance Constraint (ADR-018)**: Indicators must bind to shared templates in `VISUAL_SYSTEM.md`. Zero direct low-level drawing API calls.
* **Timezone Standard (ADR-001)**: Charts take UTC naive inputs; calculations use ET (New York) session windows; storage uses UTC Unix Epoch.
* **Statistical Normalization Standard (ADR-002)**: Performance/statistical metrics must be calculated and reported as price percentage gains/excursions, not absolute points.
* **Strict Context Window Rule**: Never read full files unless necessary. Always utilize line-specific views (`StartLine` & `EndLine` parameters) to load only target blocks (limit to 30–50 lines per turn) to optimize token consumption.
