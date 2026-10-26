# TrialMatch AI: Coordinator & Deterministic Decision Engine

## Overview

The **Eligibility Coordinator** and **Deterministic Decision Engine** form the core clinical trial eligibility adjudication component of TrialMatch AI (Components 1 & 2). This component coordinates multi-agent evaluation outputs, enforces strict schema and semantic validation, and deterministically determines a patient's screening eligibility status without relying on opaque percentage scores or probabilistic guessing.

For the exact contract and instructions for Person 1's agent implementations, see [docs/agent_contract.md](file:///c:/Projects/TrialMatch%20AI/docs/agent_contract.md).

---

## 1. Data Contracts

### 1.1 Input Contracts

The coordinator accepts:
- `patient_id` (`str`): Unique identifier of the patient (non-empty string).
- `trial_id` (`str`): Target clinical trial identifier (e.g. `NCT05001234`).
- `agent_results` (`Sequence[AgentResult | dict]`): Collection of agent evaluation outputs.
- `required_agents` (`Optional[Sequence[str]]`): List of agent IDs expected to report (e.g. `['demographics_agent', 'labs_agent']`).
- `required_criteria` (`Optional[Sequence[str]]`): List of criterion IDs that must be evaluated.

#### Agent Result Schema (`AgentResult`)
| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | `str` | Yes | Identifier of the reporting agent. |
| `status` | `AgentExecutionStatus` | Yes | `SUCCESS`, `ERROR`, or `SKIPPED`. Default is `SUCCESS`. |
| `criteria_results` | `List[CriterionResult]` | Yes | List of individual criterion evaluations. |
| `error_message` | `Optional[str]` | No | Error details if agent execution failed. |
| `metadata` | `Dict[str, Any]` | No | Additional execution metadata (execution latency, models used, etc.). |

#### Criterion Result Schema (`CriterionResult`)
| Field | Type | Required | Description |
|---|---|---|---|
| `criterion_id` | `str` | Yes | Unique ID of the criterion (e.g., `CRIT_AGE_MIN`). |
| `name` | `Optional[str]` | No | Human-readable criterion label. |
| `criterion_type` | `CriterionType` | Yes | `MANDATORY` or `OPTIONAL`. |
| `status` | `CriterionStatus` | Yes | `PASS`, `FAIL`, or `UNKNOWN`. |
| `observed_value` | `Any` | No | Patient observation (e.g., `45`, `Stage IV`). |
| `expected_value` | `Any` | No | Protocol threshold (e.g., `>= 18`, `NSCLC`). |
| `explanation` | `str` | Yes | Human-readable rationale for the criterion outcome. |
| `evidence` | `Optional[EvidenceProvenance | dict | str]` | No | Source citation and provenance details. |
| `agent_id` | `Optional[str]` | No | Provenance identifier of the evaluating agent. |

#### Evidence Provenance Schema (`EvidenceProvenance`)
| Field | Type | Description |
|---|---|---|
| `source` | `str` | Origin source (e.g., `EHR`, `Lab_Report`, `Pathology`). |
| `document_id` | `Optional[str]` | Source document identifier. |
| `field_name` | `Optional[str]` | Specific observation/lab field name. |
| `extracted_value` | `Any` | Raw or normalized value extracted from clinical records. |
| `source_text` | `Optional[str]` | Verbatim sentence or clinical text supporting evaluation. |
| `confidence` | `Optional[float]` | Extraction confidence score (0.0 to 1.0). |
| `timestamp` | `Optional[str]` | Date or timestamp of observation. |
| `metadata` | `Dict[str, Any]` | Additional provenance context. |

---

### 1.2 Result Contract (`ScreeningReport`)

