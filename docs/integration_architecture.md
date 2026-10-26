# TrialMatch AI — Integration Architecture & Data Flow

> **Document Version**: 1.0.0  
> **Component**: Integrated Multi-Agent Clinical Matching Architecture  
> **Authors**: Person 1 (Eligibility Agents) & Person 2 (Orchestration & Decision Engine)  

---

## 1. System Overview

TrialMatch AI bridges Person 1's domain-specific clinical eligibility agents and Person 2's canonical eligibility coordinator, deterministic decision engine, FastAPI backend, and Streamlit user interface.

```
[ Patient Data ]       [ Trial Protocol ]
(Synthea / EHR)        (Protocol Specs)
       │                      │
       └──────────┬───────────┘
                  ▼
      ┌─────────────────────────┐
      │  ClinicalAgentsAdapter  │ <──── Translates domain outputs into canonical models
      └───────────┬─────────────┘
                  │ Invokes & Transforms
    ┌─────────────┼─────────────┬─────────────┐
    ▼             ▼             ▼             ▼
┌────────┐  ┌───────────┐  ┌─────────┐  ┌───────────────┐
│AgeAgent│  │Diag Agent │  │Lab Agent│  │Exclusion Agent│
└────────┘  └───────────┘  └─────────┘  └───────────────┘
    │             │             │             │
    └─────────────┴──────┬──────┴─────────────┘
                         ▼ Canonical AgentResults
            ┌─────────────────────────┐
            │ EligibilityCoordinator  │ <──── Validates agents, prevents silent pass
            └────────────┬────────────┘
                         ▼ Aggregated Findings
            ┌─────────────────────────┐
            │DeterministicDecisionEng │ <──── Rules-based clinical outcome determination
            └────────────┬────────────┘
                         ▼ ScreeningReport
            ┌─────────────────────────┐
            │     FastAPI Backend     │ <──── REST API with audit provenance
            └────────────┬────────────┘
                         ▼ HTTP
            ┌─────────────────────────┐
            │   Streamlit Dashboard   │ <──── Visual review & criteria findings table
            └─────────────────────────┘
```

---

## 2. End-to-End Data Flow

### Step 1: Ingestion & Normalization
* **Patient Demographics**: Patient demographics (`birth_date`, `gender`) are parsed from EHR tables or synthetic Synthea records (`src/normalization/normalize_patients.py`).
* **Condition Records**: Diagnoses are standardized using case-folding and punctuation normalization (`src/agents/diagnosis_agent.py:normalize_condition_name`).
* **Laboratory Observations**: Numeric observations (`observation`, `value`, `units`, `observation_date`) are filtered and sorted to identify the latest relevant clinical reading.

### Step 2: The Agent Adapter Layer (`src/agents/adapter.py`)
`ClinicalAgentsAdapter` serves as the integration boundary:
* **Lazy Loading & Safe Ingestion**: Accesses patient records and trial definitions without loading large CSVs into memory at import time.
* **Domain Invocation**: Invokes only verified agents whose inputs can be reliably satisfied (`run_age_agent`, `run_diagnosis_agent`, `run_lab_agent`, `run_exclusion_agent`).
* **Status Normalization**: Maps domain agent statuses to canonical `CriterionStatus` (`PASS`, `FAIL`, `UNKNOWN`).
* **Clinical Safety Translation**:
  - `NOT_APPLICABLE` (e.g. trial with no specified age limit) is mapped to `CriterionStatus.UNKNOWN` with `CriterionType.OPTIONAL`. It is **never** mapped to `PASS`.
  - Missing clinical evidence is mapped to `UNKNOWN` (*absence of documentation is never proof of disease absence*).
  - Unsupported criteria (medication washout, surgery, pregnancy) produce `UNKNOWN` findings via `run_unsupported_criteria` and are never assumed to have passed.
* **Evidence Provenance**: Builds canonical `EvidenceProvenance` objects preserving the source table, timestamp, field name, and observed clinical value.

### Step 3: Coordination & Audit Validation (`src/matching/coordinator.py`)
`EligibilityCoordinator` orchestrates the evaluation:
* Validates inputs, ensuring no unauthorized agents or contradictory duplicate criteria are submitted.
* Verifies that all required criteria have been assessed.
* Never assumes an agent ran if it was not invoked.
* Captures agent execution errors without crashing the pipeline.

### Step 4: Deterministic Decision Engine (`src/matching/decision_rules.py`)
`DeterministicDecisionEngine` applies clinical decision rules:
1. **Rule 1 (Definitive Disqualification)**: If any mandatory criterion has status `FAIL`, the overall outcome is `NOT_A_MATCH` (`requires_human_review = False` unless other conflicts exist).
2. **Rule 2 (Clinical Review Requirement)**: If any mandatory criterion has status `UNKNOWN`, agent errors occurred, required criteria were missing, or evaluations conflict, the overall outcome is `REQUIRES_REVIEW` (`requires_human_review = True`).
3. **Rule 3 (Potential Match)**: If all mandatory criteria have status `PASS` and no review conditions exist, the overall status is `POTENTIAL_MATCH`. If optional criteria failed, `requires_human_review` is set to `True` for investigator awareness.

### Step 5: FastAPI Backend (`src/api/app.py`)
* Exposes `/health` to report backend status and readiness without claiming operational readiness when datasets are unconfigured.
* Exposes `/api/v1/evaluate` to accept `EvaluationRequest` and return validated `ScreeningReport`.
* Handles validation errors (`422 Unprocessable Content`) and generic errors (`500 Internal Server Error`) without leaking sensitive connection strings or internal tracebacks.

### Step 6: Streamlit Dashboard (`src/dashboard/app.py`)
* Connects to the backend via `TrialMatchApiClient`.
* Displays status badges (`POTENTIAL MATCH`, `NOT A MATCH`, `REQUIRES REVIEW`).
* Provides summary metrics, an interactive criteria findings table, and expandable evidence provenance details for researcher audit.
* Offers a distinct **Demonstration Mode** with labeled synthetic scenarios.

---

## 3. Clinical Safety Rules Summary

| Rule | Implementation Mechanism |
|---|---|
| Never map `NOT_APPLICABLE` to `PASS` | `ClinicalAgentsAdapter._map_status()` maps `NOT_APPLICABLE` to `UNKNOWN` (`OPTIONAL`). |
| Never treat missing evidence as proof of absence | Agents return `UNKNOWN` when conditions or lab observations are absent. |
| Never convert optional failures into passes | `DeterministicDecisionEngine` flags optional failures as requiring human review. |
| Never infer that unsupported agents passed | `run_unsupported_criteria` explicitly returns `UNKNOWN` for unimplemented criteria. |
| Deterministic outcomes owned by matching module | All final status assignments are computed exclusively by `src/matching/decision_rules.py`. |
| Zero synthetic data fabrication | In unconfigured environments, explicit error reports are returned rather than fabricated patient records. |
