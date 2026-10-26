# TrialMatch AI — Component 3: FastAPI Backend

## Overview

The **TrialMatch AI FastAPI Backend** (`src.api.app`) provides a RESTful interface for clinical trial eligibility screening. It serves as the bridge between user interfaces (such as future dashboards) and the underlying deterministic orchestration engine (`EligibilityCoordinator`).

---

## 1. Local Setup and Running the Server

### Prerequisites
Install all backend dependencies:
```bash
pip install -r requirements.txt
```

### Starting the Application
You can start the backend locally using `uvicorn`:

```bash
# Standard uvicorn execution with live reload
uvicorn src.api.app:app --reload

# Module syntax execution
uvicorn src.api.app --reload

# Direct python execution
python -m src.api.app
```

The server binds to `http://127.0.0.1:8000` by default.

### Interactive API Documentation
FastAPI provides automatic interactive OpenAPI documentation:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 2. API Endpoints

### 2.1 Health Check: `GET /health`
Returns the operational and readiness status of the backend service.

> **Safety Notice**: The health check does not claim the eligibility pipeline is operational if real agents have not yet been configured.

#### Response Schema (`HealthResponse`)
```json
{
  "status": "ok",
  "service": "trialmatch-ai-backend",
  "version": "1.0.0",
  "agents_configured": false,
  "pipeline_status": "agents_unconfigured_pipeline_incomplete",
  "registered_agents": []
}
```

#### Example cURL
```bash
curl -X GET "http://127.0.0.1:8000/health"
```

---

### 2.2 Evaluate Eligibility: `POST /api/v1/evaluate`
Accepts a target `patient_id` and `trial_id`, evaluates protocol criteria via the coordinator, and returns an auditable `ScreeningReport`.

#### Request Schema (`EvaluationRequest`)
| Field | Type | Required | Description |
|---|---|---|---|
| `patient_id` | `str` | Yes | Non-empty unique patient identifier. |
| `trial_id` | `str` | Yes | Non-empty clinical trial identifier (e.g. `NCT05001234`). |
| `agent_results` | `List[AgentResult]` | No | Optional pre-collected agent findings. If omitted, the coordinator executes registered agent runners. |
| `required_agents` | `List[str]` | No | Optional list of agent IDs that must report. |
| `required_criteria` | `List[str]` | No | Optional list of criterion IDs that must be evaluated. |

#### Request Example (Evaluating with Pre-collected Agent Findings)
```json
{
  "patient_id": "SYNTH_PATIENT_001",
  "trial_id": "NCT05001234",
  "agent_results": [
    {
      "agent_id": "demographics_agent",
      "status": "SUCCESS",
      "criteria_results": [
        {
          "criterion_id": "CRIT_AGE",
          "name": "Age Requirement",
          "criterion_type": "MANDATORY",
          "status": "PASS",
          "observed_value": 45,
          "expected_value": ">= 18",
          "explanation": "Patient age 45 meets minimum trial age of 18.",
          "evidence": {
            "source": "EHR_Demographics",
            "field_name": "birth_date",
            "extracted_value": "1981-05-12"
          }
        }
      ]
    }
  ]
}
```

#### Response Schema (`ScreeningReport`)
```json
{
  "patient_id": "SYNTH_PATIENT_001",
  "trial_id": "NCT05001234",
  "overall_status": "POTENTIAL_MATCH",
  "requires_human_review": false,
  "reasons": [
    "All mandatory criteria passed (1/1)."
  ],
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
    "optional_unknown": 0
  },
  "criterion_results": [
    {
      "criterion_id": "CRIT_AGE",
      "name": "Age Requirement",
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 45,
      "expected_value": ">= 18",
      "explanation": "Patient age 45 meets minimum trial age of 18.",
      "evidence": {
        "source": "EHR_Demographics",
        "document_id": null,
        "field_name": "birth_date",
        "extracted_value": "1981-05-12",
        "source_text": null,
        "confidence": null,
        "timestamp": null,
        "metadata": {}
      },
      "agent_id": "demographics_agent"
    }
  ],
  "missing_agents": [],
  "missing_criteria": [],
  "errors": [],
  "timestamp": "2026-10-26T21:20:00.000000+00:00"
}
```

#### Example cURL
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "SYNTH_PATIENT_001", "trial_id": "NCT05001234"}'
```

---

## 3. Current Integration State & Agent Configuration

### 3.1 Default Unconfigured State
Person 1's real agent implementations are not yet in the repository. When the server runs in this default state:
- `GET /health` reports `agents_configured: false` and `pipeline_status: "agents_unconfigured_pipeline_incomplete"`.
- `POST /api/v1/evaluate` without explicit `agent_results` returns a structured `ScreeningReport` with status `REQUIRES_REVIEW` and clear audit reasons explaining that agents are unconfigured.
- **The system never fabricates successful matches or clinical findings.**

### 3.2 Configuring Real Agents for Person 1
When Person 1 implements agent runners (e.g., in `src/agents/`), they can be injected into the application-wide coordinator instance using the clean dependency boundary:

```python
from src.api.dependencies import set_coordinator
from src.matching.coordinator import EligibilityCoordinator
from src.matching.decision_rules import DeterministicDecisionEngine

# Example: Registering Person 1's agent runner callables
coordinator = EligibilityCoordinator(
    decision_engine=DeterministicDecisionEngine(),
    registered_agents={
        "demographics_agent": run_demographics_agent,
        "conditions_agent": run_conditions_agent,
        "labs_agent": run_labs_agent,
        "medications_agent": run_medications_agent,
        "exclusion_agent": run_exclusion_agent,
    },
)

# Set the active coordinator for FastAPI
set_coordinator(coordinator)
```

### 3.3 Test Boundary & Mocking
Unit and integration tests use FastAPI's dependency override pattern (`app.dependency_overrides[get_coordinator] = lambda: mock_coordinator`). Tests run in memory without requiring network calls, external databases, or an LLM.

---

## 4. Error Handling and Security

- **Validation Errors (`422 Unprocessable Entity`)**: Clean, formatted error messages are returned when request payloads lack required fields or provide invalid data types.
- **Internal Server Errors (`500 Internal Server Error`)**: Unhandled exceptions are caught by global exception handlers. Generic safe error messages are returned to the client, preventing stack trace or internal credential leaks.
