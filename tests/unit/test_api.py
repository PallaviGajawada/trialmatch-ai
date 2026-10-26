"""Unit tests for FastAPI backend endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, create_app
from src.api.dependencies import get_coordinator
from src.matching.coordinator import EligibilityCoordinator
from src.matching.decision_rules import DeterministicDecisionEngine
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
def client() -> TestClient:
    """Create test client with fresh clean dependency state."""
    app.dependency_overrides.clear()
    return TestClient(app)


def test_health_endpoint_unconfigured_agents(client: TestClient):
    """Test 1a: GET /health returns expected response and reports unconfigured agents."""
    unconfigured_coordinator = EligibilityCoordinator(
        decision_engine=DeterministicDecisionEngine()
    )
    app.dependency_overrides[get_coordinator] = lambda: unconfigured_coordinator

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "trialmatch-ai-backend"
    assert data["agents_configured"] is False
    assert data["pipeline_status"] == "agents_unconfigured_pipeline_incomplete"
    assert data["registered_agents"] == []


def test_health_endpoint_configured_agents(client: TestClient):
    """Test 1b: GET /health accurately reflects configured agent runners."""
    configured_coordinator = EligibilityCoordinator(
        registered_agents={"demographics_agent": lambda p, t: None}
    )
    app.dependency_overrides[get_coordinator] = lambda: configured_coordinator

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["agents_configured"] is True
    assert data["pipeline_status"] == "operational"
    assert data["registered_agents"] == ["demographics_agent"]


def test_missing_patient_id_rejected(client: TestClient):
    """Test 3a: Request missing patient_id is rejected with 422."""
    response = client.post("/api/v1/evaluate", json={"trial_id": "NCT05001234"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_empty_patient_id_rejected(client: TestClient):
    """Test 3b: Empty or whitespace patient_id is rejected with 422."""
    response = client.post(
        "/api/v1/evaluate", json={"patient_id": "   ", "trial_id": "NCT05001234"}
    )
    assert response.status_code == 422


def test_missing_trial_id_rejected(client: TestClient):
    """Test 3c: Request missing trial_id is rejected with 422."""
    response = client.post("/api/v1/evaluate", json={"patient_id": "PATIENT_001"})
    assert response.status_code == 422


def test_invalid_request_types_rejected(client: TestClient):
    """Test 4: Invalid request types or malformed payloads are rejected with 422."""
    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": 12345, "trial_id": ["not_a_string"]},
    )
    assert response.status_code == 422


def test_evaluate_unconfigured_agents_reports_incomplete(client: TestClient):
    """Test 8a: Without configured agents or pre-collected results, report indicates incomplete evaluation."""
    unconfigured_coordinator = EligibilityCoordinator()
    app.dependency_overrides[get_coordinator] = lambda: unconfigured_coordinator

    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": "PATIENT_UNCONFIG", "trial_id": "NCT05001234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "PATIENT_UNCONFIG"
    assert data["trial_id"] == "NCT05001234"
    assert data["overall_status"] == OverallStatus.REQUIRES_REVIEW.value
    assert data["requires_human_review"] is True
    assert any("no eligibility agents are currently registered" in r for r in data["reasons"])


def test_mocked_potential_match_returned_correctly(client: TestClient):
    """Test 5: A mocked potential-match result is returned correctly with structured report."""
    def mock_demographics(p_id: str, t_id: str) -> AgentResult:
        return AgentResult(
            agent_id="demographics_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_AGE",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.PASS,
                    observed_value=42,
                    expected_value=">= 18",
                    explanation="Age is 42.",
                    evidence=EvidenceProvenance(
                        source="EHR",
                        field_name="birth_date",
                    ),
                )
            ],
        )

    mock_coordinator = EligibilityCoordinator(
        registered_agents={"demographics_agent": mock_demographics}
    )
    app.dependency_overrides[get_coordinator] = lambda: mock_coordinator

    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": "PATIENT_MATCH", "trial_id": "NCT05001234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == OverallStatus.POTENTIAL_MATCH.value
    assert data["requires_human_review"] is False
    assert data["counts"]["mandatory_passed"] == 1
    assert data["counts"]["mandatory_failed"] == 0
    assert len(data["criterion_results"]) == 1
    assert data["criterion_results"][0]["status"] == "PASS"
    assert data["criterion_results"][0]["evidence"]["source"] == "EHR"


def test_mocked_not_a_match_returned_correctly(client: TestClient):
    """Test 6: A mocked not-a-match result is returned correctly."""
    def mock_exclusion(p_id: str, t_id: str) -> AgentResult:
        return AgentResult(
            agent_id="exclusion_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_PRIOR_THERAPY",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.FAIL,
                    observed_value="Prior Immunotherapy",
                    expected_value="None",
                    explanation="Violates exclusion criteria.",
                )
            ],
        )

    mock_coordinator = EligibilityCoordinator(
        registered_agents={"exclusion_agent": mock_exclusion}
    )
    app.dependency_overrides[get_coordinator] = lambda: mock_coordinator

    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": "PATIENT_NOT_MATCH", "trial_id": "NCT05001234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == OverallStatus.NOT_A_MATCH.value
    assert data["requires_human_review"] is False
    assert data["counts"]["mandatory_failed"] == 1
    assert any("CRIT_PRIOR_THERAPY" in r and "failed" in r for r in data["reasons"])


def test_mocked_unknown_criteria_results_in_requires_review(client: TestClient):
    """Test 7: Unknown criteria result in REQUIRES_REVIEW."""
    def mock_labs(p_id: str, t_id: str) -> AgentResult:
        return AgentResult(
            agent_id="labs_agent",
            criteria_results=[
                CriterionResult(
                    criterion_id="CRIT_BIOMARKER",
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.UNKNOWN,
                    observed_value=None,
                    expected_value="Positive",
                    explanation="Test pending.",
                )
            ],
        )

    mock_coordinator = EligibilityCoordinator(
        registered_agents={"labs_agent": mock_labs}
    )
    app.dependency_overrides[get_coordinator] = lambda: mock_coordinator

    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": "PATIENT_UNKNOWN", "trial_id": "NCT05001234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == OverallStatus.REQUIRES_REVIEW.value
    assert data["requires_human_review"] is True
    assert data["counts"]["mandatory_unknown"] == 1


def test_internal_exception_details_not_exposed(client: TestClient):
    """Test 9: Internal exception details are not leaked to the client (clean HTTP 500)."""
    class CrashingCoordinator:
        def evaluate(self, *args, **kwargs):
            raise RuntimeError("Database connection string postgres://secret_user:secret_pass@db.internal:5432")

        def evaluate_with_agents(self, *args, **kwargs):
            raise RuntimeError("Database connection string postgres://secret_user:secret_pass@db.internal:5432")

        @property
        def registered_agents(self):
            return {"crashing_agent": lambda p, t: None}

    app.dependency_overrides[get_coordinator] = lambda: CrashingCoordinator()

    response = client.post(
        "/api/v1/evaluate",
        json={"patient_id": "PATIENT_ERR", "trial_id": "NCT05001234"},
    )
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    # Sensitive connection string and internal traceback must NOT be present
    assert "secret_pass" not in response.text
    assert "Traceback" not in response.text
    assert "postgres" not in response.text


def test_evaluate_with_pre_collected_agent_results(client: TestClient):
    """Test 2: Valid evaluation requests with pre-collected results return expected report."""
    payload = {
        "patient_id": "PATIENT_PRE_COLLECTED",
        "trial_id": "NCT05001234",
        "agent_results": [
            {
                "agent_id": "demographics_agent",
                "status": "SUCCESS",
                "criteria_results": [
                    {
                        "criterion_id": "CRIT_AGE",
                        "criterion_type": "MANDATORY",
                        "status": "PASS",
                        "observed_value": 30,
                        "expected_value": ">= 18",
                        "explanation": "Valid age.",
                    }
                ],
            }
        ],
    }

    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == OverallStatus.POTENTIAL_MATCH.value
    assert data["counts"]["mandatory_passed"] == 1
