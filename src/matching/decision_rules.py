"""Deterministic decision engine for clinical trial patient eligibility matching."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple
from src.matching.schema import (
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvaluationCounts,
    OverallStatus,
)


class DeterministicDecisionEngine:
    """
    Deterministic rule-based clinical trial eligibility decision engine.

    Implements clinical trial eligibility logic with zero score-based heuristics:
    1. A definitive failure of any mandatory criterion results in NOT_A_MATCH.
    2. Any required criterion with status UNKNOWN results in REQUIRES_REVIEW,
       unless a mandatory failure already establishes NOT_A_MATCH.
    3. Missing agent outputs, evaluation errors, invalid statuses, missing required
       criteria, or empty results result in REQUIRES_REVIEW (unless a mandatory failure
       already establishes NOT_A_MATCH).
    4. All mandatory criteria must be evaluated and PASS before returning POTENTIAL_MATCH.
    5. Optional criteria that are UNKNOWN do not block POTENTIAL_MATCH.
    6. Clinical eligibility is NEVER inferred from a percentage score.
    """

    def compute_counts(
        self, criterion_results: Sequence[CriterionResult]
    ) -> EvaluationCounts:
        """Calculate statistical counts across evaluated criteria."""
        counts = EvaluationCounts()
        counts.total_criteria = len(criterion_results)

        for c in criterion_results:
            is_mand = c.criterion_type == CriterionType.MANDATORY

            if c.status == CriterionStatus.PASS:
                counts.passed += 1
                if is_mand:
                    counts.mandatory_passed += 1
                else:
                    counts.optional_passed += 1
            elif c.status == CriterionStatus.FAIL:
                counts.failed += 1
                if is_mand:
                    counts.mandatory_failed += 1
                else:
                    counts.optional_failed += 1
            elif c.status == CriterionStatus.UNKNOWN:
                counts.unknown += 1
                if is_mand:
                    counts.mandatory_unknown += 1
                else:
                    counts.optional_unknown += 1

            if is_mand:
                counts.mandatory_total += 1
            else:
                counts.optional_total += 1

        return counts

    def evaluate(
        self,
        criterion_results: Sequence[CriterionResult],
        missing_agents: Optional[Sequence[str]] = None,
        missing_criteria: Optional[Sequence[str]] = None,
        agent_errors: Optional[Sequence[str]] = None,
        validation_errors: Optional[Sequence[str]] = None,
    ) -> Tuple[OverallStatus, bool, List[str], EvaluationCounts]:
        """
        Evaluate criteria results and return deterministic eligibility decision.

        Returns:
            Tuple of:
                - overall_status (OverallStatus)
                - requires_human_review (bool)
                - reasons (List[str])
                - counts (EvaluationCounts)
        """
        missing_agents = list(missing_agents or [])
        missing_criteria = list(missing_criteria or [])
        agent_errors = list(agent_errors or [])
        validation_errors = list(validation_errors or [])

        counts = self.compute_counts(criterion_results)

        # Rule 1: A definitive failure of any mandatory criterion results in NOT_A_MATCH
        mandatory_fails = [
            c
            for c in criterion_results
            if c.is_mandatory and c.status == CriterionStatus.FAIL
        ]

        if mandatory_fails:
            reasons = [
                f"Mandatory criterion '{c.criterion_id}' failed: "
                f"observed={c.observed_value!r}, expected={c.expected_value!r}. "
                f"Explanation: {c.explanation or 'Criteria requirement not met.'}"
                for c in mandatory_fails
            ]

            # Informative notes for reviewer awareness even if NOT_A_MATCH is definitive
            if counts.mandatory_unknown > 0:
                reasons.append(
                    f"Note: {counts.mandatory_unknown} mandatory criteria had UNKNOWN status, "
                    "but mandatory failure establishes NOT_A_MATCH."
                )
            if missing_agents:
                reasons.append(
                    f"Note: Missing required agent(s): {', '.join(missing_agents)}."
                )
            if missing_criteria:
                reasons.append(
                    f"Note: Missing required criterion/criteria: {', '.join(missing_criteria)}."
                )
            if agent_errors:
                reasons.append(f"Note: Agent error(s): {'; '.join(agent_errors)}.")
            if validation_errors:
                reasons.append(
                    f"Note: Validation error(s): {'; '.join(validation_errors)}."
                )

            return OverallStatus.NOT_A_MATCH, False, reasons, counts

        # Rule 2 & 3: Check for conditions that preclude POTENTIAL_MATCH and require review
        review_reasons: List[str] = []

        if validation_errors:
            review_reasons.extend(
                [f"Validation error: {err}" for err in validation_errors]
            )

        if agent_errors:
            review_reasons.extend(
                [f"Agent execution failure: {err}" for err in agent_errors]
            )

        if missing_agents:
            review_reasons.append(
                f"Missing required agent(s): {', '.join(missing_agents)}"
            )

        if missing_criteria:
            review_reasons.append(
                f"Missing required mandatory criterion/criteria: {', '.join(missing_criteria)}"
            )

        # Rule 2: Any required criterion with status UNKNOWN results in REQUIRES_REVIEW
        for c in criterion_results:
            if c.is_mandatory and c.status == CriterionStatus.UNKNOWN:
                review_reasons.append(
                    f"Mandatory criterion '{c.criterion_id}' status is UNKNOWN: "
                    f"{c.explanation or 'Insufficient patient data to evaluate criterion.'}"
                )

        # Rule 4: Empty results / no mandatory criteria evaluated cannot be PASS
        if counts.mandatory_total == 0:
            review_reasons.append(
                "No mandatory criteria were evaluated (empty or incomplete results)."
            )

        if review_reasons:
            return OverallStatus.REQUIRES_REVIEW, True, review_reasons, counts

        # Rule 5: All mandatory criteria must be evaluated and PASS before returning POTENTIAL_MATCH
        # Optional criteria that are UNKNOWN do NOT block POTENTIAL_MATCH.
        if (
            counts.mandatory_total > 0
            and counts.mandatory_passed == counts.mandatory_total
        ):
            reasons = [
                f"All mandatory criteria passed ({counts.mandatory_passed}/{counts.mandatory_total})."
            ]

            # Add context for optional criteria if any are unknown or failed
            for c in criterion_results:
                if not c.is_mandatory:
                    if c.status == CriterionStatus.UNKNOWN:
                        reasons.append(
                            f"Note: Optional criterion '{c.criterion_id}' is UNKNOWN: "
                            f"{c.explanation or 'Data unavailable.'}"
                        )
                    elif c.status == CriterionStatus.FAIL:
                        reasons.append(
                            f"Note: Optional criterion '{c.criterion_id}' did not match: "
                            f"observed={c.observed_value!r}, expected={c.expected_value!r}."
                        )

            return OverallStatus.POTENTIAL_MATCH, False, reasons, counts

        # Fallback safeguard: Any unhandled state must require review
        return (
            OverallStatus.REQUIRES_REVIEW,
            True,
            ["Evaluation could not be deterministically resolved."],
            counts,
        )
