# Shared Agent Integration Contract (Person 1 & Person 2)

> **Contract Status**: Active / Canonical Shared Integration Contract  
> **Authors**: Person 2 (Orchestration & Decision Engine) & Person 1 (Data & Eligibility Agents)  
> **Version**: 1.1.0  

---

## 1. Overview & Purpose

This document defines the strict, shared integration contract between **Person 1's eligibility agents** and **Person 2's coordinator & deterministic decision engine**.

The coordinator expects all eligibility agents to emit results adhering to this specification. By following this contract:
- Agents remain decoupled from orchestration, HTTP routes, and UI presentation.
- All criterion evaluations preserve strict data provenance for auditability.
- Decisions remain 100% deterministic, without opaque percentage scores.

---

## 2. Standard Agent Identifiers & Responsibilities

The system recognizes standard canonical agents (`StandardAgentId` in `src.matching.schema`). Person 1 should implement agents matching these identifiers:

| Agent Identifier (`agent_id`) | Primary Responsibility | Example Criteria Evaluated |
|---|---|---|
| `demographics_agent` | Age, gender, geographic residence, legal consent capacity | `CRIT_AGE_MIN`, `CRIT_AGE_MAX`, `CRIT_GENDER` |
| `conditions_agent` | Primary diagnosis, disease stage, histology, disease recurrence | `CRIT_DIAGNOSIS`, `CRIT_STAGE`, `CRIT_HISTOLOGY` |
| `labs_agent` | Clinical measurements, organ function (hematology, hepatic, renal) | `CRIT_PLATELETS`, `CRIT_CREATININE`, `CRIT_BILIRUBIN` |
| `medications_agent` | Prior lines of therapy, concurrent medications, required washout | `CRIT_PRIOR_IMMUNOTHERAPY`, `CRIT_WASHOUT_PERIOD` |
| `exclusion_agent` | Systemic exclusion criteria (infections, pregnancy, concurrent trials) | `CRIT_ACTIVE_INFECTION`, `CRIT_PREGNANCY`, `CRIT_CONCURRENT_TRIAL` |

---

## 3. Canonical Data Schemas

Person 1 can return either typed Pydantic models (`AgentResult`, `CriterionResult`, `EvidenceProvenance`) or equivalent Python dictionaries (`dict`). The coordinator uses Pydantic's `model_validate` for parsing and validation.

### 3.1 `AgentResult`
The top-level envelope returned by each agent for a given patient and trial:

```python
class AgentResult(BaseModel):
    agent_id: str                      # Required: Canonical agent identifier (e.g. 'demographics_agent')
    status: AgentExecutionStatus       # Required: SUCCESS, ERROR, or SKIPPED (default: SUCCESS)
    criteria_results: List[CriterionResult] # List of criterion assessments
    error_message: Optional[str] = None # Detailed error message if status == ERROR
    metadata: Dict[str, Any] = {}      # Optional agent metadata (execution time, version, etc.)
```

### 3.2 `CriterionResult`
An individual criterion finding:

```python
class CriterionResult(BaseModel):
    criterion_id: str                  # Required: Unique criterion ID (e.g. 'CRIT_AGE_MIN')
    name: Optional[str] = None         # Human-readable name (e.g. 'Minimum Age')
    criterion_type: CriterionType      # Required: MANDATORY or OPTIONAL (default: MANDATORY)
    status: CriterionStatus            # Required: PASS, FAIL, or UNKNOWN
    observed_value: Any = None         # Patient value found in EHR (e.g. 45, 'Stage IV')
    expected_value: Any = None         # Trial requirement (e.g. '>= 18', 'Stage III or IV')
    explanation: str = ""              # Required: Human-readable clinical justification
    evidence: Optional[Union[EvidenceProvenance, Dict[str, Any], str]] = None
    agent_id: Optional[str] = None     # Agent identifier (auto-populated by coordinator if omitted)
```

### 3.3 `EvidenceProvenance`
Source citation and provenance for audit trails:

