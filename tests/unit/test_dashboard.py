"""Unit tests for the Streamlit dashboard API client and presentation utilities."""

import pytest
import httpx
from unittest.mock import MagicMock, patch

from src.dashboard.api_client import (
    BackendConnectionError,
    BackendHttpError,
    BackendResponseError,
    BackendTimeoutError,
    TrialMatchApiClient,
)
from src.dashboard.presentation import (
    format_evidence_provenance,
    format_status_badge,
    prepare_criteria_table_data,
    summarize_review_items,
)
from src.matching.schema import (
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    EvaluationCounts,
    OverallStatus,
    ScreeningReport,
)


@pytest.fixture
def sample_report_payload() -> dict:
    return {
        "patient_id": "SYNTH_PAT_001",
        "trial_id": "NCT05001234",
        "overall_status": "POTENTIAL_MATCH",
        "requires_human_review": False,
        "reasons": ["All mandatory criteria passed (1/1)."],
        "counts": {
            "total_criteria": 1,
            "passed": 1,
            "failed": 0,
            "unknown": 0,
            "mandatory_total": 1,
            "mandatory_passed": 1,
            "mandatory_failed": 0,
            "mandatory_unknown": 0,
            "optional_total": 0,
            "optional_passed": 0,
            "optional_failed": 0,
            "optional_unknown": 0,
        },
        "criterion_results": [
            {
                "criterion_id": "CRIT_AGE",
                "name": "Minimum Age",
                "criterion_type": "MANDATORY",
                "status": "PASS",
                "observed_value": 45,
                "expected_value": ">= 18",
                "explanation": "Age criterion met.",
                "evidence": {
                    "source": "EHR",
                    "field_name": "birth_date",
                    "extracted_value": "1981-05-12",
                },
                "agent_id": "demographics_agent",
            }
        ],
        "missing_agents": [],
        "missing_criteria": [],
        "errors": [],
        "timestamp": "2026-10-26T21:00:00+00:00",
    }


# =====================================================================
# API Client Tests
# =====================================================================

def test_api_client_successful_evaluation(sample_report_payload: dict):
    """Test 1: Successful API response deserializes into ScreeningReport."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_report_payload

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        report = client.evaluate("SYNTH_PAT_001", "NCT05001234")

    assert isinstance(report, ScreeningReport)
    assert report.patient_id == "SYNTH_PAT_001"
    assert report.overall_status == OverallStatus.POTENTIAL_MATCH
    assert report.requires_human_review is False
    assert len(report.criterion_results) == 1


def test_api_client_all_three_statuses(sample_report_payload: dict):
    """Test 2: Evaluates all three overall statuses correctly."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    for test_status in [
        OverallStatus.POTENTIAL_MATCH,
        OverallStatus.NOT_A_MATCH,
        OverallStatus.REQUIRES_REVIEW,
    ]:
        payload = dict(sample_report_payload)
        payload["overall_status"] = test_status.value
        payload["requires_human_review"] = test_status == OverallStatus.REQUIRES_REVIEW

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload

        with patch.object(httpx.Client, "post", return_value=mock_resp):
            report = client.evaluate("PATIENT_X", "TRIAL_Y")

        assert report.overall_status == test_status


def test_api_client_connection_failure():
    """Test 5: Backend connection error raises BackendConnectionError."""
    client = TrialMatchApiClient(base_url="http://unreachable-backend:8000")

    with patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        with pytest.raises(BackendConnectionError) as exc_info:
            client.evaluate("P1", "T1")

    assert "Unable to connect" in str(exc_info.value)


def test_api_client_timeout():
    """Test timeout: Request timeout raises BackendTimeoutError."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    with patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.TimeoutException("Timed out"),
    ):
        with pytest.raises(BackendTimeoutError) as exc_info:
            client.evaluate("P1", "T1")

    assert "timed out" in str(exc_info.value)


def test_api_client_http_error_response():
    """Test 6: HTTP error response raises BackendHttpError."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.json.return_value = {"detail": "Request validation failed for patient_id."}

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(BackendHttpError) as exc_info:
            client.evaluate("", "T1")

    assert exc_info.value.status_code == 422
    assert "Request validation failed" in exc_info.value.detail


