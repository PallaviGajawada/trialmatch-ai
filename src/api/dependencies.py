"""Dependency injection providers for FastAPI backend."""

from __future__ import annotations

from typing import Optional
from src.agents.adapter import ClinicalAgentsAdapter
from src.matching.coordinator import EligibilityCoordinator
from src.matching.decision_rules import DeterministicDecisionEngine

_coordinator_instance: Optional[EligibilityCoordinator] = None
_adapter_instance: Optional[ClinicalAgentsAdapter] = None


def get_adapter() -> Optional[ClinicalAgentsAdapter]:
    """
    FastAPI dependency providing a ClinicalAgentsAdapter instance.

    Can be overridden in tests via app.dependency_overrides[get_adapter].
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = ClinicalAgentsAdapter()
    return _adapter_instance


def set_adapter(adapter: Optional[ClinicalAgentsAdapter]) -> None:
    """Set or reset the global adapter instance."""
    global _adapter_instance
    _adapter_instance = adapter


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
