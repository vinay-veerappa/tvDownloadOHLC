"""Concept Provider Central Registry

Discovers, registers, and executes trading concepts across the repository.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List, Type
from src.concepts.base import BaseConceptProvider, ConceptPayload

log = logging.getLogger(__name__)


class ConceptRegistry:
    """Central registry for all analytical trading concept providers."""

    _registry: Dict[str, BaseConceptProvider] = {}

    @classmethod
    def register(cls, provider: BaseConceptProvider) -> None:
        """Register a concept provider instance."""
        cls._registry[provider.name] = provider
        log.info(f"Registered concept provider: {provider.name}")

    @classmethod
    def get(cls, name: str) -> Optional[BaseConceptProvider]:
        """Retrieve a registered provider by name."""
        return cls._registry.get(name)

    @classmethod
    def list_concepts(cls) -> List[Dict[str, str]]:
        """List all registered concepts with their descriptions."""
        return [
            {"name": p.name, "description": p.description}
            for p in cls._registry.values()
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
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ConceptPayload]:
        """Execute all registered concepts and return a dictionary of payloads."""
        results = {}
        for name, provider in cls._registry.items():
            try:
                results[name] = provider.compute(
                    ticker=ticker,
                    target_date=target_date,
                    cutoff_time=cutoff_time,
                    context=context
                )
            except Exception as e:
                log.error(f"Error executing concept {name}: {e}")
        return results
