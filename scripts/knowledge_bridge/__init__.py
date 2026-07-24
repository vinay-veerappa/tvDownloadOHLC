"""Knowledge Bridge — Phase 3 strategy candidate registry.

Bridges KB setup units (prose descriptions of ICT trading setups) to
executable detection functions in ``ict_engine`` and strategy classes
in ``trading_framework``.

Modules
-------
detection_catalog
    Prose → function mapping for all ICT detection functions.
strategy_candidates
    ``StrategyCandidate`` dataclass + LLM-assisted candidate generation
    from KB setup units.
candidate_export
    JSON export + bidirectional linking (candidate ↔ source units).
"""

from .detection_catalog import (
    DETECTION_CATALOG,
    DetectionEntry,
    resolve_detection,
    list_concepts,
    concepts_by_category,
    search_concepts,
)
from .strategy_candidates import (
    StrategyCandidate,
    CandidateStatus,
    CandidateGenerator,
    DetectionStep,
    generate_candidates,
)
from .candidate_export import (
    export_candidates_json,
    load_candidates_json,
    link_candidates_to_units,
    compute_unit_updates,
    filter_by_status,
    filter_by_strategy_key,
    filter_by_session,
    summary_stats,
)
from .backtest_loop import (
    BacktestLoop,
    BacktestResult,
    ProfileResult,
    run_candidate_backtest,
    export_backtest_results,
    load_backtest_results,
    apply_backtest_results,
    summarize_results,
)
from .kb_context import (
    DEFAULT_KB_API_URL,
    CONCEPT_TRIGGERS,
    check_kb_api,
    detect_concepts,
    fetch_kb_context,
)
from .confluence_engine import (
    ConfluenceEngine,
    ConfluenceResult,
    ConfluenceSignal,
    TradePlan,
    LiveContext,
    DEFAULT_PROVIDERS,
    DEFAULT_DOMAIN_WEIGHTS,
)

__version__ = "0.4.0"