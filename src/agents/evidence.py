
from datetime import datetime, timezone


def create_evidence(
    patient_id,
    trial_id,
    agent_result,
    criterion,
    source="unknown"
):
    """
    Create a traceable record of an eligibility-agent result.

    This function records evidence; it does not determine
    clinical eligibility or validate the agent's conclusion.
    """

    if not isinstance(agent_result, dict):
        raise ValueError("agent_result must be a dictionary.")

    required_fields = {"agent", "status", "explanation"}

    if not required_fields.issubset(agent_result):
        raise ValueError(
            "agent_result must contain agent, status, and explanation."
        )

    status = str(agent_result["status"]).strip().upper()

    allowed_statuses = {
        "PASS",
        "FAIL",
        "UNKNOWN",
        "NOT_APPLICABLE"
    }

    if status not in allowed_statuses:
        raise ValueError("Unsupported agent result status.")

    if not patient_id or not trial_id:
        raise ValueError("patient_id and trial_id are required.")

    if not criterion or not str(criterion).strip():
        raise ValueError("criterion cannot be empty.")

    return {
        "patient_id": str(patient_id),
        "trial_id": str(trial_id),
        "agent": str(agent_result["agent"]),
        "criterion": str(criterion).strip(),
        "status": status,
        "explanation": str(agent_result["explanation"]),
        "source": str(source),
        "evidence_details": {
            key: value
            for key, value in agent_result.items()
            if key not in {"agent", "status", "explanation"}
        },
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }
