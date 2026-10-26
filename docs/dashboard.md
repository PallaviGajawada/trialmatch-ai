# TrialMatch AI — Component 4: Streamlit Dashboard

## Overview

The **TrialMatch AI Screening Dashboard** (`src.dashboard.app`) is an interactive, clinician-accessible web interface for clinical trial patient eligibility matching. It communicates with the FastAPI backend (`POST /api/v1/evaluate` and `GET /health`) to provide transparent, explainable screening assessments with criterion-level evidence provenance.

---

## 1. Quickstart & Local Execution

### 1.1 Prerequisites
Install dependencies from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 1.2 Step 1: Start the FastAPI Backend
In a terminal, start the FastAPI backend service:
```bash
uvicorn src.api.app:app --reload
```
By default, the backend runs on `http://127.0.0.1:8000`.

### 1.3 Step 2: Start the Streamlit Dashboard
In a second terminal, launch the Streamlit dashboard:
```bash
streamlit run src/dashboard/app.py
```
Streamlit will automatically open the dashboard in your default browser at `http://localhost:8501`.

---

## 2. Configuration & Environment Variables

### API Base URL Configuration
The dashboard communicates with the backend via HTTP. You can configure the backend URL in two ways:

1. **Environment Variable**:
   Set `TRIALMATCH_API_URL` before launching Streamlit:
   ```bash
   # Linux / macOS
   export TRIALMATCH_API_URL="http://127.0.0.1:8000"

   # Windows PowerShell
   $env:TRIALMATCH_API_URL="http://127.0.0.1:8000"
   ```

2. **In-App Sidebar Override**:
   You can modify the **Backend API Base URL** directly in the dashboard sidebar at runtime.

---

## 3. Dashboard Features

### 3.1 Medical Research Disclaimer
Prominently displayed at the top of every screen:
> **CLINICAL RESEARCH DISCLAIMER**: TrialMatch AI is an investigational screening decision-support prototype. Automated screening results do not constitute a medical diagnosis, clinical judgment, or definitive enrollment decision. All matching reports require independent review by qualified clinical research staff.

### 3.2 Patient & Trial Selection
- **Patient Identifier**: Select from synthetic demo patient records or enter a custom patient ID.
- **Clinical Trial Identifier**: Select from sample trial protocols or enter a custom trial NCT ID.
- **"Evaluate Eligibility"**: Triggers deterministic screening evaluation through the FastAPI backend.

### 3.3 Accessible Status Presentation
The overall status is displayed using accessible visual cards and text symbols (not color alone):
- `[ MATCH ] POTENTIAL MATCH`: All mandatory criteria evaluated and satisfied.
- `[ NO MATCH ] NOT A MATCH`: Disqualified by a definitive mandatory criterion failure.
- `[ REVIEW REQUIRED ] REQUIRES REVIEW`: Information is incomplete, unknown, conflicting, or agents are unconfigured.

### 3.4 Summary Metric Cards
- **Total Criteria Evaluated**
- **Mandatory Passed** (`X / Total Mandatory`)
- **Mandatory Failed**
- **Mandatory Unknown**
- **Human Review Flag** (`REQUIRED` / `NOT REQUIRED`)

### 3.5 Review Section & Audit Reasons
An expandable audit section highlighting:
- Plain-English justifications for the overall status.
- Mandatory criterion failures.
- Unknown or pending clinical data.
- Missing required agents or criteria.
- Execution or validation errors.

### 3.6 Criterion-Level Findings Table
Displays a tabular breakdown of all evaluated protocol criteria:
- **Criterion ID & Label**
- **Type**: Mandatory vs. Optional
- **Status**: `✓ PASS`, `✗ FAIL`, or `❓ UNKNOWN`
- **Observed Patient Value** (or `(Unrecorded)`)
- **Expected Trial Value**
- **Explanation**: Clinical rationale
- **Provenance Citation**: Source EHR document, lab report, field name, and extracted value
- **Evaluating Agent**: Attribution to the reporting agent

---

## 4. Demonstration Mode (Synthetic Scenarios)

Because Person 1's real eligibility agents are in development, the dashboard includes a **Demonstration Mode**:
- Activate via the sidebar checkbox: **"Enable Synthetic Demonstration Mode"**.
- Clearly marked: `[SYNTHETIC DEMO ONLY - NOT REAL CLINICAL DATA]`.
- Allows exploring:
  - **Scenario 1 (Potential Match)**: Patient satisfies all protocol inclusion/exclusion criteria.
  - **Scenario 2 (Not a Match)**: Patient received prior immunotherapy, triggering a definitive exclusion failure.
  - **Scenario 3 (Requires Review)**: EGFR biomarker test is pending, resulting in a mandatory `UNKNOWN`.

---

## 5. Architectural Separation

- **UI vs API**: The dashboard rendering code in `src/dashboard/app.py` never directly accesses the database, coordinator, or agent files. All communication is routed through `TrialMatchApiClient` in `src/dashboard/api_client.py`.
- **Logic Integrity**: The dashboard never reimplements eligibility heuristics or overrides decision rules. It renders the structured `ScreeningReport` emitted by the backend.
- **Fail-Safe Operation**: If the backend is unreachable or returns HTTP errors, the dashboard displays clear, non-cryptic error cards with troubleshooting guidance.
