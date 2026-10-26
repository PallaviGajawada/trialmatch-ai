"""Unit tests for the deterministic decision engine."""

import pytest
from src.matching.decision_rules import DeterministicDecisionEngine
from src.matching.schema import (
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    OverallStatus,
)


@pytest.fixture
def engine() -> DeterministicDecisionEngine:
    return DeterministicDecisionEngine()


def test_all_mandatory_criteria_passing(engine: DeterministicDecisionEngine):
    """Test 1: All mandatory criteria passing results in POTENTIAL_MATCH."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_AGE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=45,
            expected_value=">= 18",
            explanation="Patient age is 45, which meets >= 18 requirement.",
            evidence=EvidenceProvenance(
                source="EHR", field_name="birth_date", extracted_value="1981-05-12"
            ),
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_DIAGNOSIS",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value="Non-small cell lung cancer",
            expected_value="NSCLC",
            explanation="Histologically confirmed NSCLC.",
            evidence=EvidenceProvenance(
                source="Pathology_Report",
                document_id="PATH_992",
                extracted_value="NSCLC Stage IV",
            ),
            agent_id="conditions_agent",
        ),
    ]

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    assert status == OverallStatus.POTENTIAL_MATCH
    assert review_needed is False
    assert counts.total_criteria == 2
    assert counts.mandatory_passed == 2
    assert counts.mandatory_failed == 0
    assert counts.mandatory_unknown == 0
    assert any("All mandatory criteria passed" in r for r in reasons)


def test_one_mandatory_criterion_failing(engine: DeterministicDecisionEngine):
    """Test 2: One mandatory criterion failing results in NOT_A_MATCH."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_AGE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=30,
            expected_value=">= 18",
            explanation="Age requirement met.",
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_PRIOR_THERAPY",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.FAIL,
            observed_value="Prior anti-PD-1 immunotherapy received",
            expected_value="No prior immunotherapy",
            explanation="Patient received prior pembrolizumab, violating exclusion criteria.",
            evidence=EvidenceProvenance(
                source="EHR_Medications",
                field_name="medication_history",
                extracted_value="Pembrolizumab 200mg",
            ),
            agent_id="medications_agent",
        ),
    ]

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    assert status == OverallStatus.NOT_A_MATCH
    assert review_needed is False
    assert counts.mandatory_failed == 1
    assert any("CRIT_PRIOR_THERAPY" in r and "failed" in r for r in reasons)


def test_unknown_required_information(engine: DeterministicDecisionEngine):
    """Test 3: Any required/mandatory criterion with status UNKNOWN results in REQUIRES_REVIEW."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_AGE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=55,
            expected_value=">= 18",
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_EGFR_MUTATION",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.UNKNOWN,
            observed_value=None,
            expected_value="EGFR Exon 19 del or L858R",
            explanation="Molecular lab panel has not completed yet; EGFR status unknown.",
            agent_id="labs_agent",
        ),
    ]

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    assert status == OverallStatus.REQUIRES_REVIEW
    assert review_needed is True
    assert counts.mandatory_unknown == 1
    assert any("CRIT_EGFR_MUTATION" in r and "UNKNOWN" in r for r in reasons)


def test_empty_results(engine: DeterministicDecisionEngine):
    """Test 4: Empty results must never silently count as PASS and result in REQUIRES_REVIEW."""
    criteria = []

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    assert status == OverallStatus.REQUIRES_REVIEW
    assert review_needed is True
    assert counts.total_criteria == 0
    assert counts.mandatory_total == 0
    assert any("empty" in r.lower() or "no mandatory" in r.lower() for r in reasons)


def test_mandatory_failure_combined_with_unknown_result(engine: DeterministicDecisionEngine):
    """Test 10: A definitive mandatory failure combined with an unknown result results in NOT_A_MATCH."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_AGE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.FAIL,
            observed_value=16,
            expected_value=">= 18",
            explanation="Patient is pediatric (16yo), trial requires adults >= 18.",
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_LAB_CREATININE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.UNKNOWN,
            observed_value=None,
            expected_value="Serum creatinine <= 1.5 mg/dL",
            explanation="Creatinine test not found in recent records.",
            agent_id="labs_agent",
        ),
    ]

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    # Definitive failure takes precedence over unknown
    assert status == OverallStatus.NOT_A_MATCH
    assert review_needed is False
    assert counts.mandatory_failed == 1
    assert counts.mandatory_unknown == 1
    assert any("CRIT_AGE" in r and "failed" in r for r in reasons)
    assert any("UNKNOWN" in r and "NOT_A_MATCH" in r for r in reasons)


def test_optional_criterion_unknown_does_not_block_potential_match(
    engine: DeterministicDecisionEngine,
):
    """Test 11: Optional criteria that are UNKNOWN do not block a valid mandatory POTENTIAL_MATCH."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_MANDATORY_AGE",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=50,
            expected_value=">= 18",
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_OPTIONAL_BIOMARKER",
            criterion_type=CriterionType.OPTIONAL,
            status=CriterionStatus.UNKNOWN,
            observed_value=None,
            expected_value="PD-L1 Expression >= 50%",
            explanation="Biomarker test is exploratory/secondary.",
            agent_id="biomarker_agent",
        ),
    ]

    status, review_needed, reasons, counts = engine.evaluate(criteria)

    assert status == OverallStatus.POTENTIAL_MATCH
    assert review_needed is False
    assert counts.mandatory_passed == 1
    assert counts.optional_unknown == 1
    assert any("All mandatory criteria passed" in r for r in reasons)
    assert any("Optional criterion 'CRIT_OPTIONAL_BIOMARKER' is UNKNOWN" in r for r in reasons)
