"""Comprehensive unit and integration tests for ClinicalAgentsAdapter."""

from datetime import date
from unittest.mock import patch
import pandas as pd
import pytest

from src.agents.adapter import (
    ClinicalAgentsAdapter,
    DatasetUnavailableError,
    _sanitize_criterion_id,
)
from src.matching.coordinator import EligibilityCoordinator
from src.matching.schema import (
    AgentExecutionStatus,
    AgentResult,
    CriterionResult,
    CriterionStatus,
    CriterionType,
    OverallStatus,
    ScreeningReport,
)


@pytest.fixture
def synthetic_patients_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "patient_id": "P_ELIGIBLE",
                "birth_date": "1985-06-15",
                "gender": "F",
            },
            {
                "patient_id": "P_UNDERAGE",
                "birth_date": "2015-01-01",
                "gender": "M",
            },
            {
                "patient_id": "P_OVERAGE",
                "birth_date": "1930-01-01",
                "gender": "F",
            },
            {
                "patient_id": "P_NO_DOB",
                "birth_date": None,
                "gender": "M",
            },
        ]
    )


@pytest.fixture
def synthetic_conditions_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"patient_id": "P_ELIGIBLE", "condition": "Type 2 diabetes mellitus"},
            {"patient_id": "P_EXCLUDED", "condition": "Type 2 diabetes mellitus"},
            {"patient_id": "P_EXCLUDED", "condition": "Heart failure"},
            {"patient_id": "P_OTHER_COND", "condition": "Hypertension"},
        ]
    )


@pytest.fixture
def synthetic_observations_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "patient_id": "P_ELIGIBLE",
                "observation": "Hemoglobin A1c",
                "value": 7.4,
                "units": "%",
                "observation_date": "2024-03-01",
            },
            {
                "patient_id": "P_HIGH_LAB",
                "observation": "Hemoglobin A1c",
                "value": 9.8,
                "units": "%",
                "observation_date": "2024-03-01",
            },
            {
                "patient_id": "P_WRONG_UNIT",
                "observation": "Hemoglobin A1c",
                "value": 55.0,
                "units": "mmol/mol",
                "observation_date": "2024-03-01",
            },
        ]
    )


@pytest.fixture
def synthetic_trials() -> list:
    return [
        {
            "nct_id": "NCT001",
            "trial_id": "NCT001",
            "minimum_age": "18 Years",
            "maximum_age": "75 Years",
            "source": "TrialRegistry_Mock",
        },
        {
            "nct_id": "NCT_NO_AGE",
            "trial_id": "NCT_NO_AGE",
            "minimum_age": None,
            "maximum_age": None,
            "source": "TrialRegistry_Mock",
        },
    ]


@pytest.fixture
def configured_adapter(
    synthetic_patients_df,
    synthetic_conditions_df,
    synthetic_observations_df,
    synthetic_trials,
) -> ClinicalAgentsAdapter:
    return ClinicalAgentsAdapter(
        patients=synthetic_patients_df,
        conditions=synthetic_conditions_df,
        observations=synthetic_observations_df,
        trials=synthetic_trials,
    )


# =============================================================================
# 1. Individual Implemented Agent Output Shape & Conversion Tests
# =============================================================================


def test_age_agent_pass(configured_adapter):
    """Eligible patient should pass age requirements with stable criterion ID."""
    result = configured_adapter.run_age_agent("P_ELIGIBLE", "NCT001")
    assert result.agent_id == "age_agent"
    assert result.status == AgentExecutionStatus.SUCCESS
    assert len(result.criteria_results) == 1

    crit = result.criteria_results[0]
    assert crit.criterion_id == "CRIT_AGE"
    assert crit.criterion_type == CriterionType.MANDATORY
    assert crit.status == CriterionStatus.PASS
    assert crit.observed_value is not None
    assert crit.evidence is not None
    assert crit.evidence.source == "TrialRegistry_Mock"


