"""Eligibility coordinator orchestrating agents and deterministic decision engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union
from pydantic import ValidationError

from src.matching.decision_rules import DeterministicDecisionEngine
from src.matching.schema import (
    AgentExecutionStatus,
    AgentResult,
    CriterionResult,
    CriterionStatus,
    EvaluationCounts,
    OverallStatus,
    ScreeningReport,
)

logger = logging.getLogger(__name__)


class EligibilityCoordinator:
    """
    Coordinates clinical trial eligibility evaluation across multi-agent outputs.

    Responsibilities:
    - Validate input parameters (patient_id, trial_id, agent_results).
    - Ensure all required agents have reported and all required criteria evaluated.
    - Aggregate criterion findings preserving provenance.
    - Invoke the deterministic decision engine.
    - Produce an auditable, structured ScreeningReport.
    - Safely handle agent failures, malformed payloads, and unexpected exceptions.
    - Never assume an agent ran if it was not invoked.
    """

    def __init__(
        self,
        decision_engine: Optional[DeterministicDecisionEngine] = None,
        registered_agents: Optional[
            Mapping[str, Callable[[str, str], Union[AgentResult, Dict[str, Any]]]]
        ] = None,
    ):
        self.decision_engine = decision_engine or DeterministicDecisionEngine()
        self.registered_agents = dict(registered_agents) if registered_agents else {}

    def evaluate(
        self,
        patient_id: str,
        trial_id: str,
        agent_results: Sequence[Union[AgentResult, Dict[str, Any]]],
        required_agents: Optional[Sequence[str]] = None,
        required_criteria: Optional[Sequence[str]] = None,
    ) -> ScreeningReport:
        """
        Evaluate eligibility from pre-collected agent outputs.

        Args:
            patient_id: Unique identifier for the patient.
            trial_id: Clinical trial identifier (e.g., NCT01234567).
            agent_results: Sequence of AgentResult instances or raw result dicts.
            required_agents: Optional list of agent IDs that must report.
            required_criteria: Optional list of criterion IDs that must be evaluated.

        Returns:
            Structured ScreeningReport with deterministic eligibility outcome.
        """
        try:
            return self._execute_evaluation(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_results=agent_results,
                required_agents=required_agents,
                required_criteria=required_criteria,
            )
        except Exception as exc:
            logger.exception("Unexpected exception in coordinator: %s", exc)
            return self._build_safe_error_report(
                patient_id=str(patient_id) if patient_id is not None else "UNKNOWN",
                trial_id=str(trial_id) if trial_id is not None else "UNKNOWN",
                error_message=f"Coordinator internal error: {str(exc)}",
            )

    def evaluate_with_agents(
        self,
        patient_id: str,
        trial_id: str,
        agents_to_run: Optional[
            Mapping[str, Callable[[str, str], Union[AgentResult, Dict[str, Any]]]]
        ] = None,
        required_agents: Optional[Sequence[str]] = None,
        required_criteria: Optional[Sequence[str]] = None,
    ) -> ScreeningReport:
        """
        Execute injected agent callables and evaluate patient eligibility.

        Never pretends an agent ran if it was not called.
        """
        runners = dict(self.registered_agents)
        if agents_to_run:
            runners.update(agents_to_run)

        collected_results: List[AgentResult] = []

        for agent_id, runner in runners.items():
            try:
                raw_result = runner(patient_id, trial_id)
                if isinstance(raw_result, AgentResult):
                    collected_results.append(raw_result)
                elif isinstance(raw_result, dict):
                    collected_results.append(AgentResult.model_validate(raw_result))
                else:
                    collected_results.append(
                        AgentResult(
                            agent_id=agent_id,
                            status=AgentExecutionStatus.ERROR,
                            error_message=f"Agent runner returned unexpected type: {type(raw_result).__name__}",
                        )
                    )
            except Exception as exc:
                logger.warning("Agent %s failed during execution: %s", agent_id, exc)
                collected_results.append(
                    AgentResult(
                        agent_id=agent_id,
                        status=AgentExecutionStatus.ERROR,
                        error_message=f"Agent execution exception: {str(exc)}",
                    )
                )

        return self.evaluate(
            patient_id=patient_id,
            trial_id=trial_id,
            agent_results=collected_results,
            required_agents=required_agents,
            required_criteria=required_criteria,
        )

    def _execute_evaluation(
        self,
        patient_id: str,
        trial_id: str,
        agent_results: Sequence[Union[AgentResult, Dict[str, Any]]],
        required_agents: Optional[Sequence[str]],
        required_criteria: Optional[Sequence[str]],
    ) -> ScreeningReport:
        validation_errors: List[str] = []
        agent_errors: List[str] = []

        # Validate identifiers
        if not patient_id or not isinstance(patient_id, str) or not patient_id.strip():
            validation_errors.append("Invalid patient_id: must be a non-empty string.")

        if not trial_id or not isinstance(trial_id, str) or not trial_id.strip():
            validation_errors.append("Invalid trial_id: must be a non-empty string.")

        # Validate agent_results container
        if agent_results is None or not hasattr(agent_results, "__iter__"):
            validation_errors.append("agent_results must be a valid sequence/iterable.")
            agent_results = []

        parsed_agents: List[AgentResult] = []
        aggregated_criteria: List[CriterionResult] = []

        for idx, item in enumerate(agent_results):
            if isinstance(item, AgentResult):
                agent = item
            elif isinstance(item, dict):
                try:
                    agent = AgentResult.model_validate(item)
                except ValidationError as val_err:
                    validation_errors.append(
                        f"Malformed agent result at index {idx}: {val_err}"
                    )
                    continue
                except Exception as ex:
                    validation_errors.append(
                        f"Malformed agent result at index {idx}: {ex}"
                    )
                    continue
            else:
                validation_errors.append(
                    f"Malformed agent output at index {idx}: expected AgentResult or dict, got {type(item).__name__}"
                )
                continue

            parsed_agents.append(agent)

            # Check agent execution status
            if agent.status == AgentExecutionStatus.ERROR:
                agent_errors.append(
                    f"Agent '{agent.agent_id}' reported failure: {agent.error_message or 'Unknown error'}"
                )

            # Validate each criterion
            for crit_idx, criterion in enumerate(agent.criteria_results):
                # Ensure agent_id is populated for provenance
                if not criterion.agent_id:
                    criterion.agent_id = agent.agent_id

                # Validate status value
                if not isinstance(criterion.status, CriterionStatus):
                    try:
                        criterion.status = CriterionStatus(str(criterion.status).upper())
                    except Exception:
                        validation_errors.append(
                            f"Invalid status '{criterion.status}' on criterion '{criterion.criterion_id}' (agent '{agent.agent_id}')."
                        )

                aggregated_criteria.append(criterion)

        # Check required agents presence
        reported_agent_ids = {a.agent_id for a in parsed_agents}
        missing_agents: List[str] = []
        if required_agents:
            for req_agent in required_agents:
                if req_agent not in reported_agent_ids:
                    missing_agents.append(req_agent)

        # Check required criteria presence
        evaluated_crit_ids = {c.criterion_id for c in aggregated_criteria}
        missing_criteria: List[str] = []
        if required_criteria:
            for req_crit in required_criteria:
                if req_crit not in evaluated_crit_ids:
                    missing_criteria.append(req_crit)

        # Run deterministic decision engine
        overall_status, requires_human_review, reasons, counts = (
            self.decision_engine.evaluate(
                criterion_results=aggregated_criteria,
                missing_agents=missing_agents,
                missing_criteria=missing_criteria,
                agent_errors=agent_errors,
                validation_errors=validation_errors,
            )
        )

        all_errors = validation_errors + agent_errors

        return ScreeningReport(
            patient_id=str(patient_id) if patient_id is not None else "UNKNOWN",
            trial_id=str(trial_id) if trial_id is not None else "UNKNOWN",
            overall_status=overall_status,
            requires_human_review=requires_human_review,
            reasons=reasons,
            counts=counts,
            criterion_results=aggregated_criteria,
            missing_agents=missing_agents,
            missing_criteria=missing_criteria,
            errors=all_errors,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _build_safe_error_report(
        self, patient_id: str, trial_id: str, error_message: str
    ) -> ScreeningReport:
        """Produce safe fallback report when an unhandled exception occurs."""
        return ScreeningReport(
            patient_id=patient_id,
            trial_id=trial_id,
            overall_status=OverallStatus.REQUIRES_REVIEW,
            requires_human_review=True,
            reasons=[error_message],
            counts=EvaluationCounts(),
            criterion_results=[],
            errors=[error_message],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
