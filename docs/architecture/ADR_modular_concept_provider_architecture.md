# ADR: Modular Trading Concept Provider Architecture & Unified Brain System

## 1. Context & Motivation
Trading decisions require synthesizing multiple distinct analytical disciplines (Candle Science, HTF Macro, Weekly Candle Cycles, P12 Vectors, Volatility DRO Budgets, Signature Setups, ALN Line Netting, Herman Probabilities, Expected Moves, and GEX).

Previously, adding a new analytical concept required modifying multiple monolithic scripts (`generate_daily_wargame.py`, `render_wargame_chart.py`, etc.), resulting in tight coupling, lack of independent testability, and context clutter for AI subagents.

## 2. Decision: The Modular Concept Provider Architecture
We establish a decentralized, plugin-based Concept Provider Architecture:

1. **`BaseConceptProvider` Abstract Contract**:
   Every concept implements:
   - `name`: Unique identifier (`candle_science`, `htf_macro`, `aln_levels`, `herman_probabilities`, etc.).
   - `compute(ticker, target_date, cutoff_time, context) -> ConceptPayload`: Deterministic analytical computation.
   - `format_markdown(payload) -> str`: Independent standalone markdown report.
   - `get_chart_overlays(payload) -> ChartOverlays`: Visual price lines, target boxes, trajectories, or HUD badges.
   - `get_skill_definition() -> SkillMetadata`: Metadata for dedicated AI agent skills.

2. **Central Concept Registry (`ConceptRegistry`)**:
   - Auto-discovers and registers all concept providers in `scripts/concepts/`.
   - Allows running any concept independently via CLI:
     ```bash
     python -m scripts.concepts.runner --concept aln --ticker NQ1
     ```
   - Allows running the unified master synthesis:
     ```bash
     python -m scripts.concepts.runner --all --ticker NQ1
     ```

3. **Unified 4-Layer Trading Second Brain**:
   - **Layer 1: Standalone Concept Engines (`scripts/concepts/`)**: Pure executable Python engines.
   - **Layer 2: Domain Reference Documentation (`docs/<domain>/`)**: Deep methodology manuals.
   - **Layer 3: Persistent Memory & Graph (`SQLite DB`, `NotebookLM`, `codebase-memory-mcp`)**: Shared cross-session knowledge and transcripts.
   - **Layer 4: Master Confluence Synthesizer**: Blends all active concept outputs into the Master Wargame Playbook, Lightweight Charts visualizer, and Next.js Platform.

## 3. Benefits & Extensibility
- **Zero-Friction Addition of New Concepts**: Adding ALN, Herman, or any future concept only requires creating `scripts/concepts/<concept_name>.py` and `docs/<concept_name>/`.
- **Independent Testing**: Every concept has its own unit tests and standalone CLI.
- **AI Agent Skill Autonomy**: AI subagents can load and execute individual concepts with minimal token overhead.