```python
class EvidenceProvenance(BaseModel):
    source: str                        # Required: Source type (e.g. 'EHR', 'Lab_Report', 'Pathology_Report')
    document_id: Optional[str] = None  # Source document or note identifier
    field_name: Optional[str] = None   # Clinical observation field or lab test name
    extracted_value: Any = None        # Raw or normalized value extracted from text/tables
    source_text: Optional[str] = None  # Verbatim sentence or text snippet supporting finding
    confidence: Optional[float] = None # Extraction confidence score (0.0 to 1.0)
    timestamp: Optional[str] = None    # Date/time of clinical record or measurement
    metadata: Dict[str, Any] = {}      # Additional metadata
```

---

## 4. Key Semantic Distinctions

Person 1 must strictly observe the following semantic distinctions:

### 4.1 Missing Data vs. Failed Criterion
- **`status = CriterionStatus.FAIL`**:
  - The patient record was successfully inspected and patient data **does not meet** the trial criteria.
  - *Example*: Patient age is 15; trial requires age `>= 18`.
  - *Effect*: If the criterion is `MANDATORY`, this definitively disqualifies the patient (`NOT_A_MATCH`).
- **`status = CriterionStatus.UNKNOWN`**:
  - The patient record lacks necessary data, the test was not performed, or the lab is pending.
  - *Example*: EGFR mutation status cannot be evaluated because no molecular panel exists in the record.
  - *Effect*: If the criterion is `MANDATORY`, this triggers `REQUIRES_REVIEW`. The patient is **not** disqualified.

### 4.2 Agent Execution Error vs. Criterion UNKNOWN
- **Criterion UNKNOWN (`status = UNKNOWN`)**:
  - Agent executed normally (`AgentExecutionStatus.SUCCESS`), examined clinical records, and determined that information is missing.
- **Agent Execution Error (`AgentExecutionStatus.ERROR` or unhandled Exception)**:
  - Infrastructure failure: database timeout, parser failure, network disconnection, or unhandled exception.
  - Set `status = AgentExecutionStatus.ERROR` and populate `error_message`.
  - Never emit a fake `PASS` or silent `UNKNOWN` on agent infrastructure failure.

### 4.3 Mandatory vs. Optional Criteria
- **`MANDATORY`**: Core protocol inclusion/exclusion criteria. All mandatory criteria must pass for a patient to be a `POTENTIAL_MATCH`. A single mandatory failure results in `NOT_A_MATCH`.
- **`OPTIONAL`**: Secondary, exploratory, or stratifying criteria. If an optional criterion is `UNKNOWN` or `FAIL`, it does **not** block `POTENTIAL_MATCH` as long as all mandatory criteria passed.

---

## 5. Coordinator Validation & Error Handling Rules

The coordinator validates incoming results with zero tolerance for silent failures:

1. **Unknown Agent Identifiers**: If `allowed_agents` is configured on the coordinator, any unrecognized agent ID triggers `REQUIRES_REVIEW`.
2. **Duplicate Agent Reports**: Emitting multiple `AgentResult` objects for the same `agent_id` is an error and triggers `REQUIRES_REVIEW`.
3. **Duplicate Criteria**: Two agents reporting the same `criterion_id` is flagged as duplicate and triggers `REQUIRES_REVIEW`.
4. **Conflicting Criterion Results**: If two evaluations for the same `criterion_id` provide contradictory statuses (e.g., `PASS` vs `FAIL`), the coordinator records a conflict error and escalates to `REQUIRES_REVIEW`.
5. **Precedence**: An independent, non-conflicting mandatory failure (`FAIL`) results in `NOT_A_MATCH` even if another criterion had an `UNKNOWN` status or conflict.
6. **Timeouts**: If agent execution exceeds configured timeouts, the coordinator safely wraps it as an `AgentExecutionStatus.ERROR`.

---

## 6. Realistic Synthetic Examples for Person 1