def test_age_agent_fail(configured_adapter):
    """Underage patient should fail age requirements."""
    result = configured_adapter.run_age_agent("P_UNDERAGE", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.FAIL
    assert crit.criterion_type == CriterionType.MANDATORY


def test_diagnosis_agent_pass(configured_adapter):
    """Patient with documented Type 2 Diabetes should pass diagnosis inclusion."""
    result = configured_adapter.run_diagnosis_agent("P_ELIGIBLE", "NCT001")
    assert result.agent_id == "diagnosis_agent"
    assert result.status == AgentExecutionStatus.SUCCESS
    assert len(result.criteria_results) == 1

    crit = result.criteria_results[0]
    assert crit.criterion_id == "CRIT_DIAGNOSIS_TYPE_2_DIABETES"
    assert crit.status == CriterionStatus.PASS
    assert crit.criterion_type == CriterionType.MANDATORY
    assert crit.evidence is not None
    assert "Type 2 diabetes" in str(crit.observed_value)


def test_diagnosis_agent_unknown_when_absent(configured_adapter):
    """Patient without documented condition should yield UNKNOWN, not FAIL."""
    result = configured_adapter.run_diagnosis_agent("P_OTHER_COND", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.UNKNOWN


def test_lab_agent_pass(configured_adapter):
    """Patient with HbA1c <= 8.0% should pass lab criteria."""
    result = configured_adapter.run_lab_agent("P_ELIGIBLE", "NCT001")
    assert result.agent_id == "lab_agent"
    assert result.status == AgentExecutionStatus.SUCCESS
    assert len(result.criteria_results) == 1

    crit = result.criteria_results[0]
    assert crit.criterion_id == "CRIT_LAB_HBA1C"
    assert crit.status == CriterionStatus.PASS
    assert "7.4" in str(crit.observed_value)


def test_lab_agent_fail(configured_adapter):
    """Patient with HbA1c > 8.0% should fail lab threshold."""
    result = configured_adapter.run_lab_agent("P_HIGH_LAB", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.FAIL


def test_lab_agent_unit_mismatch(configured_adapter):
    """Lab result with mismatched unit must yield UNKNOWN, not PASS or FAIL."""
    result = configured_adapter.run_lab_agent("P_WRONG_UNIT", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.UNKNOWN


def test_exclusion_agent_fail(configured_adapter):
    """Patient with documented Heart Failure must FAIL exclusion criterion."""
    result = configured_adapter.run_exclusion_agent("P_EXCLUDED", "NCT001")
    assert result.agent_id == "exclusion_agent"
    assert result.status == AgentExecutionStatus.SUCCESS
    assert len(result.criteria_results) == 1

    crit = result.criteria_results[0]
    assert crit.criterion_id == "CRIT_EXCLUSION_HEART_FAILURE"
    assert crit.status == CriterionStatus.FAIL


def test_exclusion_agent_unknown_when_no_record(configured_adapter):
    """Patient with no record of Heart Failure yields UNKNOWN (absence of record != absence of disease)."""
    result = configured_adapter.run_exclusion_agent("P_ELIGIBLE", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.UNKNOWN


# =============================================================================
# 2. Clinical Safety & Status Mapping Rules
# =============================================================================


def test_status_mapping_safety():
    """Verify strictly enforced status conversion rules."""
    assert ClinicalAgentsAdapter._map_status("PASS") == (CriterionStatus.PASS, False)
    assert ClinicalAgentsAdapter._map_status("FAIL") == (CriterionStatus.FAIL, False)
    assert ClinicalAgentsAdapter._map_status("NOT_APPLICABLE") == (
        CriterionStatus.UNKNOWN,
        True,
    )
    assert ClinicalAgentsAdapter._map_status("UNKNOWN") == (
        CriterionStatus.UNKNOWN,
        False,
    )
    assert ClinicalAgentsAdapter._map_status("gibberish") == (
        CriterionStatus.UNKNOWN,
        False,
    )
    assert ClinicalAgentsAdapter._map_status(None) == (CriterionStatus.UNKNOWN, False)


def test_not_applicable_age_is_conservative_unknown(configured_adapter):
    """
    CRITICAL SAFETY RULE: NOT_APPLICABLE must never map to PASS.
    When a trial specifies no age criteria, it must map to UNKNOWN (OPTIONAL)
    with clear documentation of the canonical schema limitation.
    """
    result = configured_adapter.run_age_agent("P_ELIGIBLE", "NCT_NO_AGE")
    assert result.status == AgentExecutionStatus.SUCCESS
    assert len(result.criteria_results) == 1

    crit = result.criteria_results[0]
    assert crit.status == CriterionStatus.UNKNOWN
    assert crit.criterion_type == CriterionType.OPTIONAL
    assert "NOT_APPLICABLE" in crit.explanation
    assert "canonical schema limitation" in crit.explanation.lower()


# =============================================================================
# 3. Stable Criterion Identifiers
# =============================================================================


def test_stable_criterion_ids():
    """Ensure sanitized criterion IDs are deterministic, uppercase, and alphanumeric."""
    assert _sanitize_criterion_id("CRIT_AGE", "") == "CRIT_AGE"
    assert (
        _sanitize_criterion_id("CRIT_DIAGNOSIS", "Type 2 Diabetes Mellitus")
        == "CRIT_DIAGNOSIS_TYPE_2_DIABETES_MELLITUS"
    )
    assert (
        _sanitize_criterion_id("CRIT_LAB", "Hemoglobin A1c (HbA1c)")
        == "CRIT_LAB_HEMOGLOBIN_A1C_HBA1C"
    )
    assert (
        _sanitize_criterion_id("CRIT_EXCLUSION", "Congestive Heart Failure / CAD")
        == "CRIT_EXCLUSION_CONGESTIVE_HEART_FAILURE_CAD"
    )


# =============================================================================
# 4. Evidence and Provenance Preservation
# =============================================================================


def test_evidence_provenance_preservation(configured_adapter):
    """Audit trail and provenance must be fully retained in CriterionResult."""
    result = configured_adapter.run_age_agent("P_ELIGIBLE", "NCT001")
    crit = result.criteria_results[0]
    assert crit.evidence is not None
    assert crit.evidence.source == "TrialRegistry_Mock"
    assert crit.evidence.field_name == "Age limits"
    assert crit.evidence.extracted_value is not None


# =============================================================================
# 5. Missing Patient or Trial Data
# =============================================================================


def test_missing_patient_id(configured_adapter):
    """Missing patient record must return UNKNOWN, not crash or claim PASS."""
    result = configured_adapter.run_age_agent("NON_EXISTENT_ID", "NCT001")
    assert result.status == AgentExecutionStatus.SUCCESS
    assert result.criteria_results[0].status == CriterionStatus.UNKNOWN


def test_missing_trial_id(configured_adapter):
    """Missing trial specification must return UNKNOWN, not crash."""
    result = configured_adapter.run_age_agent("P_ELIGIBLE", "NON_EXISTENT_TRIAL")
    assert result.status == AgentExecutionStatus.SUCCESS
    assert result.criteria_results[0].status == CriterionStatus.UNKNOWN


# =============================================================================
# 6. Missing Optional Datasets
# =============================================================================


def test_missing_datasets_without_injection_raises_error(tmp_path):
    """Adapter created without datasets must raise DatasetUnavailableError when accessing missing files."""
    adapter = ClinicalAgentsAdapter(data_dir=tmp_path / "empty_dir")
    with pytest.raises(DatasetUnavailableError):
        adapter._ensure_patients_loaded()

    # Diagnosis agent handles the error safely into AgentExecutionStatus.ERROR
    diag_result = adapter.run_diagnosis_agent("P_ELIGIBLE", "NCT001")
    assert diag_result.status == AgentExecutionStatus.ERROR
    assert "DatasetUnavailableError" in diag_result.error_message or "unavailable" in diag_result.error_message.lower()


# =============================================================================
# 7. Malformed Agent Output & Unhandled Exceptions
# =============================================================================


def test_agent_raising_exception_handled_safely(configured_adapter):
    """If an agent throws an unexpected exception, it must return AgentExecutionStatus.ERROR."""
    with patch("src.agents.adapter.evaluate_age", side_effect=RuntimeError("Simulated engine fault")):
        result = configured_adapter.run_age_agent("P_ELIGIBLE", "NCT001")
        assert result.agent_id == "age_agent"
        assert result.status == AgentExecutionStatus.ERROR
        assert "Simulated engine fault" in result.error_message


# =============================================================================
# 8. Unsupported Criteria Never Reported as Passed
# =============================================================================


def test_unsupported_criteria_never_pass(synthetic_patients_df, synthetic_trials):
    """
    CRITICAL CLINICAL SAFETY RULE: Unimplemented criteria (medications, pregnancy, etc.)
    must never be inferred or reported as PASS.
    """
    custom_specs = {
        "NCT_MED": {
            "unsupported_criteria": [
                "Metformin usage >= 3 months",
                "History of bariatric surgery",
            ]
        }
    }
    adapter = ClinicalAgentsAdapter(
        patients=synthetic_patients_df,
        trials=synthetic_trials,
        criteria_specs=custom_specs,
    )

    unsupported_result = adapter.run_unsupported_criteria("P_ELIGIBLE", "NCT_MED")
    assert unsupported_result.status == AgentExecutionStatus.SUCCESS
    assert len(unsupported_result.criteria_results) == 2

    for crit in unsupported_result.criteria_results:
        assert crit.status == CriterionStatus.UNKNOWN
        assert crit.status != CriterionStatus.PASS
        assert crit.criterion_type == CriterionType.MANDATORY
        assert "cannot be inferred as pass" in crit.explanation.lower()


# =============================================================================
# 9. Real Integration Test with EligibilityCoordinator
# =============================================================================


def test_full_coordinator_integration_eligible_patient(configured_adapter):
    """
    End-to-end integration: Run adapter runners through EligibilityCoordinator.
    A patient satisfying all criteria should be screened without contract errors.
    """
    coordinator = EligibilityCoordinator()
    runners = configured_adapter.as_runners_dict()

    report: ScreeningReport = coordinator.evaluate_with_agents(
        patient_id="P_ELIGIBLE",
        trial_id="NCT001",
        agents_to_run=runners,
    )

    assert isinstance(report, ScreeningReport)
    assert report.patient_id == "P_ELIGIBLE"
    assert report.trial_id == "NCT001"
    assert report.counts.total_criteria >= 3
    assert report.counts.passed == 3
    assert report.counts.unknown == 1

    # Age passed, Diagnosis passed, Lab passed.
    # Exclusion returned UNKNOWN (absence of condition != proof of absence), so human review is required.
    assert report.overall_status in {OverallStatus.POTENTIAL_MATCH, OverallStatus.REQUIRES_REVIEW}
    assert report.counts.mandatory_failed == 0


def test_full_coordinator_integration_failing_patient(configured_adapter):
    """
    End-to-end integration: Patient failing age should definitively receive NOT_A_MATCH.
    """
    coordinator = EligibilityCoordinator()
    runners = configured_adapter.as_runners_dict()

    report: ScreeningReport = coordinator.evaluate_with_agents(
        patient_id="P_UNDERAGE",
        trial_id="NCT001",
        agents_to_run=runners,
    )

    assert report.overall_status == OverallStatus.NOT_A_MATCH
    assert report.counts.mandatory_failed >= 1
    assert any("CRIT_AGE" in r for r in report.reasons)
