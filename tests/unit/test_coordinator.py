"""Unit tests for the EligibilityCoordinator."""

import pytest
from src.matching.coordinator import EligibilityCoordinator
from src.matching.schema import (
    AgentExecutionStatus,
    AgentResult,
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    OverallStatus,
)


@pytest.fixture
def coordinator() -> EligibilityCoordinator:
    return EligibilityCoordinator()


def test_coordinator_all_mandatory_passing(coordinator: EligibilityCoordinator):
    """Test coordinator normal flow with all mandatory criteria passing."""
    agent_results = [
        AgentResult(
            agent_id="demographics_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=35,
                    expected_value=">= 18",
                    explanation="Age is 35.",
                )
            ],
        ),
        AgentResult(
            agent_id="labs_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_PLATELETS",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=200000,
                    expected_value=">= 100000",
                    explanation="Platelet count adequate.",
                )
            ],
        ),
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_001",
        trial_id="NCT05001234",
        agent_results=agent_results,
        required_agents=["demographics_agent", "labs_agent"],
        required_criteria=["CRIT_AGE", "CRIT_PLATELETS"],
    )

    assert report.patient_id == "PATIENT_001"
    assert report.trial_id == "NCT05001234"
    assert report.overall_status == OverallStatus.POTENTIAL_MATCH
    assert report.requires_human_review is False
    assert report.counts.mandatory_passed == 2
    assert len(report.missing_agents) == 0
    assert len(report.missing_criteria) == 0
    assert len(report.errors) == 0


def test_coordinator_one_mandatory_failing(coordinator: EligibilityCoordinator):
    """Test coordinator normal flow with one mandatory failing criterion."""
    agent_results = [
        AgentResult(
            agent_id="oncology_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_STAGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.FAIL,
                    observed_value="Stage II",
                    expected_value="Stage IV (Metastatic)",
                    explanation="Trial restricted to metastatic disease.",
                )
            ],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_002",
        trial_id="NCT05001234",
        agent_results=agent_results,
    )

    assert report.overall_status == OverallStatus.NOT_A_MATCH
    assert report.requires_human_review is False
    assert report.counts.mandatory_failed == 1
    assert any("CRIT_STAGE" in r and "failed" in r for r in report.reasons)


def test_coordinator_missing_required_agent(coordinator: EligibilityCoordinator):
    """Test 5: Missing required agent results in REQUIRES_REVIEW."""
    agent_results = [
        AgentResult(
            agent_id="demographics_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=40,
                    expected_value=">= 18",
                )
            ],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_003",
        trial_id="NCT05001234",
        agent_results=agent_results,
        required_agents=["demographics_agent", "pathology_agent"],
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert "pathology_agent" in report.missing_agents
    assert any("Missing required agent(s): pathology_agent" in r for r in report.reasons)


def test_coordinator_missing_mandatory_criterion(coordinator: EligibilityCoordinator):
    """Test 6: Missing mandatory criterion results in REQUIRES_REVIEW."""
    agent_results = [
        AgentResult(
            agent_id="demographics_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=40,
                    expected_value=">= 18",
                )
            ],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_004",
        trial_id="NCT05001234",
        agent_results=agent_results,
        required_criteria=["CRIT_AGE", "CRIT_HISTOLOGY"],
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert "CRIT_HISTOLOGY" in report.missing_criteria
    assert any("Missing required mandatory criterion/criteria: CRIT_HISTOLOGY" in r for r in report.reasons)


