"""Presentation and data formatting utilities for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.matching.schema import (
    CriterionResult,
    CriterionStatus,
    CriterionType,
    EvidenceProvenance,
    OverallStatus,
    ScreeningReport,
)


def format_status_badge(overall_status: OverallStatus | str) -> Dict[str, str]:
    """
    Format accessible visual and textual badges for overall eligibility status.

    Does not rely on color alone; includes clear text prefixes, icons, and explanations.
    """
    raw_status = (
        overall_status.value
        if isinstance(overall_status, OverallStatus)
        else str(overall_status).upper()
    )

    if raw_status == OverallStatus.POTENTIAL_MATCH.value:
        return {
            "label": "POTENTIAL MATCH",
            "symbol": "[ MATCH ]",
            "icon": "✓",
            "description": "All evaluated mandatory eligibility criteria have been satisfied.",
            "ui_class": "success",
        }
    elif raw_status == OverallStatus.NOT_A_MATCH.value:
        return {
            "label": "NOT A MATCH",
            "symbol": "[ NO MATCH ]",
            "icon": "✗",
            "description": "One or more mandatory protocol inclusion/exclusion criteria failed.",
            "ui_class": "error",
        }
    elif raw_status == OverallStatus.REQUIRES_REVIEW.value:
        return {
            "label": "REQUIRES REVIEW",
            "symbol": "[ REVIEW REQUIRED ]",
            "icon": "⚠",
            "description": "Eligibility cannot be deterministically resolved due to missing information, conflicts, or unconfigured agents.",
            "ui_class": "warning",
        }
    else:
        return {
            "label": raw_status,
            "symbol": f"[ {raw_status} ]",
            "icon": "ℹ",
            "description": "Status evaluation pending or unassigned.",
            "ui_class": "info",
        }


def format_evidence_provenance(evidence: Any) -> str:
    """Format evidence provenance into a clean human-readable string summary."""
    if evidence is None:
        return "No provenance citation recorded"

    if isinstance(evidence, str):
        return evidence.strip() or "No provenance citation recorded"

    if isinstance(evidence, dict):
        source = evidence.get("source", "Unknown")
        doc_id = evidence.get("document_id")
        field = evidence.get("field_name")
        val = evidence.get("extracted_value")

        parts = [f"Source: {source}"]
        if doc_id:
            parts.append(f"Doc ID: {doc_id}")
        if field:
            parts.append(f"Field: {field}")
        if val is not None:
            parts.append(f"Extracted: {val}")
        return " | ".join(parts)

    if isinstance(evidence, EvidenceProvenance):
        parts = [f"Source: {evidence.source}"]
        if evidence.document_id:
            parts.append(f"Doc ID: {evidence.document_id}")
        if evidence.field_name:
            parts.append(f"Field: {evidence.field_name}")
        if evidence.extracted_value is not None:
            parts.append(f"Extracted: {evidence.extracted_value}")
        return " | ".join(parts)

    return str(evidence)


def prepare_criteria_table_data(
    criterion_results: List[CriterionResult],
) -> List[Dict[str, Any]]:
    """
    Transform CriterionResult objects into structured tabular dictionary rows for UI display.
    """
    rows: List[Dict[str, Any]] = []

    for c in criterion_results:
        # Determine status symbol for accessible display
        if c.status == CriterionStatus.PASS:
            status_display = "✓ PASS"
        elif c.status == CriterionStatus.FAIL:
            status_display = "✗ FAIL"
        elif c.status == CriterionStatus.UNKNOWN:
            status_display = "❓ UNKNOWN"
        else:
            status_display = str(c.status)

        type_display = (
            "Mandatory" if c.criterion_type == CriterionType.MANDATORY else "Optional"
        )

        rows.append(
            {
                "Criterion ID": c.criterion_id,
                "Name": c.name or c.criterion_id,
                "Type": type_display,
                "Status": status_display,
                "Observed Value": (
                    str(c.observed_value)
                    if c.observed_value is not None
                    else "(Unrecorded)"
                ),
                "Expected Value": (
                    str(c.expected_value)
                    if c.expected_value is not None
                    else "(Not specified)"
                ),
                "Explanation": c.explanation or "No explanation provided.",
                "Provenance Citation": format_evidence_provenance(c.evidence),
                "Evaluating Agent": c.agent_id or "Unknown",
            }
        )

    return rows


def summarize_review_items(report: ScreeningReport) -> Dict[str, List[str]]:
    """
    Extract and categorize review items from a ScreeningReport.
    """
    mandatory_failures: List[str] = []
    unknown_criteria: List[str] = []

    for c in report.criterion_results:
        if c.is_mandatory and c.status == CriterionStatus.FAIL:
            mandatory_failures.append(
                f"{c.criterion_id}: Observed {c.observed_value!r}, Expected {c.expected_value!r} — {c.explanation}"
            )
        elif c.is_mandatory and c.status == CriterionStatus.UNKNOWN:
            unknown_criteria.append(
                f"{c.criterion_id}: {c.explanation or 'Missing clinical observation.'}"
            )

    return {
        "reasons": list(report.reasons),
        "mandatory_failures": mandatory_failures,
        "unknown_criteria": unknown_criteria,
        "missing_agents": list(report.missing_agents),
        "missing_criteria": list(report.missing_criteria),
        "errors": list(report.errors),
    }
