"""Concept Provider Central Registry

Discovers, registers, and executes trading concepts across the repository.
Enforces production vs. scaffold lifecycle boundaries and explicit failure surfacing.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from scripts.concepts.base import BaseConceptProvider, ConceptPayload, STATUS_PRODUCTION, STATUS_SCAFFOLD

log = logging.getLogger(__name__)


class ConceptRegistry:
    """Central registry for all analytical trading concept providers."""

    _registry: Dict[str, BaseConceptProvider] = {}

    @classmethod
    def register(cls, provider: BaseConceptProvider) -> None:
        """Register a concept provider instance."""
        cls._registry[provider.name] = provider
        log.info(f"Registered concept provider: {provider.name} [{provider.status.upper()}] (v{provider.version})")

    @classmethod
    def get(cls, name: str) -> Optional[BaseConceptProvider]:
        """Retrieve a registered provider by name."""
        return cls._registry.get(name)

    @classmethod
    def list_concepts(cls, include_scaffolds: bool = True) -> List[Dict[str, Any]]:
        """List all registered concepts with their descriptions, version, and lifecycle status."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "version": p.version,
                "is_production": p.is_production,
            }
            for p in cls._registry.values()
            if include_scaffolds or p.is_production
        ]

    @classmethod
    def execute_concept(
        cls,
        name: str,
        ticker: str = "NQ1",
        target_date: Optional[str] = None,
        cutoff_time: str = "08:45",
        context: Optional[Dict[str, Any]] = None
    ) -> ConceptPayload:
        """Execute a single concept by name."""
        provider = cls.get(name)
        if not provider:
            raise ValueError(f"Concept '{name}' is not registered. Available: {list(cls._registry.keys())}")
        return provider.compute(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time, context=context)

    @classmethod
    def execute_all(
        cls,
        ticker: str = "NQ1",
        target_date: Optional[str] = None,
        cutoff_time: str = "08:45",
        context: Optional[Dict[str, Any]] = None,
        include_scaffolds: bool = False,
    ) -> Dict[str, ConceptPayload]:
        """Execute concepts and return a dictionary of payloads.
        
        By default, executes ONLY production-grade concepts.
        Failed concepts return explicit error payloads rather than being silently omitted.
        """
        results = {}
        for name, provider in cls._registry.items():
            if not include_scaffolds and not provider.is_production:
                log.info(f"Skipping non-production concept in production synthesis: {name} [{provider.status}]")
                continue

            try:
                payload = provider.compute(
                    ticker=ticker,
                    target_date=target_date,
                    cutoff_time=cutoff_time,
                    context=context
                )
                results[name] = payload
            except Exception as e:
                log.error(f"Execution failure in concept '{name}': {e}", exc_info=True)
                results[name] = ConceptPayload(
                    name=name,
                    ticker=ticker,
                    target_date=target_date or "Unknown",
                    spot_price=0.0,
                    data={"error": str(e)},
                    markdown_report=f"# ⚠️ ERROR: Concept '{name}' Failed: {str(e)}",
                    status=provider.status,
                    is_success=False,
                    error_message=str(e),
                )
        return results
