"""Data contracts and schemas for TrialMatch AI matching and decision engine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class OverallStatus(str, Enum):
    """Overall screening eligibility status."""

    POTENTIAL_MATCH = "POTENTIAL_MATCH"
    NOT_A_MATCH = "NOT_A_MATCH"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class CriterionStatus(str, Enum):
    """Outcome status for an individual criterion evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class CriterionType(str, Enum):
    """Explicit designation whether a criterion is mandatory or optional."""

    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"


class AgentExecutionStatus(str, Enum):
    """Execution status of an eligibility agent."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class EvidenceProvenance(BaseModel):
    """Provenance and source citation for criterion evidence."""

    model_config = ConfigDict(extra="allow")

    source: str = Field(
        ...,
        description="Source data system or document, e.g., 'EHR', 'Lab_Report', 'Trial_Protocol'.",
    )
    document_id: Optional[str] = Field(
        None, description="Identifier of the source document or record."
    )
    field_name: Optional[str] = Field(
        None, description="Specific field or observation name in the record."
    )
    extracted_value: Any = Field(
        None, description="Raw or normalized value extracted from the source."
    )
    source_text: Optional[str] = Field(
        None, description="Exact text excerpt or snippet supporting the finding."
    )
    confidence: Optional[float] = Field(
        None, description="Optional extraction confidence score (0.0 to 1.0)."
    )
    timestamp: Optional[str] = Field(
        None, description="Timestamp of the clinical observation or extraction."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context or provenance metadata."
    )


class CriterionResult(BaseModel):
    """Structured evaluation result for an individual criterion."""

    model_config = ConfigDict(extra="allow")

    criterion_id: str = Field(..., description="Unique criterion identifier.")
    name: Optional[str] = Field(None, description="Human-readable name of the criterion.")
    criterion_type: CriterionType = Field(
        default=CriterionType.MANDATORY,
        description="Whether this criterion is MANDATORY or OPTIONAL.",
    )
    status: CriterionStatus = Field(
        ..., description="Evaluation outcome: PASS, FAIL, or UNKNOWN."
    )
    observed_value: Any = Field(
        None, description="Observed patient value, measurement, or condition."
    )
    expected_value: Any = Field(
        None, description="Required trial value, threshold, or inclusion/exclusion target."
    )
    explanation: str = Field(
        default="", description="Detailed human-readable explanation of the assessment."
    )
    evidence: Optional[Union[EvidenceProvenance, Dict[str, Any], str]] = Field(
        None, description="Provenance evidence supporting this finding."
    )
    agent_id: Optional[str] = Field(
        None, description="Identifier of the agent that evaluated this criterion."
    )

    @property
    def is_mandatory(self) -> bool:
        """Returns True if this criterion is mandatory for trial eligibility."""
        return self.criterion_type == CriterionType.MANDATORY


class AgentResult(BaseModel):
    """Result payload emitted by an eligibility agent."""

    model_config = ConfigDict(extra="allow")

    agent_id: str = Field(..., description="Unique identifier of the agent.")
    status: AgentExecutionStatus = Field(
        default=AgentExecutionStatus.SUCCESS,
        description="Execution status of the agent (SUCCESS, ERROR, SKIPPED).",
    )
    criteria_results: List[CriterionResult] = Field(
        default_factory=list,
        description="List of criterion evaluations conducted by this agent.",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if the agent encountered a failure."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent execution metadata (execution time, version, etc.).",
    )


class EvaluationCounts(BaseModel):
    """Statistical counts of criterion evaluations."""

    total_criteria: int = 0
    passed: int = 0
    failed: int = 0
    unknown: int = 0
    mandatory_total: int = 0
    mandatory_passed: int = 0
    mandatory_failed: int = 0
    mandatory_unknown: int = 0
    optional_total: int = 0
    optional_passed: int = 0
    optional_failed: int = 0
    optional_unknown: int = 0


class ScreeningReport(BaseModel):
    """Deterministic eligibility screening report produced by the coordinator."""

    model_config = ConfigDict(extra="allow")

    patient_id: str = Field(..., description="Target patient identifier.")
    trial_id: str = Field(..., description="Target clinical trial identifier.")
    overall_status: OverallStatus = Field(
        ..., description="Overall eligibility status: POTENTIAL_MATCH, NOT_A_MATCH, REQUIRES_REVIEW."
    )
    requires_human_review: bool = Field(
        ..., description="Flag indicating if manual human/clinician review is required."
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Auditable reasons supporting the overall eligibility decision.",
    )
    counts: EvaluationCounts = Field(
        default_factory=EvaluationCounts,
        description="Aggregate counts across evaluated criteria.",
    )
    criterion_results: List[CriterionResult] = Field(
        default_factory=list,
        description="All individual criterion results with provenance preserved.",
    )
    missing_agents: List[str] = Field(
        default_factory=list,
        description="List of required agent IDs that failed to report.",
    )
    missing_criteria: List[str] = Field(
        default_factory=list,
        description="List of required criterion IDs that were not evaluated.",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any validation, agent execution, or parsing errors recorded.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of report generation.",
    )
