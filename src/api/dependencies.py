"""Dependency injection providers for FastAPI backend."""

from __future__ import annotations

from typing import Optional
from src.matching.coordinator import EligibilityCoordinator
from src.matching.decision_rules import DeterministicDecisionEngine

_coordinator_instance: Optional[EligibilityCoordinator] = None


def get_coordinator() -> EligibilityCoordinator:
    """
    FastAPI dependency providing an EligibilityCoordinator.

    Can be overridden in tests via app.dependency_overrides[get_coordinator].
    """
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = EligibilityCoordinator(
            decision_engine=DeterministicDecisionEngine()
        )
    return _coordinator_instance


def set_coordinator(coordinator: Optional[EligibilityCoordinator]) -> None:
    """Set or reset the global coordinator instance."""
    global _coordinator_instance
    _coordinator_instance = coordinator
