"""
testing_framework — Extensible validation framework for WebUI features.

This package provides a generic framework to validate WebUI backend computations
against local reference computations. Each WebUI feature (profiler, candle-science,
etc.) gets its own module that implements the FeatureValidator protocol.

Architecture:
    testing_framework/
        __init__.py          — Package exports
        core/
            __init__.py
            base.py          — FeatureValidator protocol, ValidationResult
            filter_engine.py — Generic pivot-table filter engine
            api_client.py    — Base WebUI API client
            comparator.py    — Field-by-field comparison engine
            reporter.py      — Markdown/JSON report formatting
        features/
            __init__.py
            profiler/
                __init__.py
                data.py      — Profiler data loading
                compute.py   — Local profiler stats computation
                api.py       — Profiler WebUI API calls
                validator.py — ProfilerFeatureValidator
        run.py               — Main CLI runner
"""

from __future__ import annotations
