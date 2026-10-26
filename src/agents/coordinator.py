
def evaluate_eligibility(patient_id, trial_id, agent_results):
    """
    Combine individual eligibility-agent results into one outcome.

    Overall outcomes:
    - Potential match
    - Not a match
    - Requires review

    This is a research prototype, not a clinical decision tool.
    """

    def review_result(reason):
        return {
            "patient_id": patient_id,
            "trial_id": trial_id,
            "status": "Requires review",
            "explanation": reason,
            "criteria_results": agent_results
        }

    # Check whether agent results are available.
    if not isinstance(agent_results, list) or not agent_results:
        return review_result(
            "No eligibility results were provided for evaluation."
        )

    valid_statuses = {
        "PASS",
        "FAIL",
        "UNKNOWN",
        "NOT_APPLICABLE"
    }

    statuses = []

    for result in agent_results:
        # Invalid results must not be treated as a successful match.
        if not isinstance(result, dict):
            return review_result(
                "An agent returned an invalid result."
            )

        status = result.get("status")

        if not isinstance(status, str):
            return review_result(
                "An agent result has no valid status."
            )

        status = status.strip().upper()

        if status not in valid_statuses:
            return review_result(
                "An agent returned an unsupported status."
            )

        statuses.append(status)

    # A confirmed failure of a mandatory criterion means no match.
    if "FAIL" in statuses:
        return {
            "patient_id": patient_id,
            "trial_id": trial_id,
            "status": "Not a match",
            "explanation": (
                "At least one evaluated criterion was not satisfied."
            ),
            "criteria_results": agent_results
        }

    # Missing or uncertain information requires human review.
    if "UNKNOWN" in statuses:
        return review_result(
            "One or more criteria could not be evaluated reliably."
        )

    # NOT_APPLICABLE is neutral, not a passing criterion.
    if all(status == "NOT_APPLICABLE" for status in statuses):
        return review_result(
            "No applicable eligibility criteria were evaluated."
        )

    # Potential match requires at least one PASS and no failures
    # or unresolved criteria.
    if all(
        status in {"PASS", "NOT_APPLICABLE"}
        for status in statuses
    ) and "PASS" in statuses:
        return {
            "patient_id": patient_id,
            "trial_id": trial_id,
            "status": "Potential match",
            "explanation": (
                "All evaluated applicable criteria passed. "
                "Human review is still required."
            ),
            "criteria_results": agent_results
        }

    return review_result(
        "The overall eligibility outcome could not be determined."
    )