The coordinator outputs a `ScreeningReport`:
| Field | Type | Description |
|---|---|---|
| `patient_id` | `str` | Identifier of the patient evaluated. |
| `trial_id` | `str` | Identifier of the clinical trial. |
| `overall_status` | `OverallStatus` | One of `POTENTIAL_MATCH`, `NOT_A_MATCH`, `REQUIRES_REVIEW`. |
| `requires_human_review` | `bool` | Flag set to `True` whenever eligibility cannot be deterministically cleared. |
| `reasons` | `List[str]` | Clear, auditable justifications for the overall status. |
| `counts` | `EvaluationCounts` | Aggregate statistics (`total`, `passed`, `failed`, `unknown`, mandatory vs optional). |
| `criterion_results` | `List[CriterionResult]` | Complete list of all evaluated criteria with provenance preserved. |
| `missing_agents` | `List[str]` | Missing required agents that failed to report. |
| `missing_criteria` | `List[str]` | Missing mandatory criteria that were not evaluated. |
| `errors` | `List[str]` | Validation, agent crash, or malformed payload errors. |
| `timestamp` | `str` | ISO 8601 UTC timestamp of report creation. |

---

## 2. Deterministic Decision Rules

The decision engine strictly enforces deterministic clinical trial logic without percentage scores:

1. **Definitive Failure Rule**: A definitive failure (`FAIL`) of any `MANDATORY` criterion immediately results in `NOT_A_MATCH`.
2. **Definitive Failure Precedence**: If a mandatory criterion has failed, the status remains `NOT_A_MATCH` even if another criterion is `UNKNOWN` or if non-fatal agent errors occurred (the patient is definitively disqualified by protocol).
3. **Review Escalation Rule**: Any required/mandatory criterion with status `UNKNOWN` results in `REQUIRES_REVIEW` (unless a mandatory failure already establishes `NOT_A_MATCH`).
4. **Zero Silent Pass Policy**:
   - Missing required agent outputs,
   - Missing required criteria,
   - Agent evaluation errors,
   - Invalid status strings (e.g., `MAYBE`, `PENDING`),
   - Malformed agent payloads, and
   - Empty criteria results
   must **never** silently count as `PASS`. All trigger `REQUIRES_REVIEW` with `requires_human_review = True`.
5. **Full Mandatory Compliance**: `POTENTIAL_MATCH` is returned **only** when all mandatory criteria have been evaluated and all have status `PASS`.
6. **Optional Criteria Independence**: Optional criteria with status `UNKNOWN` or `FAIL` do not block a valid `POTENTIAL_MATCH` if all mandatory criteria passed, but findings are recorded in the report for researcher awareness.
7. **No Heuristic Scoring**: Clinical eligibility is never inferred from a percentage or threshold score (e.g. "80% match").

---

## 3. Status Examples

### Example 1: `POTENTIAL_MATCH`
```json
{
  "patient_id": "PATIENT_101",
  "trial_id": "NCT05123456",
  "overall_status": "POTENTIAL_MATCH",
  "requires_human_review": false,
  "reasons": [
    "All mandatory criteria passed (2/2)."
  ],
  "counts": {
    "total_criteria": 2,
    "passed": 2,
    "failed": 0,
    "unknown": 0,
    "mandatory_total": 2,
    "mandatory_passed": 2,
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
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 45,
      "expected_value": ">= 18",
      "explanation": "Patient age 45 meets minimum age of 18.",
      "evidence": {
        "source": "EHR",
        "field_name": "birth_date"
      },
      "agent_id": "demographics_agent"
    },
    {
      "criterion_id": "CRIT_PLATELETS",
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 220000,
      "expected_value": ">= 100000",
      "explanation": "Platelet count within acceptable trial threshold.",
      "evidence": {
        "source": "Lab_Report",
        "document_id": "LAB_8810"
      },
      "agent_id": "labs_agent"
    }
  ],
  "missing_agents": [],
  "missing_criteria": [],
  "errors": []
}
```

