# TrialMatch AI

**Multi-Agent Patient Eligibility Matching for Clinical Trials**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.66.1-red.svg)](https://streamlit.io/)

> **IMPORTANT CLINICAL RESEARCH DISCLAIMER**  
> TrialMatch AI is an investigational prototype and research system. It is **not** a certified medical device and is **not** clinically validated for autonomous medical diagnosis, treatment planning, or patient selection. All screening outputs, eligibility categorizations, and criterion interpretations require independent validation by qualified clinical research staff and principal investigators.

---

## 1. Project Purpose and Scope

TrialMatch AI addresses the inefficiency and opacity of clinical trial prescreening. Protocol eligibility criteria are frequently buried in unstructured text, while electronic health records (EHR) contain heterogeneous observations, diagnoses, and demographic records. 

TrialMatch AI evaluates patient eligibility against clinical trial protocols using:
1. **Domain-specific clinical eligibility agents** (Age, Diagnosis, Laboratory thresholds, Exclusion conditions).
2. **ClinicalAgentsAdapter** that safely translates domain agent outputs into canonical matching schemas.
3. **Deterministic Decision Engine** that applies auditable clinical decision rules without opaque percentage scoring.
4. **FastAPI Backend** exposing standardized, validated REST endpoints for orchestration.
5. **Streamlit Screening Dashboard** providing researchers with audit trails, review checklists, and visual cues.

---

## 2. High-Level Architecture & Agent Responsibilities

```
                                  +----------------------------+
                                  |   Streamlit Dashboard      |
                                  |   (src/dashboard/app.py)   |
                                  +--------------+-------------+
                                                 | HTTP
                                                 v
                                  +----------------------------+
                                  |     FastAPI Backend        |
                                  |     (src/api/app.py)       |
                                  +--------------+-------------+
                                                 | Dependency Injection
                                                 v
                                  +----------------------------+
                                  |   EligibilityCoordinator   |
                                  | (src/matching/coordinator) |
                                  +--------------+-------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
         +----------------------------+                     +----------------------------+
         |   ClinicalAgentsAdapter    |                     | DeterministicDecisionEngine|
         |  (src/agents/adapter.py)   |                     | (src/matching/decision_...)|
         +-------------+--------------+                     +----------------------------+
                       | Calls
       +---------------+---------------+---------------+
       |               |               |               |
       v               v               v               v
+--------------+ +--------------+ +--------------+ +--------------+
|   AgeAgent   | |DiagnosisAgent| |   LabAgent   | |ExclusionAgent|
|  (Age limits)| | (Type 2 DM)  | |(HbA1c & Labs)| |(HeartFailure)|
+--------------+ +--------------+ +--------------+ +--------------+
```

### Agent Responsibilities
* **`age_agent` (`src/agents/age_agent.py`)**: Evaluates patient age against protocol minimum and maximum age bounds. Maps missing protocol age restrictions conservatively to `UNKNOWN (OPTIONAL)` without silently passing.
* **`diagnosis_agent` (`src/agents/diagnosis_agent.py`)**: Assesses EHR condition records for required indications (e.g., Type 2 Diabetes). Missing evidence yields `UNKNOWN` (*absence of documentation is never proof of disease absence*).
* **`lab_agent` (`src/agents/lab_agent.py`)**: Assesses numerical observations against threshold comparisons (`<=`, `>=`, `<`, `>`, `==`) and validates units (e.g. `%` for HbA1c). Mismatched units or missing tests return `UNKNOWN`.
* **`exclusion_agent` (`src/agents/exclusion_agent.py`)**: Identifies documented conflicting conditions (e.g., Heart Failure). A documented exclusion yields `FAIL`; absence of documented condition yields `UNKNOWN` requiring clinical verification.
* **`unsupported_criteria_agent` (`src/agents/adapter.py`)**: Handles criteria lacking automated agent implementations (e.g. medication washouts, prior surgical interventions, pregnancy), ensuring they are explicitly surfaced as `UNKNOWN` for human review and never inferred as `PASS`.

---

## 3. Repository Layout

```text
trialmatch-ai/
├── data/                         # Local datasets (git-ignored)
│   ├── patients/synthea/         # Synthea patient, condition, observation CSVs
│   ├── trials/                   # Clinical trial JSON specifications
│   └── processed/                # Normalized intermediate datasets
├── docs/                         # Project technical documentation
│   ├── agent_contract.md         # Canonical Person 1 / Person 2 integration contract
│   ├── api_backend.md            # FastAPI endpoints and schema specifications
│   ├── dashboard.md              # Streamlit dashboard layout and UI states
│   ├── decision_engine.md        # Deterministic decision rules and truth tables
│   └── integration_architecture.md # End-to-end data flow and safety architecture
├── src/
│   ├── agents/                   # Person 1 agents & ClinicalAgentsAdapter
│   │   ├── adapter.py            # Canonical adapter connecting agents to coordinator
│   │   ├── age_agent.py          # Age criteria agent
│   │   ├── diagnosis_agent.py    # Primary diagnosis agent
│   │   ├── lab_agent.py          # Quantitative laboratory agent
│   │   ├── exclusion_agent.py    # Exclusion condition agent
│   │   ├── evidence.py           # Evidence and provenance builders
│   │   └── coordinator.py        # Pipeline runner
│   ├── api/                      # Person 2 FastAPI backend
│   │   ├── app.py                # FastAPI routes and exception handlers
│   │   ├── dependencies.py       # Dependency injection providers
│   │   └── schemas.py            # Pydantic request/response models
│   ├── dashboard/                # Person 2 Streamlit dashboard
│   │   ├── app.py                # Dashboard application
│   │   ├── api_client.py         # Resilient HTTP client
│   │   ├── demo_data.py          # Labeled synthetic demonstration scenarios
│   │   └── presentation.py       # Table formatting and status badges
│   ├── criteria/                 # Criteria extraction from text
│   ├── ingestion/                # Synthea and trial ingestion loaders
│   ├── matching/                 # Person 2 core matching and decision engine
│   │   ├── coordinator.py        # EligibilityCoordinator
│   │   ├── decision_rules.py     # DeterministicDecisionEngine
│   │   └── schema.py             # Canonical Pydantic domain models
│   └── normalization/            # Patient and observation normalization
├── tests/
│   └── unit/                     # Complete pytest suite (131 tests)
│       ├── test_agent_adapter.py # Adapter unit & integration tests
│       ├── test_api.py           # FastAPI endpoint tests
│       ├── test_coordinator.py   # Coordinator orchestration tests
│       ├── test_dashboard.py     # Streamlit client & display tests
│       └── test_decision_rules.py# Decision engine rules tests
├── requirements.txt              # Unified dependencies
└── README.md                     # Project documentation
```

---

## 4. Installation and Setup

### Prerequisites
* **Python**: Version 3.10, 3.11, 3.12, or 3.13.
* **Git**: Installed and configured.

### Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/PallaviGajawada/trialmatch-ai.git
   cd trialmatch-ai
   ```

2. **Create and activate a virtual environment:**
   * **Linux/macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   * **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 5. Environment Variables & Configuration

The application uses explicit configuration with safe fallbacks:

| Variable | Default Value | Description |
|---|---|---|
| `TRIALMATCH_API_URL` | `http://127.0.0.1:8000` | Base URL used by the Streamlit dashboard to connect to the FastAPI backend. |
| `TRIALMATCH_DATA_DIR` | `data` | Base directory for local Synthea patient CSVs and trial JSON files. |

---

## 6. Supplying Input Datasets (Optional for Local Live Evaluation)

Because real Synthea CSV files and trial downloads can be several gigabytes and may contain synthetic PHI, they are excluded from Git via `.gitignore`.

To configure live evaluation with local datasets:
1. Place Synthea patient CSVs in `data/patients/synthea/`:
   * `patients.csv` (contains `Id`, `BIRTHDATE`, `GENDER`)
   * `conditions.csv` (contains `PATIENT`, `CODE`, `DESCRIPTION`)
   * `observations.csv` (contains `PATIENT`, `DATE`, `CODE`, `DESCRIPTION`, `VALUE`, `UNITS`)
2. Place trial protocol JSON definitions in `data/trials/`:
   * `diabetes_trials.json` (list of clinical trial definitions with `nct_id`, `minimum_age`, `maximum_age`)

*Note: If local datasets are not present, the system defaults to an unconfigured state, reporting controlled errors rather than fabricating synthetic data.*

---

## 7. Running the Application

### 1. Run the Full Test Suite
Execute all 131 unit and integration tests:
```bash
pytest
```
Run with verbose output:
```bash
pytest -v
```

### 2. Start the FastAPI Backend
Launch the backend server:
```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
* **Interactive API Documentation (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Alternative API Documentation (ReDoc)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 3. Start the Streamlit Dashboard
In a separate terminal, launch the dashboard:
```bash
streamlit run src/dashboard/app.py
```
Open your browser to [http://localhost:8501](http://localhost:8501).

---

## 8. Operating Modes

### A. Demonstration Mode (Synthetic Scenarios)
The dashboard includes built-in, clearly labeled synthetic clinical scenarios:
1. Open the dashboard at [http://localhost:8501](http://localhost:8501).
2. In the left sidebar, check **Enable Synthetic Demonstration Mode**.
3. Select a scenario from the dropdown:
   * **Eligible Candidate**: Patient satisfying all demographic, diagnostic, and biomarker criteria.
   * **Ineligible Candidate**: Patient failing mandatory age limit criteria (`NOT_A_MATCH`).
   * **Uncertain Candidate**: Patient with pending lab biomarker (`REQUIRES_REVIEW`).
   * **Conflicted Candidate**: Contradictory evaluations requiring audit.
4. Click **Evaluate Eligibility** to view the structured report, criterion findings, and evidence provenance.

### B. Live API Evaluation Mode
When demonstration mode is disabled, the dashboard issues evaluation requests directly to the FastAPI backend:
1. Enter a `Patient Identifier` and `Clinical Trial Identifier`.
2. Click **Evaluate Eligibility**.
3. If local datasets are configured, the backend executes the multi-agent adapter pipeline and presents live evaluation findings.
4. If local datasets are absent, the system displays an informative message explaining that evaluation is incomplete and clinical review is required.

---

## 9. API Endpoint Reference

### `GET /health`
Returns backend service status and readiness:
```bash
curl http://127.0.0.1:8000/health
```
**Example Response (Unconfigured Datasets):**
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

### `POST /api/v1/evaluate`
Evaluates a patient's eligibility against clinical trial criteria.

**Request Payload:**
```json
{
  "patient_id": "P_SYNTH_001",
  "trial_id": "NCT05001234",
  "required_agents": ["age_agent", "diagnosis_agent", "lab_agent", "exclusion_agent"]
}
```

**Response Payload (`ScreeningReport`):**
```json
{
  "report_id": "REP_P_SYNTH_001_NCT05001234_20261026T170000Z",
  "patient_id": "P_SYNTH_001",
  "trial_id": "NCT05001234",
  "overall_status": "REQUIRES_REVIEW",
  "requires_human_review": true,
  "criteria_results": [
    {
      "criterion_id": "CRIT_AGE",
      "name": "Age Limit Requirement",
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 45,
      "expected_value": "Min: 18 Years, Max: 75 Years",
      "explanation": "Patient satisfies the specified age limits.",
      "agent_id": "age_agent"
    }
  ],
  "counts": {
    "total_criteria": 4,
    "passed": 3,
    "failed": 0,
    "unknown": 1,
    "mandatory_total": 4,
    "mandatory_passed": 3,
    "mandatory_failed": 0,
    "mandatory_unknown": 1
  },
  "reasons": [
    "Mandatory criterion 'CRIT_EXCLUSION_HEART_FAILURE' status is UNKNOWN: requires clinician verification."
  ]
}
```

---

## 10. Troubleshooting

| Issue | Cause | Resolution |
|---|---|---|
| Dashboard displays `✖ Backend Disconnected` | FastAPI backend is not running or running on a different port. | Start the backend using `uvicorn src.api.app:app --reload` and check `TRIALMATCH_API_URL`. |
| Health reports `agents_unconfigured_pipeline_incomplete` | Local Synthea CSVs or trial JSON files are absent from `data/`. | This is expected in a clean checkout. Use Synthetic Demonstration Mode in the dashboard, or supply datasets to `data/patients/synthea/`. |
| API returns `422 Unprocessable Content` | Request body missing `patient_id` or `trial_id`, or fields are whitespace only. | Verify request payload contains non-empty string values for both identifiers. |
| Test suite fails to import dependencies | Virtual environment is not activated or dependencies are missing. | Activate virtual environment and run `pip install -r requirements.txt`. |

---

## 11. Known Limitations & Unsupported Criteria

1. **Unsupported Clinical Domains**: The current agents evaluate age, Type 2 Diabetes diagnosis, quantitative laboratory thresholds (HbA1c), and Heart Failure exclusion. Complex criteria such as medication washout periods, prior systemic immunotherapy regimens, pregnancy/lactation, and surgical history are **unsupported** by automated agents and are assigned `UNKNOWN` for mandatory human review.
2. **Indication Scope**: `diagnosis_agent` currently recognizes Type 2 Diabetes Mellitus variations. Non-diabetes indications return `UNKNOWN`.
3. **Absence != Proof of Disease Absence**: Absence of an EHR code is never interpreted as proof that a condition is not present.
4. **Research Prototype**: All outputs are decision-support aids requiring validation by clinical investigators before patient recruitment.