def test_api_client_malformed_backend_response():
    """Test 7: Malformed backend payload raises BackendResponseError."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"invalid_key": "not a report"}

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(BackendResponseError) as exc_info:
            client.evaluate("P1", "T1")

    assert "malformed" in str(exc_info.value).lower()


def test_api_client_health_check_states():
    """Test 8: Health check accurately reports agent configuration state."""
    client = TrialMatchApiClient(base_url="http://mock-backend:8000")

    # Unconfigured state
    mock_unconfigured = MagicMock()
    mock_unconfigured.status_code = 200
    mock_unconfigured.json.return_value = {
        "status": "ok",
        "agents_configured": False,
        "pipeline_status": "agents_unconfigured_pipeline_incomplete",
    }
    with patch.object(httpx.Client, "get", return_value=mock_unconfigured):
        data = client.check_health()
    assert data["agents_configured"] is False

    # Configured state
    mock_configured = MagicMock()
    mock_configured.status_code = 200
    mock_configured.json.return_value = {
        "status": "ok",
        "agents_configured": True,
        "pipeline_status": "operational",
    }
    with patch.object(httpx.Client, "get", return_value=mock_configured):
        data = client.check_health()
    assert data["agents_configured"] is True


# =====================================================================
# Presentation & Formatting Tests
# =====================================================================

def test_display_preparation_criteria_table_data():
    """Test 9: Prepares criterion-level results for tabular display."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_AGE",
            name="Age Requirement",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=45,
            expected_value=">= 18",
            explanation="Meets age threshold.",
            evidence=EvidenceProvenance(source="EHR", field_name="dob"),
            agent_id="demographics_agent",
        ),
        CriterionResult(
            criterion_id="CRIT_PRIOR_MEDS",
            name="No Prior Immunotherapy",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.FAIL,
            observed_value="Pembrolizumab",
            expected_value="None",
            explanation="Received pembrolizumab.",
            agent_id="medications_agent",
        ),
    ]

    rows = prepare_criteria_table_data(criteria)
    assert len(rows) == 2

    row1 = rows[0]
    assert row1["Criterion ID"] == "CRIT_AGE"
    assert row1["Status"] == "✓ PASS"
    assert row1["Type"] == "Mandatory"
    assert row1["Observed Value"] == "45"
    assert "Source: EHR" in row1["Provenance Citation"]

    row2 = rows[1]
    assert row2["Criterion ID"] == "CRIT_PRIOR_MEDS"
    assert row2["Status"] == "✗ FAIL"
    assert row2["Observed Value"] == "Pembrolizumab"


def test_display_preparation_empty_criteria_results():
    """Test 3: Empty criterion results produce an empty table list without errors."""
    rows = prepare_criteria_table_data([])
    assert rows == []


def test_display_preparation_missing_evidence_and_unknown():
    """Test 4: Handles missing evidence and UNKNOWN values gracefully."""
    criteria = [
        CriterionResult(
            criterion_id="CRIT_LAB_EGFR",
            name="EGFR Panel",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.UNKNOWN,
            observed_value=None,
            expected_value="Exon 19 del",
            explanation="Test pending.",
            evidence=None,
            agent_id="labs_agent",
        )
    ]

    rows = prepare_criteria_table_data(criteria)
    assert len(rows) == 1
    row = rows[0]
    assert row["Status"] == "❓ UNKNOWN"
    assert row["Observed Value"] == "(Unrecorded)"
    assert row["Provenance Citation"] == "No provenance citation recorded"


def test_format_status_badge():
    """Verify accessible status badge formatting for all statuses."""
    b_match = format_status_badge(OverallStatus.POTENTIAL_MATCH)
    assert "POTENTIAL MATCH" in b_match["label"]
    assert b_match["icon"] == "✓"
    assert "[ MATCH ]" in b_match["symbol"]

    b_no_match = format_status_badge(OverallStatus.NOT_A_MATCH)
    assert "NOT A MATCH" in b_no_match["label"]
    assert b_no_match["icon"] == "✗"

    b_review = format_status_badge(OverallStatus.REQUIRES_REVIEW)
    assert "REQUIRES REVIEW" in b_review["label"]
    assert b_review["icon"] == "⚠"


def test_summarize_review_items():
    """Verify categorization of review reasons and failure highlights."""
    report = ScreeningReport(
        patient_id="P1",
        trial_id="T1",
        overall_status=OverallStatus.REQUIRES_REVIEW,
        requires_human_review=True,
        reasons=["Mandatory criterion failed.", "Biomarker is unknown."],
        counts=EvaluationCounts(),
        criterion_results=[
            CriterionResult(
                criterion_id="CRIT_FAIL",
                criterion_type=CriterionType.MANDATORY,
                status=CriterionStatus.FAIL,
                observed_value="Stage I",
                expected_value="Stage IV",
                explanation="Not metastatic.",
            ),
            CriterionResult(
                criterion_id="CRIT_UNK",
                criterion_type=CriterionType.MANDATORY,
                status=CriterionStatus.UNKNOWN,
                explanation="Lab missing.",
            ),
        ],
        missing_agents=["pathology_agent"],
        errors=["Network glitch during test"],
    )

    summary = summarize_review_items(report)
    assert len(summary["reasons"]) == 2
    assert len(summary["mandatory_failures"]) == 1
    assert "CRIT_FAIL" in summary["mandatory_failures"][0]
    assert len(summary["unknown_criteria"]) == 1
    assert "CRIT_UNK" in summary["unknown_criteria"][0]
    assert summary["missing_agents"] == ["pathology_agent"]
    assert summary["errors"] == ["Network glitch during test"]