### Example 2: `NOT_A_MATCH`
```json
{
  "patient_id": "PATIENT_202",
  "trial_id": "NCT05123456",
  "overall_status": "NOT_A_MATCH",
  "requires_human_review": false,
  "reasons": [
    "Mandatory criterion 'CRIT_PRIOR_THERAPY' failed: observed='Prior anti-PD-1 immunotherapy received', expected='No prior immunotherapy'. Explanation: Patient received prior pembrolizumab, violating exclusion criteria."
  ],
  "counts": {
    "total_criteria": 2,
    "passed": 1,
    "failed": 1,
    "unknown": 0,
    "mandatory_total": 2,
    "mandatory_passed": 1,
    "mandatory_failed": 1,
    "mandatory_unknown": 0,
    "optional_total": 0,
    "optional_passed": 0,
    "optional_failed": 0,
    "optional_unknown": 0
  },
  "criterion_results": [
    {
      "criterion_id": "CRIT_AGE",
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 52,
      "expected_value": ">= 18",
      "explanation": "Age criterion met.",
      "agent_id": "demographics_agent"
    },
    {
      "criterion_id": "CRIT_PRIOR_THERAPY",
      "criterion_type": "MANDATORY",
      "status": "FAIL",
      "observed_value": "Prior anti-PD-1 immunotherapy received",
      "expected_value": "No prior immunotherapy",
      "explanation": "Patient received prior pembrolizumab, violating exclusion criteria.",
      "evidence": {
        "source": "EHR_Medications",
        "field_name": "medication_history",
        "extracted_value": "Pembrolizumab 200mg"
      },
      "agent_id": "medications_agent"
    }
  ],
  "missing_agents": [],
  "missing_criteria": [],
  "errors": []
}
```

### Example 3: `REQUIRES_REVIEW`
```json
{
  "patient_id": "PATIENT_303",
  "trial_id": "NCT05123456",
  "overall_status": "REQUIRES_REVIEW",
  "requires_human_review": true,
  "reasons": [
    "Missing required agent(s): pathology_agent",
    "Mandatory criterion 'CRIT_EGFR_MUTATION' status is UNKNOWN: Molecular panel pending; EGFR status unavailable."
  ],
  "counts": {
    "total_criteria": 2,
    "passed": 1,
    "failed": 0,
    "unknown": 1,
    "mandatory_total": 2,
    "mandatory_passed": 1,
    "mandatory_failed": 0,
    "mandatory_unknown": 1,
    "optional_total": 0,
    "optional_passed": 0,
    "optional_failed": 0,
    "optional_unknown": 0
  },
  "criterion_results": [
    {
      "criterion_id": "CRIT_AGE",
      "criterion_type": "MANDATORY",
      "status": "PASS",
      "observed_value": 61,
      "expected_value": ">= 18",
      "explanation": "Age criterion met.",
      "agent_id": "demographics_agent"
    },
    {
      "criterion_id": "CRIT_EGFR_MUTATION",
      "criterion_type": "MANDATORY",
      "status": "UNKNOWN",
      "observed_value": null,
      "expected_value": "EGFR Exon 19 del or L858R",
      "explanation": "Molecular panel pending; EGFR status unavailable.",
      "agent_id": "genomics_agent"
    }
  ],
  "missing_agents": ["pathology_agent"],
  "missing_criteria": [],
  "errors": []
}
```

---

## 4. Key Assumptions & Safety Guardrails

1. **Safety First**: TrialMatch AI is a clinical research screening tool and does not make final clinical enrollment decisions without human clinician review.
2. **Never Assume Agent Execution**: The coordinator never assumes or synthesizes output for an agent that did not execute or report.
3. **Decoupled Architecture**: All decision and orchestration rules are completely decoupled from UI frameworks (e.g., Streamlit) and transport layers (e.g., FastAPI), allowing robust unit testing and flexible integration.
4. **Preserved Provenance**: Every criterion outcome retains its original source provenance and agent attribution for end-to-end auditability.
