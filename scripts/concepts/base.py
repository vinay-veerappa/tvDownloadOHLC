"""Base Concept Provider Interface

Every trading concept (Candle Science, HTF Macro, Weekly Outlook, P12 Scenarios,
NQStats ALN, etc.) inherits from BaseConceptProvider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

STATUS_PRODUCTION = "production"
STATUS_SCAFFOLD = "scaffold"
STATUS_EXPERIMENTAL = "experimental"


@dataclass
class ChartOverlays:
    """Overlays to inject into Lightweight Charts renderer."""
    price_lines: List[Dict[str, Any]] = field(default_factory=list) # [{name, price, color, style, prob, tier}]
    target_boxes: List[Dict[str, Any]] = field(default_factory=list) # [{label, start_ts, end_ts, top, bottom, color}]
    badges: List[Dict[str, Any]] = field(default_factory=list) # [{text, bg_color, text_color}]
    hud_rows: List[Dict[str, Any]] = field(default_factory=list) # [{label, value, color}]


@dataclass
class ConceptPayload:
    """Standard payload returned by every Concept Provider."""
    name: str
    ticker: str
    target_date: str
    spot_price: float
    data: Dict[str, Any]
    markdown_report: str
    status: str = STATUS_PRODUCTION
    is_success: bool = True
    error_message: Optional[str] = None
    overlays: ChartOverlays = field(default_factory=ChartOverlays)


class BaseConceptProvider(ABC):
    """Abstract Base Class for all analytical trading concepts."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique concept identifier (e.g. 'candle_science', 'aln_sessions')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief human-readable description of what this concept computes."""
        pass

    @property
    def status(self) -> str:
        """Lifecycle status: 'production', 'scaffold', or 'experimental'."""
        return STATUS_PRODUCTION

    @property
    def version(self) -> str:
        """Provider version (semver)."""
        return "1.0.0"

    @property
    def is_production(self) -> bool:
        """Helper to verify if provider is ready for live production wargaming."""
        return self.status == STATUS_PRODUCTION

    @abstractmethod
    def compute(
        self,
        ticker: str = "NQ1",
        target_date: Optional[str] = None,
        cutoff_time: str = "08:45",
        context: Optional[Dict[str, Any]] = None
    ) -> ConceptPayload:
        """Execute the concept's mathematical / statistical analysis."""
        pass

    @abstractmethod
    def format_markdown(self, data: Dict[str, Any]) -> str:
        """Format the concept's results into a clean, standalone GitHub markdown report."""
        pass

    def get_chart_overlays(self, payload: Dict[str, Any]) -> ChartOverlays:
        """Extract chart lines, target boxes, or badges for visual rendering."""
        return ChartOverlays()
