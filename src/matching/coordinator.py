"""Eligibility coordinator orchestrating agents and deterministic decision engine."""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Union
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
    - Detect invalid agent identifiers, duplicate agent reports, duplicate criteria, and conflicting evaluations.
    - Ensure all required agents have reported and all required criteria evaluated.
    - Aggregate criterion findings preserving provenance.
    - Invoke the deterministic decision engine.
    - Produce an auditable, structured ScreeningReport.
    - Safely handle agent failures, malformed payloads, timeouts, and unexpected exceptions.
    - Never assume an agent ran if it was not invoked.
    """

    def __init__(
        self,
        decision_engine: Optional[DeterministicDecisionEngine] = None,
        registered_agents: Optional[
            Mapping[str, Callable[[str, str], Union[AgentResult, Dict[str, Any]]]]
        ] = None,
        allowed_agents: Optional[Sequence[str]] = None,
        default_agent_timeout: Optional[float] = None,
    ):
        self.decision_engine = decision_engine or DeterministicDecisionEngine()
        self.registered_agents = dict(registered_agents) if registered_agents else {}
        self.allowed_agents = set(allowed_agents) if allowed_agents else None
        self.default_agent_timeout = default_agent_timeout

    def evaluate(
        self,
        patient_id: str,
        trial_id: str,
        agent_results: Sequence[Union[AgentResult, Dict[str, Any]]],
        required_agents: Optional[Sequence[str]] = None,
        required_criteria: Optional[Sequence[str]] = None,
        allowed_agents: Optional[Sequence[str]] = None,
    ) -> ScreeningReport:
        """
        Evaluate eligibility from pre-collected agent outputs.

        Args:
            patient_id: Unique identifier for the patient.
            trial_id: Clinical trial identifier (e.g., NCT01234567).
            agent_results: Sequence of AgentResult instances or raw result dicts.
            required_agents: Optional list of agent IDs that must report.
            required_criteria: Optional list of criterion IDs that must be evaluated.
            allowed_agents: Optional list of authorized agent IDs.

        Returns:
            Structured ScreeningReport with deterministic eligibility outcome.
        """
        try:
            effective_allowed_agents = (
                set(allowed_agents)
                if allowed_agents is not None
                else self.allowed_agents
            )
            return self._execute_evaluation(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_results=agent_results,
                required_agents=required_agents,
                required_criteria=required_criteria,
                allowed_agents=effective_allowed_agents,
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
        allowed_agents: Optional[Sequence[str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ScreeningReport:
        """
        Execute injected agent callables and evaluate patient eligibility.

        Never pretends an agent ran if it was not called.
        Supports execution timeouts when timeout_seconds is provided.
        """
        runners = dict(self.registered_agents)
        if agents_to_run:
            runners.update(agents_to_run)

        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.default_agent_timeout
        )

        collected_results: List[AgentResult] = []

        for agent_id, runner in runners.items():
            try:
                if timeout and timeout > 0:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(runner, patient_id, trial_id)
                        try:
                            raw_result = future.result(timeout=timeout)
                        except concurrent.futures.TimeoutError:
                            collected_results.append(
                                AgentResult(
                                    agent_id=agent_id,
                                    status=AgentExecutionStatus.ERROR,
                                    error_message=f"Agent '{agent_id}' execution timed out after {timeout} seconds.",
                                )
                            )
                            continue
                else:
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
            allowed_agents=allowed_agents,
        )

    def _execute_evaluation(
        self,
        patient_id: str,
        trial_id: str,
        agent_results: Sequence[Union[AgentResult, Dict[str, Any]]],
        required_agents: Optional[Sequence[str]],
        required_criteria: Optional[Sequence[str]],
        allowed_agents: Optional[Set[str]],
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
        seen_agents: Set[str] = set()
        seen_criteria: Dict[str, List[CriterionResult]] = {}
        conflicting_criteria: Set[str] = set()

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

            # Validate agent_id
            if not agent.agent_id or not agent.agent_id.strip():
                validation_errors.append(
                    f"Invalid agent_id at index {idx}: must be a non-empty string."
                )
                continue

            # Validate against allowed_agents if configured
            if allowed_agents is not None and agent.agent_id not in allowed_agents:
                validation_errors.append(
                    f"Unknown agent identifier: '{agent.agent_id}'. Allowed agents: {sorted(allowed_agents)}"
                )

            # Check for duplicate agent results
            if agent.agent_id in seen_agents:
                validation_errors.append(
                    f"Duplicate agent result received for agent '{agent.agent_id}'."
                )
            seen_agents.add(agent.agent_id)

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

                cid = criterion.criterion_id
                if not cid or not isinstance(cid, str) or not cid.strip():
                    validation_errors.append(
                        f"Invalid criterion_id at index {crit_idx} in agent '{agent.agent_id}'."
                    )
                    continue

                # Check for duplicate criterion evaluations
                if cid in seen_criteria:
                    prev_evals = seen_criteria[cid]
                    validation_errors.append(
                        f"Duplicate evaluation received for criterion '{cid}' (reported by '{criterion.agent_id}')."
                    )

                    # Check for conflicting criterion statuses
                    conflicts = [p for p in prev_evals if p.status != criterion.status]
                    if conflicts:
                        conflicting_criteria.add(cid)
                        conflict_msg = (
                            f"Conflicting evaluation results for criterion '{cid}': "
                            f"received '{criterion.status.value}' from '{criterion.agent_id}' but earlier received "
                            f"{[p.status.value for p in prev_evals]} from {[p.agent_id for p in prev_evals]}."
                        )
                        validation_errors.append(conflict_msg)

                seen_criteria.setdefault(cid, []).append(criterion)
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
                conflicting_criteria=list(conflicting_criteria),
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
