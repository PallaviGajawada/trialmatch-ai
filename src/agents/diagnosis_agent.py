
import re


def normalize_condition_name(name):
    """Standardize a condition name for comparison."""

    if not isinstance(name, str):
        return ""

    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name


def is_type2_diabetes(condition_name):
    """Check for common names of Type 2 Diabetes."""

    name = normalize_condition_name(condition_name)

    patterns = [
        r"\btype 2 diabetes\b",
        r"\btype ii diabetes\b",
        r"\bdiabetes mellitus type 2\b",
        r"\btype 2 diabetes mellitus\b",
        r"\btype ii diabetes mellitus\b"
    ]

    return any(re.search(pattern, name) for pattern in patterns)


def evaluate_diagnosis(
    patient_id,
    conditions,
    required_condition="Type 2 Diabetes",
    direction="inclusion"
):
    """
    Evaluate a documented diagnosis criterion.

    Missing diagnosis records are UNKNOWN, not proof of absence.
    """

    if direction not in ["inclusion", "exclusion"]:
        return {
            "agent": "diagnosis_agent",
            "status": "UNKNOWN",
            "explanation": "Criterion direction is not recognized."
        }

    if not patient_id or conditions is None:
        return {
            "agent": "diagnosis_agent",
            "status": "UNKNOWN",
            "explanation": "Patient ID or condition records are missing."
        }

    required_columns = {"patient_id", "condition"}

    if not required_columns.issubset(conditions.columns):
        return {
            "agent": "diagnosis_agent",
            "status": "UNKNOWN",
            "explanation": "Condition data has an unexpected structure."
        }

    if normalize_condition_name(required_condition) not in [
        "type 2 diabetes",
        "type 2 diabetes mellitus",
        "diabetes mellitus type 2",
        "type ii diabetes",
        "type ii diabetes mellitus"
    ]:
        return {
            "agent": "diagnosis_agent",
            "status": "UNKNOWN",
            "explanation": "This diagnosis is not supported by this agent."
        }

    patient_conditions = conditions[
        conditions["patient_id"].astype("string").str.strip()
        == str(patient_id).strip()
    ]

    matches = patient_conditions[
        patient_conditions["condition"].apply(is_type2_diabetes)
    ]

    if matches.empty:
        return {
            "agent": "diagnosis_agent",
            "status": "UNKNOWN",
            "explanation": (
                "No matching diagnosis was found in the available "
                "records; this does not prove the patient lacks it."
            )
        }

    evidence = matches["condition"].dropna().astype(str).tolist()

    if direction == "exclusion":
        status = "FAIL"
        explanation = (
            "A documented Type 2 Diabetes diagnosis was found, "
            "which conflicts with this exclusion criterion."
        )
    else:
        status = "PASS"
        explanation = (
            "A documented Type 2 Diabetes diagnosis was found."
        )

    return {
        "agent": "diagnosis_agent",
        "status": status,
        "evidence": evidence,
        "explanation": explanation
    }