def test_coordinator_invalid_criterion_status(coordinator: EligibilityCoordinator):
    """Test 7: Invalid status never silently passes and results in REQUIRES_REVIEW."""
    raw_results = [
        {
            "agent_id": "experimental_agent",
            "criteria_results": [
                {
                    "criterion_id": "CRIT_BIOMARKER",
                    "criterion_type": "MANDATORY",
                    "status": "MAYBE",  # Invalid enum value
                    "observed_value": "Borderline",
                    "expected_value": "Positive",
                }
            ],
        }
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_005",
        trial_id="NCT05001234",
        agent_results=raw_results,
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert len(report.errors) > 0
    assert any("MAYBE" in err or "Validation error" in r for err in report.errors for r in report.reasons)


def test_coordinator_malformed_agent_output(coordinator: EligibilityCoordinator):
    """Test 8: Malformed agent output never silently passes and results in REQUIRES_REVIEW."""
    malformed_results = [
        "not a valid agent result dictionary or object",
        {"completely_wrong_key": 123},
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_006",
        trial_id="NCT05001234",
        agent_results=malformed_results,
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert len(report.errors) >= 2
    assert any("Malformed" in err for err in report.errors)


def test_coordinator_agent_evaluation_failure(coordinator: EligibilityCoordinator):
    """Test 9: Agent evaluation failure results in REQUIRES_REVIEW with error recorded."""
    agent_results = [
        AgentResult(
            agent_id="genomics_agent",
            status=AgentExecutionStatus.ERROR,
            error_message="VCF file could not be parsed: line 402 corrupt.",
            criteria_results=[],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_007",
        trial_id="NCT05001234",
        agent_results=agent_results,
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert any("genomics_agent" in err for err in report.errors)
    assert any("VCF file could not be parsed" in r for r in report.reasons)


def test_coordinator_with_injected_agent_runners(coordinator: EligibilityCoordinator):
    """Test dependency injection with callable agents."""
    def mock_demographics_runner(p_id: str, t_id: str) -> AgentResult:
        return AgentResult(
            agent_id="mock_demographics",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=60,
                    expected_value=">= 18",
                )
            ],
        )

    def mock_failing_runner(p_id: str, t_id: str) -> AgentResult:
        raise RuntimeError("Service unavailable timeout")

    report = coordinator.evaluate_with_agents(
        patient_id="PATIENT_008",
        trial_id="NCT05001234",
        agents_to_run={
            "mock_demographics": mock_demographics_runner,
            "mock_failing": mock_failing_runner,
        },
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert any("mock_failing" in err and "Service unavailable timeout" in err for err in report.errors)


def test_coordinator_never_pretends_uncalled_agent_ran():
    """Verify that coordinator only reports agents that were actually supplied."""
    coordinator = EligibilityCoordinator()
    report = coordinator.evaluate(
        patient_id="PATIENT_009",
        trial_id="NCT05001234",
        agent_results=[],
        required_agents=["uncalled_agent"],
    )

    assert "uncalled_agent" in report.missing_agents
    assert report.overall_status == OverallStatus.REQUIRES_REVIEW


def test_coordinator_safe_exception_handling_on_invalid_inputs(coordinator: EligibilityCoordinator):
    """Test that invalid inputs (e.g., None patient_id, empty strings) are safely handled without unhandled crashes."""
    report = coordinator.evaluate(
        patient_id="",
        trial_id="",
        agent_results=None,  # type: ignore
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert any("Invalid patient_id" in err for err in report.errors)
    assert any("Invalid trial_id" in err for err in report.errors)
    assert any("agent_results" in err for err in report.errors)


def test_coordinator_empty_results(coordinator: EligibilityCoordinator):
    """Test 4 via coordinator: Empty results result in REQUIRES_REVIEW."""
    report = coordinator.evaluate(
        patient_id="PATIENT_EMPTY",
        trial_id="NCT05001234",
        agent_results=[],
    )

    assert report.overall_status == OverallStatus.REQUIRES_REVIEW
    assert report.requires_human_review is True
    assert any("empty" in r.lower() or "no mandatory" in r.lower() for r in report.reasons)


def test_coordinator_mandatory_failure_combined_with_unknown(coordinator: EligibilityCoordinator):
    """Test 10 via coordinator: Definitive mandatory failure combined with unknown results in NOT_A_MATCH."""
    agent_results = [
        AgentResult(
            agent_id="agent_1",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.FAIL,
                    observed_value=15,
                    expected_value=">= 18",
                    explanation="Underage.",
                ),
                CriterionResult(
                    criterion_id="CRIT_LAB",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.UNKNOWN,
                    observed_value=None,
                    expected_value="Platelets >= 100k",
                    explanation="Lab not yet drawn.",
                ),
            ],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_010",
        trial_id="NCT05001234",
        agent_results=agent_results,
    )

    assert report.overall_status == OverallStatus.NOT_A_MATCH
    assert report.requires_human_review is False
    assert report.counts.mandatory_failed == 1
    assert report.counts.mandatory_unknown == 1


def test_coordinator_optional_unknown_does_not_block_potential_match(
    coordinator: EligibilityCoordinator,
):
    """Test 11 via coordinator: Optional criteria that are UNKNOWN do not block POTENTIAL_MATCH."""
    agent_results = [
        AgentResult(
            agent_id="agent_1",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_MANDATORY_1",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=40,
                    expected_value=">= 18",
                    explanation="Age valid.",
                ),
                CriterionResult(
                    criterion_id="CRIT_OPTIONAL_1",
                    criterion_type=CriterionType.OPTIONAL,
                    status=CriterionStatus.UNKNOWN,
                    observed_value=None,
                    expected_value="Optional biomarker positive",
                    explanation="Exploratory biomarker test not performed.",
                ),
            ],
        )
    ]

    report = coordinator.evaluate(
        patient_id="PATIENT_011",
        trial_id="NCT05001234",
        agent_results=agent_results,
    )

    assert report.overall_status == OverallStatus.POTENTIAL_MATCH
    assert report.requires_human_review is False
    assert report.counts.mandatory_passed == 1
    assert report.counts.optional_unknown == 1

