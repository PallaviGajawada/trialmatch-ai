"""Pydantic schemas for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from src.matching.schema import AgentResult


class EvaluationRequest(BaseModel):
    """Request payload for patient clinical trial eligibility screening."""

    patient_id: str = Field(..., description="Unique patient identifier.")
    trial_id: str = Field(
        ..., description="Target clinical trial identifier (e.g., NCT05001234)."
    )
    agent_results: Optional[List[Union[AgentResult, Dict[str, Any]]]] = Field(
        default=None,
        description="Optional pre-evaluated agent results. If omitted, coordinator executes registered agents.",
    )
    required_agents: Optional[List[str]] = Field(
        default=None,
        description="Optional list of required agent IDs that must report.",
    )
    required_criteria: Optional[List[str]] = Field(
        default=None,
        description="Optional list of required criterion IDs that must be evaluated.",
    )

    @field_validator("patient_id", "trial_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Must be a non-empty string.")
        return v.strip()


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
    service: str
    version: str
    agents_configured: bool
    pipeline_status: str
    registered_agents: List[str] = Field(default_factory=list)
