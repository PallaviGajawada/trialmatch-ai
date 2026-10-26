"""Adapter connecting Person 1's clinical eligibility agents to Person 2's canonical matching models."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union
import pandas as pd

from src.agents.age_agent import evaluate_age
from src.agents.diagnosis_agent import evaluate_diagnosis, normalize_condition_name
from src.agents.evidence import create_evidence
from src.agents.exclusion_agent import evaluate_exclusion
from src.agents.lab_agent import evaluate_lab
from src.matching.schema import (
    AgentExecutionStatus,
    AgentResult,
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
)

logger = logging.getLogger(__name__)


def _sanitize_criterion_id(prefix: str, identifier: str) -> str:
    """Generate a stable, clean criterion identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(identifier).strip()).strip("_").upper()
    return f"{prefix}_{cleaned}" if cleaned else prefix


class DatasetUnavailableError(Exception):
    """Raised when required local clinical datasets are missing."""


class ClinicalAgentsAdapter:
    """
    Adapter that integrates Person 1's domain eligibility agents into Person 2's
    canonical matching schema and coordinator interfaces.

    Responsibilities:
    - Receive or lazily load patient demographics, conditions, observations, and trial records.
    - Invoke only implemented agents whose input parameters can be satisfied.
    - Transform Person 1's flat result dictionaries into canonical AgentResult and CriterionResult models.
    - Enforce clinical safety:
        * Never map NOT_APPLICABLE to PASS.
        * Never map missing/unknown clinical data to PASS or FAIL.
        * Preserve provenance and evidence details.
        * Do not assume unimplemented medication or broad-condition criteria passed.
    """

    def __init__(
        self,
        patients: Optional[pd.DataFrame] = None,
        conditions: Optional[pd.DataFrame] = None,
        observations: Optional[pd.DataFrame] = None,
        trials: Optional[Sequence[Dict[str, Any]]] = None,
        criteria_specs: Optional[Mapping[str, Dict[str, Any]]] = None,
        data_dir: Optional[Union[str, Path]] = None,
    ):
        self._patients = patients
        self._conditions = conditions
        self._observations = observations
        self._trials_list = list(trials) if trials is not None else None
        self._trials_by_id: Optional[Dict[str, Dict[str, Any]]] = None
        if self._trials_list is not None:
            self._trials_by_id = {
                str(t.get("nct_id") or t.get("trial_id")): t
                for t in self._trials_list
                if t.get("nct_id") or t.get("trial_id")
            }
        self.criteria_specs = dict(criteria_specs) if criteria_specs else {}
        self.data_dir = Path(data_dir) if data_dir else Path("data")

    def is_configured(self) -> bool:
        """
        Check whether patient and trial data are configured and accessible,
        either through injected in-memory DataFrames or verified presence of
        local dataset files on disk. Does NOT load patient records into memory.
        """
        if self._patients is not None:
            return True

        synthea_dir = self.data_dir / "patients" / "synthea"
        patients_csv = synthea_dir / "patients.csv"
        conditions_csv = synthea_dir / "conditions.csv"
        observations_csv = synthea_dir / "observations.csv"

        return (
            patients_csv.is_file()
            and conditions_csv.is_file()
            and observations_csv.is_file()
        )

    # -------------------------------------------------------------------------
    # Lazy Data Resolution
    # -------------------------------------------------------------------------

    def _ensure_patients_loaded(self) -> pd.DataFrame:
        if self._patients is not None:
            return self._patients

        try:
            from src.ingestion.load_synthea import load_synthea_data
            from src.normalization.normalize_patients import (
                normalize_conditions,
                normalize_observations,
                normalize_patients,
            )

            synthea_dir = self.data_dir / "patients" / "synthea"
            raw = load_synthea_data(data_dir=synthea_dir)
            self._patients = normalize_patients(raw["patients"])
            self._conditions = normalize_conditions(raw["conditions"])
            self._observations = normalize_observations(raw["observations"])
            return self._patients
        except Exception as exc:
            raise DatasetUnavailableError(
                f"Synthetic patient datasets are unavailable: {exc}"
            ) from exc

    def _ensure_conditions_loaded(self) -> pd.DataFrame:
        if self._conditions is not None:
            return self._conditions
        self._ensure_patients_loaded()
        assert self._conditions is not None
        return self._conditions

    def _ensure_observations_loaded(self) -> pd.DataFrame:
        if self._observations is not None:
            return self._observations
        self._ensure_patients_loaded()
        assert self._observations is not None
        return self._observations

    def _get_trial(self, trial_id: str) -> Optional[Dict[str, Any]]:
        """Lookup trial record by trial_id or nct_id."""
        if self._trials_by_id is not None:
            return self._trials_by_id.get(str(trial_id).strip())

        # Attempt to load local trial json if exists
        trials_file = self.data_dir / "trials" / "diabetes_trials.json"
        if trials_file.exists():
            try:
                import json

                with trials_file.open("r", encoding="utf-8") as f:
                    trials_data = json.load(f)
                if isinstance(trials_data, list):
                    self._trials_by_id = {
                        str(t.get("nct_id") or t.get("trial_id")): t
                        for t in trials_data
                        if isinstance(t, dict)
                    }
                    return self._trials_by_id.get(str(trial_id).strip())
            except Exception as err:
                logger.warning("Could not load trials JSON file: %s", err)

        return None

    def _get_criteria_spec(
        self, trial_id: str, trial: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Resolve criteria specification for the given trial."""
        if trial_id in self.criteria_specs:
            return self.criteria_specs[trial_id]

        # Default standard criteria spec for Type 2 Diabetes trials
        return {
            "all_criteria_accounted_for": False,
            "diagnosis": {
                "condition": "Type 2 Diabetes",
                "direction": "inclusion",
            },
            "labs": [
                {
                    "test_name": "HbA1c",
                    "operator": "<=",
                    "threshold": 8.0,
                    "unit": "%",
                }
            ],
            "exclusions": ["Heart Failure"],
            "unsupported_criteria": [],
        }

    def _find_patient_record(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Extract a single patient record dictionary from normalized patients table."""
        try:
            patients_df = self._ensure_patients_loaded()
            matches = patients_df[
                patients_df["patient_id"].astype("string").str.strip()
                == str(patient_id).strip()
            ]
            if len(matches) == 1:
                return matches.iloc[0].to_dict()
        except Exception as exc:
            logger.debug("Patient lookup exception for %s: %s", patient_id, exc)
        return None

    # -------------------------------------------------------------------------
    # Canonical Transformation Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _map_status(raw_status: Any) -> Tuple[CriterionStatus, bool]:
        """
        Map Person 1 status string to Person 2 CriterionStatus.

        Returns:
            Tuple of (CriterionStatus, is_not_applicable_flag).

        Clinical Safety Rules:
        - Never map NOT_APPLICABLE to PASS.
        - Never map missing or invalid status to PASS.
        """
        status_str = str(raw_status).strip().upper() if raw_status else "UNKNOWN"

        if status_str == "PASS":
            return CriterionStatus.PASS, False
        if status_str == "FAIL":
            return CriterionStatus.FAIL, False
        if status_str == "NOT_APPLICABLE":
            # Semantic limitation documentation:
            # Person 2's schema strictly allows PASS, FAIL, UNKNOWN.
            # In clinical screening, a non-applicable requirement is not a verified PASS.
            # We conservatively map to UNKNOWN and mark criterion as OPTIONAL so it does
            # not block evaluation while documenting non-applicability without silent pass.
            return CriterionStatus.UNKNOWN, True
        return CriterionStatus.UNKNOWN, False

    @staticmethod
    def _build_provenance(
        patient_id: str,
        trial_id: str,
        agent_result: Dict[str, Any],
        criterion: str,
        source: str = "Clinical_Record",
    ) -> EvidenceProvenance:
        """Construct canonical EvidenceProvenance from Person 1 agent result."""
        try:
            evidence_dict = create_evidence(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_result=agent_result,
                criterion=criterion,
                source=source,
            )
            return EvidenceProvenance(
                source=evidence_dict.get("source") or source or "Unknown",
                field_name=criterion,
                extracted_value=agent_result.get("value")
                or agent_result.get("age")
                or agent_result.get("evidence"),
                timestamp=evidence_dict.get("recorded_at"),
                metadata=evidence_dict.get("evidence_details", {}),
            )
        except Exception:
            return EvidenceProvenance(
                source=source or "Unknown",
                field_name=criterion,
                extracted_value=agent_result.get("value")
                or agent_result.get("age")
                or agent_result.get("evidence"),
                metadata={
                    k: v
                    for k, v in agent_result.items()
                    if k not in {"agent", "status", "explanation"}
                },
            )

    # -------------------------------------------------------------------------
    # Individual Agent Runners
    # -------------------------------------------------------------------------

    def run_age_agent(self, patient_id: str, trial_id: str) -> AgentResult:
        """
        Execute Person 1's age_agent and return canonical AgentResult.
        """
        agent_id = "age_agent"
        trial = self._get_trial(trial_id)
        if trial is None:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_AGE",
                        name="Age Limit Requirement",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.UNKNOWN,
                        explanation=f"Trial '{trial_id}' was not found in trial registry; cannot evaluate age limits.",
                    )
                ],
            )

        patient = self._find_patient_record(patient_id)
        if patient is None:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_AGE",
                        name="Age Limit Requirement",
                        criterion_type=CriterionType.MANDATORY,
                        status=CriterionStatus.UNKNOWN,
                        explanation="Patient record was not found in normalized demographics table.",
                    )
                ],
            )

        try:
            raw_result = evaluate_age(patient, trial)
            status, is_na = self._map_status(raw_result.get("status"))

            # If NOT_APPLICABLE, it is OPTIONAL and UNKNOWN; otherwise MANDATORY
            criterion_type = (
                CriterionType.OPTIONAL if is_na else CriterionType.MANDATORY
            )
            min_age = trial.get("minimum_age")
            max_age = trial.get("maximum_age")
            expected_val = (
                f"Min: {min_age or 'None'}, Max: {max_age or 'None'}"
                if (min_age or max_age)
                else "No age limits specified"
            )

            evidence = self._build_provenance(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_result=raw_result,
                criterion="Age limits",
                source=trial.get("source") or "Trial_Protocol",
            )

            explanation = raw_result.get("explanation", "")
            if is_na:
                explanation = (
                    f"{explanation} [Canonical schema limitation: NOT_APPLICABLE mapped "
                    f"conservatively to UNKNOWN (OPTIONAL) criterion for clinical safety]."
                )

            criterion = CriterionResult(
                criterion_id="CRIT_AGE",
                name="Age Limit Requirement",
                criterion_type=criterion_type,
                status=status,
                observed_value=raw_result.get("age"),
                expected_value=expected_val,
                explanation=explanation,
                evidence=evidence,
                agent_id=agent_id,
            )

            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[criterion],
            )
        except Exception as exc:
            logger.exception("Error executing age_agent: %s", exc)
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=f"age_agent exception: {exc}",
            )

    def run_diagnosis_agent(self, patient_id: str, trial_id: str) -> AgentResult:
        """
        Execute Person 1's diagnosis_agent and return canonical AgentResult.
        """
        agent_id = "diagnosis_agent"
        trial = self._get_trial(trial_id) or {"trial_id": trial_id}
        spec = self._get_criteria_spec(trial_id, trial)
        diagnosis_spec = spec.get("diagnosis")

        if not diagnosis_spec:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_DIAGNOSIS_GENERAL",
                        name="Primary Diagnosis Inclusion",
                        criterion_type=CriterionType.OPTIONAL,
                        status=CriterionStatus.UNKNOWN,
                        explanation="No specific diagnosis criteria were mapped for this trial.",
                    )
                ],
            )

        required_condition = diagnosis_spec.get("condition", "Type 2 Diabetes")
        direction = diagnosis_spec.get("direction", "inclusion")
        criterion_id = _sanitize_criterion_id(
            "CRIT_DIAGNOSIS", normalize_condition_name(required_condition)
        )

        try:
            conditions_df = self._ensure_conditions_loaded()
            raw_result = evaluate_diagnosis(
                patient_id=patient_id,
                conditions=conditions_df,
                required_condition=required_condition,
                direction=direction,
            )
            status, _ = self._map_status(raw_result.get("status"))

            evidence = self._build_provenance(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_result=raw_result,
                criterion=f"Diagnosis: {required_condition}",
                source="EHR_Conditions",
            )

            criterion = CriterionResult(
                criterion_id=criterion_id,
                name=f"Diagnosis: {required_condition}",
                criterion_type=CriterionType.MANDATORY,
                status=status,
                observed_value=raw_result.get("evidence"),
                expected_value=f"{direction.capitalize()} of {required_condition}",
                explanation=raw_result.get("explanation", ""),
                evidence=evidence,
                agent_id=agent_id,
            )

            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[criterion],
            )
        except DatasetUnavailableError as err:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=str(err),
            )
        except Exception as exc:
            logger.exception("Error executing diagnosis_agent: %s", exc)
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=f"diagnosis_agent exception: {exc}",
            )

    def run_lab_agent(self, patient_id: str, trial_id: str) -> AgentResult:
        """
        Execute Person 1's lab_agent for all specified lab criteria and return canonical AgentResult.
        """
        agent_id = "lab_agent"
        trial = self._get_trial(trial_id) or {"trial_id": trial_id}
        spec = self._get_criteria_spec(trial_id, trial)
        labs_spec = spec.get("labs", [])

        if not labs_spec:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_LAB_GENERAL",
                        name="Laboratory Thresholds",
                        criterion_type=CriterionType.OPTIONAL,
                        status=CriterionStatus.UNKNOWN,
                        explanation="No specific laboratory criteria were configured for this trial.",
                    )
                ],
            )

        try:
            observations_df = self._ensure_observations_loaded()
            criteria_results: List[CriterionResult] = []

            for lab in labs_spec:
                if not isinstance(lab, dict):
                    continue
                test_name = lab.get("test_name", "Unknown_Lab")
                operator = lab.get("operator", "<=")
                threshold = lab.get("threshold", 0.0)
                unit = lab.get("unit")
                criterion_id = _sanitize_criterion_id("CRIT_LAB", test_name)

                raw_result = evaluate_lab(
                    observations=observations_df,
                    patient_id=patient_id,
                    test_name=test_name,
                    operator=operator,
                    threshold=threshold,
                    expected_unit=unit,
                )
                status, _ = self._map_status(raw_result.get("status"))

                evidence = self._build_provenance(
                    patient_id=patient_id,
                    trial_id=trial_id,
                    agent_result=raw_result,
                    criterion=f"Lab: {test_name}",
                    source="EHR_Observations",
                )

                expected_desc = f"{operator} {threshold}"
                if unit:
                    expected_desc += f" {unit}"

                obs_val = raw_result.get("value")
                if obs_val is not None and raw_result.get("unit"):
                    obs_val = f"{obs_val} {raw_result.get('unit')}"

                criteria_results.append(
                    CriterionResult(
                        criterion_id=criterion_id,
                        name=f"Laboratory: {test_name}",
                        criterion_type=CriterionType.MANDATORY,
                        status=status,
                        observed_value=obs_val,
                        expected_value=expected_desc,
                        explanation=raw_result.get("explanation", ""),
                        evidence=evidence,
                        agent_id=agent_id,
                    )
                )

            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=criteria_results,
            )
        except DatasetUnavailableError as err:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=str(err),
            )
        except Exception as exc:
            logger.exception("Error executing lab_agent: %s", exc)
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=f"lab_agent exception: {exc}",
            )

    def run_exclusion_agent(self, patient_id: str, trial_id: str) -> AgentResult:
        """
        Execute Person 1's exclusion_agent for all specified exclusion criteria and return canonical AgentResult.
        """
        agent_id = "exclusion_agent"
        trial = self._get_trial(trial_id) or {"trial_id": trial_id}
        spec = self._get_criteria_spec(trial_id, trial)
        exclusions_spec = spec.get("exclusions", [])

        if not exclusions_spec:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[
                    CriterionResult(
                        criterion_id="CRIT_EXCLUSION_GENERAL",
                        name="Protocol Exclusion Conditions",
                        criterion_type=CriterionType.OPTIONAL,
                        status=CriterionStatus.UNKNOWN,
                        explanation="No protocol exclusion conditions were configured for this trial.",
                    )
                ],
            )

        try:
            conditions_df = self._ensure_conditions_loaded()
            criteria_results: List[CriterionResult] = []

            for exclusion in exclusions_spec:
                if not isinstance(exclusion, str) or not exclusion.strip():
                    continue
                criterion_id = _sanitize_criterion_id(
                    "CRIT_EXCLUSION", normalize_condition_name(exclusion)
                )

                raw_result = evaluate_exclusion(
                    patient_id=patient_id,
                    conditions=conditions_df,
                    excluded_condition=exclusion,
                )
                status, _ = self._map_status(raw_result.get("status"))

                evidence = self._build_provenance(
                    patient_id=patient_id,
                    trial_id=trial_id,
                    agent_result=raw_result,
                    criterion=f"Exclusion: {exclusion}",
                    source="EHR_Conditions",
                )

                criteria_results.append(
                    CriterionResult(
                        criterion_id=criterion_id,
                        name=f"Exclusion: {exclusion}",
                        criterion_type=CriterionType.MANDATORY,
                        status=status,
                        observed_value=raw_result.get("condition")
                        if status == CriterionStatus.FAIL
                        else None,
                        expected_value=f"Absence of {exclusion}",
                        explanation=raw_result.get("explanation", ""),
                        evidence=evidence,
                        agent_id=agent_id,
                    )
                )

            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=criteria_results,
            )
        except DatasetUnavailableError as err:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=str(err),
            )
        except Exception as exc:
            logger.exception("Error executing exclusion_agent: %s", exc)
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.ERROR,
                error_message=f"exclusion_agent exception: {exc}",
            )

    def run_unsupported_criteria(self, patient_id: str, trial_id: str) -> AgentResult:
        """
        Handle criteria that lack automated agent implementations (e.g. medications,
        prior procedures, pregnancy) ensuring they are marked UNKNOWN for clinical review
        and never inferred as passed.
        """
        agent_id = "unsupported_criteria_agent"
        trial = self._get_trial(trial_id) or {"trial_id": trial_id}
        spec = self._get_criteria_spec(trial_id, trial)
        unsupported = spec.get("unsupported_criteria", [])

        if not unsupported:
            return AgentResult(
                agent_id=agent_id,
                status=AgentExecutionStatus.SUCCESS,
                criteria_results=[],
            )

        criteria_results: List[CriterionResult] = []
        for item in unsupported:
            name = str(item)
            cid = _sanitize_criterion_id("CRIT_UNSUPPORTED", name)
            criteria_results.append(
                CriterionResult(
                    criterion_id=cid,
                    name=name,
                    criterion_type=CriterionType.MANDATORY,
                    status=CriterionStatus.UNKNOWN,
                    explanation=(
                        f"Criterion '{name}' has no automated agent implemented (e.g. medication, "
                        "prior therapy, pregnancy). Under clinical safety rules, this criterion "
                        "cannot be inferred as PASS and requires human clinical review."
                    ),
                    agent_id=agent_id,
                )
            )

        return AgentResult(
            agent_id=agent_id,
            status=AgentExecutionStatus.SUCCESS,
            criteria_results=criteria_results,
        )

    # -------------------------------------------------------------------------
    # Coordinator Integration Helper
    # -------------------------------------------------------------------------

    def as_runners_dict(self) -> Dict[str, Callable[[str, str], AgentResult]]:
        """
        Return dictionary of callable runners compatible with EligibilityCoordinator.
        """
        return {
            "age_agent": self.run_age_agent,
            "diagnosis_agent": self.run_diagnosis_agent,
            "lab_agent": self.run_lab_agent,
            "exclusion_agent": self.run_exclusion_agent,
            "unsupported_criteria_agent": self.run_unsupported_criteria,
        }

    def evaluate_all(self, patient_id: str, trial_id: str) -> List[AgentResult]:
        """
        Invoke all implemented agents and return list of canonical AgentResults.
        """
        results = [
            self.run_age_agent(patient_id, trial_id),
            self.run_diagnosis_agent(patient_id, trial_id),
            self.run_lab_agent(patient_id, trial_id),
            self.run_exclusion_agent(patient_id, trial_id),
        ]
        unsupported = self.run_unsupported_criteria(patient_id, trial_id)
        if unsupported.criteria_results:
            results.append(unsupported)
        return results