### Example 1: `demographics_agent` (Passing Evaluation)
```python
from src.matching.schema import (
    AgentResult,
    AgentExecutionStatus,
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    StandardAgentId,
)

demographics_output = AgentResult(
    agent_id=StandardAgentId.DEMOGRAPHICS.value,
    status=AgentExecutionStatus.SUCCESS,
    criteria_results=[
        CriterionResult(
            criterion_id="CRIT_AGE_MIN",
            name="Minimum Age",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=54,
            expected_value=">= 18",
            explanation="Patient is 54 years old, meeting the protocol threshold of >= 18.",
            evidence=EvidenceProvenance(
                source="EHR_Demographics",
                document_id="DEMO_DOC_1001",
                field_name="birth_date",
                extracted_value="1972-04-15",
                source_text="DOB: 04/15/1972, Age: 54",
                confidence=1.0,
            ),
        )
    ],
)
```

### Example 2: `labs_agent` (Missing Data / UNKNOWN Evaluation)
```python
labs_output = AgentResult(
    agent_id=StandardAgentId.LABS.value,
    status=AgentExecutionStatus.SUCCESS,
    criteria_results=[
        CriterionResult(
            criterion_id="CRIT_PLATELET_COUNT",
            name="Platelet Count",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.PASS,
            observed_value=185000,
            expected_value=">= 100000",
            explanation="Platelet count of 185,000 /uL meets protocol requirement.",
            evidence=EvidenceProvenance(
                source="EHR_Lab_Report",
                document_id="LAB_CBC_20261020",
                field_name="platelet_count",
                extracted_value="185 K/uL",
            ),
        ),
        CriterionResult(
            criterion_id="CRIT_CREATININE_CLEARANCE",
            name="Creatinine Clearance",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.UNKNOWN,
            observed_value=None,
            expected_value=">= 50 mL/min",
            explanation="Creatinine clearance was not recorded in the past 30 days.",
            evidence=None,
        ),
    ],
)
```

### Example 3: `medications_agent` (Definitive Exclusion / FAIL)
```python
medications_output = AgentResult(
    agent_id=StandardAgentId.MEDICATIONS.value,
    status=AgentExecutionStatus.SUCCESS,
    criteria_results=[
        CriterionResult(
            criterion_id="CRIT_PRIOR_IMMUNOTHERAPY",
            name="No Prior Anti-PD-1/PD-L1 Therapy",
            criterion_type=CriterionType.MANDATORY,
            status=CriterionStatus.FAIL,
            observed_value="Pembrolizumab administered 2026-08-10",
            expected_value="No prior immune checkpoint inhibitors",
            explanation="Patient received prior pembrolizumab, violating exclusion criteria.",
            evidence=EvidenceProvenance(
                source="EHR_Medication_Administration",
                document_id="MAR_44921",
                field_name="medication_name",
                extracted_value="Pembrolizumab 200mg IV",
                source_text="Administered Pembrolizumab 200mg IV on 08/10/2026 for recurrence.",
                confidence=0.98,
            ),
        )
    ],
)
```

---

## 7. Instructions for Person 1 Integration

1. **Import the Shared Schema**:
   ```python
   from src.matching.schema import (
       AgentResult,
       AgentExecutionStatus,
       CriterionResult,
       CriterionStatus,
       CriterionType,
       EvidenceProvenance,
       StandardAgentId,
   )
   ```
2. **Implement Agent Evaluation Function**:
   Each agent function should accept `(patient_id: str, trial_id: str)` and return an `AgentResult`.
3. **Register or Pass to Coordinator**:
   ```python
   from src.matching.coordinator import EligibilityCoordinator

   coordinator = EligibilityCoordinator()
   report = coordinator.evaluate(
       patient_id="SYNTH_PATIENT_001",
       trial_id="NCT05001234",
       agent_results=[demographics_output, labs_output, medications_output],
       required_agents=["demographics_agent", "labs_agent", "medications_agent"],
       required_criteria=["CRIT_AGE_MIN", "CRIT_PLATELET_COUNT", "CRIT_PRIOR_IMMUNOTHERAPY"],
   )
   ```
4. **Run Unit Tests**:
   Ensure all tests pass:
   ```bash
   pytest -v
   ```
