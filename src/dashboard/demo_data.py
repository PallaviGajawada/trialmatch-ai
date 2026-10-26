"""Synthetic test fixtures and demonstration scenarios for TrialMatch AI dashboard.

DISCLAIMER: All patient identifiers, measurements, and clinical records in this module
are entirely synthetic and fabricated for software testing and demonstration purposes.
They do NOT represent real individuals or authentic clinical decisions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from src.matching.schema import (
    AgentExecutionStatus,
    AgentResult,
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    StandardAgentId,
)

SAMPLE_PATIENTS = [
    ("SYNTH-PAT-001", "SYNTH-PAT-001 (Adult, NSCLC Stage IV, Normal Organ Function)"),
    ("SYNTH-PAT-002", "SYNTH-PAT-002 (Pediatric 15yo, Failing Age Inclusion)"),
    ("SYNTH-PAT-003", "SYNTH-PAT-003 (Adult NSCLC, Prior Immunotherapy Exclusion)"),
    ("SYNTH-PAT-004", "SYNTH-PAT-004 (Adult NSCLC, Molecular Labs Pending)"),
]

SAMPLE_TRIALS = [
    ("NCT05001234", "NCT05001234 (Phase III First-Line NSCLC Pembrolizumab Combination)"),
    ("NCT05123456", "NCT05123456 (Phase II Targeted Therapy for EGFR Exon 19 Mutations)"),
]

DEMO_SCENARIOS = {
    "Scenario 1: Potential Match": {
        "description": "All mandatory eligibility criteria pass. Prototype evaluates to POTENTIAL_MATCH.",
        "patient_id": "SYNTH-PAT-001",
        "trial_id": "NCT05001234",
        "agent_results": [
            AgentResult(
                agent_id=StandardAgentId.DEMOGRAPHICS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_AGE",
                        name="Adult Age Requirement",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value=48,
                        expected_value=">= 18",
                        explanation="Patient age is 48, satisfying >= 18 inclusion criterion.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_EHR_Demographics",
                            document_id="SYNTH_DOC_DEMO_01",
                            field_name="birth_date",
                            extracted_value="1978-06-12",
                        ),
                    )
                ],
            ).model_dump(),
            AgentResult(
                agent_id=StandardAgentId.CONDITIONS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_DIAGNOSIS",
                        name="Histologically Confirmed NSCLC",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value="Non-small cell lung cancer",
                        expected_value="NSCLC",
                        explanation="Histologically confirmed non-small cell lung carcinoma.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_Pathology_Report",
                            document_id="SYNTH_PATH_881",
                            field_name="primary_histology",
                            extracted_value="Adenocarcinoma of Lung",
                        ),
                    ),
                    CriterionResult(
                        criterion_id="CRIT_STAGE",
                        name="Metastatic Stage IV Disease",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value="Stage IV",
                        expected_value="Stage IV (AJCC 8th)",
                        explanation="Disease is metastatic Stage IV with pleural involvement.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_Imaging_Report",
                            document_id="SYNTH_CT_992",
                            field_name="staging",
                            extracted_value="Stage IVB",
                        ),
                    ),
                ],
            ).model_dump(),
            AgentResult(
                agent_id=StandardAgentId.LABS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_PLATELETS",
                        name="Adequate Platelet Count",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value=195000,
                        expected_value=">= 100000 /uL",
                        explanation="Platelet count of 195,000 /uL is within the required protocol window.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_Lab_Panel",
                            document_id="SYNTH_LAB_CBC_01",
                            field_name="platelet_count",
                            extracted_value="195 K/uL",
                        ),
                    )
                ],
            ).model_dump(),
        ],
    },
    "Scenario 2: Not a Match": {
        "description": "Patient received prior immunotherapy, triggering a definitive mandatory exclusion failure.",
        "patient_id": "SYNTH-PAT-003",
        "trial_id": "NCT05001234",
        "agent_results": [
            AgentResult(
                agent_id=StandardAgentId.DEMOGRAPHICS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_AGE",
                        name="Adult Age Requirement",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value=55,
                        expected_value=">= 18",
                        explanation="Patient age is 55.",
                    )
                ],
            ).model_dump(),
            AgentResult(
                agent_id=StandardAgentId.MEDICATIONS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_PRIOR_IMMUNOTHERAPY",
                        name="No Prior Immune Checkpoint Inhibitor",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.FAIL,
                        observed_value="Pembrolizumab administered 2026-07-15",
                        expected_value="Treatment-naive to prior anti-PD-1/PD-L1",
                        explanation="Patient previously received pembrolizumab, violating exclusion criteria.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_EHR_MAR",
                            document_id="SYNTH_MED_044",
                            field_name="medication_administration",
                            extracted_value="Pembrolizumab 200mg",
                            source_text="Patient received 3 cycles of prior pembrolizumab.",
                        ),
                    )
                ],
            ).model_dump(),
        ],
    },
    "Scenario 3: Requires Review": {
        "description": "Essential molecular biomarker test is pending, resulting in mandatory UNKNOWN.",
        "patient_id": "SYNTH-PAT-004",
        "trial_id": "NCT05123456",
        "agent_results": [
            AgentResult(
                agent_id=StandardAgentId.DEMOGRAPHICS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_AGE",
                        name="Adult Age Requirement",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.PASS,
                        observed_value=61,
                        expected_value=">= 18",
                        explanation="Age requirement met.",
                    )
                ],
            ).model_dump(),
            AgentResult(
                agent_id=StandardAgentId.LABS.value,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_EGFR_MUTATION",
                        name="EGFR Sensitizing Mutation",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.UNKNOWN,
                        observed_value=None,
                        expected_value="EGFR Exon 19 del or L858R",
                        explanation="Next-generation sequencing panel ordered but pending results; EGFR status unavailable.",
                        evidence=EvidenceProvenance(
                            source="Synthetic_Order_Status",
                            document_id="SYNTH_ORD_5521",
                            field_name="molecular_pathology_order",
                            extracted_value="Order Status: PENDING",
                        ),
                    )
                ],
            ).model_dump(),
        ],
    },
}
