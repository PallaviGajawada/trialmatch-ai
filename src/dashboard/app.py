"""TrialMatch AI — Clinical Trial Patient Eligibility Screening Dashboard."""

from __future__ import annotations

import os
import streamlit as st
from typing import Optional, Tuple
import pandas as pd

from src.dashboard.api_client import (
    BackendConnectionError,
    BackendHttpError,
    BackendResponseError,
    BackendTimeoutError,
    TrialMatchApiClient,
)
from src.dashboard.demo_data import (
    DEMO_SCENARIOS,
    SAMPLE_PATIENTS,
    SAMPLE_TRIALS,
)
from src.dashboard.presentation import (
    format_status_badge,
    prepare_criteria_table_data,
    summarize_review_items,
)
from src.matching.schema import OverallStatus, ScreeningReport


def initialize_page():
    """Configure Streamlit page layout and title."""
    st.set_page_config(
        page_title="TrialMatch AI — Clinical Trial Screening",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar() -> Tuple[str, bool, Optional[str]]:
    """
    Render configuration and health status sidebar.

    Returns:
        Tuple of (api_base_url, use_synthetic_demo, selected_demo_scenario).
    """
    st.sidebar.title("🔬 TrialMatch AI")
    st.sidebar.markdown("**Screening Orchestration Dashboard**")
    st.sidebar.divider()

    default_url = os.environ.get("TRIALMATCH_API_URL", "http://127.0.0.1:8000")
    api_url = st.sidebar.text_input(
        "Backend API Base URL",
        value=default_url,
        help="FastAPI backend host URL. Configurable via TRIALMATCH_API_URL.",
    )

    client = TrialMatchApiClient(base_url=api_url, timeout_seconds=4.0)

    # Health check display
    st.sidebar.subheader("Backend Health & Agents")
    try:
        health = client.check_health()
        agents_configured = health.get("agents_configured", False)
        registered_agents = health.get("registered_agents", [])

        if agents_configured:
            st.sidebar.success("● Backend Operational (Agents Active)")
            st.sidebar.caption(f"Active Agents: {', '.join(registered_agents)}")
        else:
            st.sidebar.warning("⚠ Backend Online (Agents Unconfigured)")
            st.sidebar.caption(
                "Person 1 agents are not yet registered. Live evaluations will indicate incomplete pipeline."
            )
    except BackendConnectionError:
        st.sidebar.error("✖ Backend Disconnected")
        st.sidebar.caption("Cannot reach FastAPI backend. Verify server is running.")
    except Exception as exc:
        st.sidebar.error(f"✖ Health Check Failed: {exc}")

    st.sidebar.divider()
    st.sidebar.subheader("Demonstration Mode")
    use_synthetic_demo = st.sidebar.checkbox(
        "Enable Synthetic Demonstration Mode",
        value=False,
        help="Explore synthetic clinical scenarios with pre-defined findings while agents are in development.",
    )

    selected_scenario = None
    if use_synthetic_demo:
        st.sidebar.info("🧪 Synthetic Demo Active (Simulated Scenarios)")
        selected_scenario = st.sidebar.selectbox(
            "Select Scenario",
            options=list(DEMO_SCENARIOS.keys()),
        )
        scenario_info = DEMO_SCENARIOS[selected_scenario]
        st.sidebar.caption(scenario_info["description"])

    return api_url, use_synthetic_demo, selected_scenario


def render_header():
    """Render title, purpose statement, and clinical disclaimer banner."""
    st.title("TrialMatch AI")
    st.markdown("### Clinical Trial Patient Eligibility Screening Support")
    st.markdown(
        "TrialMatch AI evaluates patient clinical data against clinical trial protocol inclusion "
        "and exclusion criteria using deterministic rule-based orchestration."
    )

    # Required Medical Disclaimer Banner
    st.info(
        "🛡 **CLINICAL RESEARCH DISCLAIMER**: TrialMatch AI is an investigational decision-support prototype. "
        "Automated screening results do **not** constitute a medical diagnosis, clinical judgment, or definitive "
        "trial enrollment decision. All matching reports require independent review by qualified clinical research staff."
    )


def render_evaluation_inputs(
    use_synthetic_demo: bool, selected_scenario: Optional[str]
) -> Tuple[str, str, bool]:
    """Render patient and trial identifier selection inputs."""
    st.subheader("1. Select Patient and Clinical Trial")

    col1, col2 = st.columns(2)

    if use_synthetic_demo and selected_scenario:
        scenario_data = DEMO_SCENARIOS[selected_scenario]
        with col1:
            patient_id = st.text_input(
                "Patient Identifier",
                value=scenario_data["patient_id"],
                help="Synthetic patient record identifier.",
            )
        with col2:
            trial_id = st.text_input(
                "Clinical Trial Identifier",
                value=scenario_data["trial_id"],
                help="Target clinical trial protocol ID (e.g. ClinicalTrials.gov NCT identifier).",
            )
    else:
        patient_options = [p[0] for p in SAMPLE_PATIENTS] + ["Custom Patient ID..."]
        trial_options = [t[0] for t in SAMPLE_TRIALS] + ["Custom Trial ID..."]

        with col1:
            selected_pat = st.selectbox(
                "Patient Identifier (or select sample)",
                options=patient_options,
                index=0,
            )
            if selected_pat == "Custom Patient ID...":
                patient_id = st.text_input("Enter Custom Patient ID", value="")
            else:
                patient_id = selected_pat

        with col2:
            selected_tr = st.selectbox(
                "Clinical Trial Identifier (or select sample)",
                options=trial_options,
                index=0,
            )
            if selected_tr == "Custom Trial ID...":
                trial_id = st.text_input("Enter Custom Trial ID", value="NCT05001234")
            else:
                trial_id = selected_tr

    evaluate_clicked = st.button("Evaluate Eligibility", type="primary", use_container_width=True)
    return patient_id.strip(), trial_id.strip(), evaluate_clicked


def display_screening_report(report: ScreeningReport):
    """Render the complete structured screening report."""
    st.divider()
    st.subheader("2. Eligibility Evaluation Report")

    # Header metadata
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.markdown(f"**Patient ID:** `{report.patient_id}`")
    col_m2.markdown(f"**Trial ID:** `{report.trial_id}`")
    col_m3.markdown(f"**Timestamp:** `{report.timestamp}`")

    # Overall Status Callout with accessible text and visual cues
    badge = format_status_badge(report.overall_status)
    status_label = badge["label"]
    status_symbol = badge["symbol"]
    status_desc = badge["description"]

    if report.overall_status == OverallStatus.POTENTIAL_MATCH:
        st.success(
            f"### {status_symbol} {status_label}\n\n**Assessment:** {status_desc}"
        )
    elif report.overall_status == OverallStatus.NOT_A_MATCH:
        st.error(
            f"### {status_symbol} {status_label}\n\n**Assessment:** {status_desc}"
        )
    else:
        st.warning(
            f"### {status_symbol} {status_label}\n\n**Assessment:** {status_desc}"
        )

    # Summary Counts Metrics
    counts = report.counts
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_col1.metric("Total Evaluated", counts.total_criteria)
    m_col2.metric("Mandatory Passed", f"{counts.mandatory_passed} / {counts.mandatory_total}")
    m_col3.metric("Mandatory Failed", counts.mandatory_failed)
    m_col4.metric("Mandatory Unknown", counts.mandatory_unknown)
    m_col5.metric("Human Review", "REQUIRED" if report.requires_human_review else "NOT REQUIRED")

    # Review Section
    review_info = summarize_review_items(report)
    with st.expander("🔍 Review Section & Audit Reasons", expanded=report.requires_human_review):
        if report.requires_human_review:
            st.markdown("⚠️ **Action Required**: This patient's screening report requires clinical investigator review.")

        st.markdown("**Reasons Supporting Status Determination:**")
        for reason in report.reasons:
            st.markdown(f"- {reason}")

        if review_info["mandatory_failures"]:
            st.markdown("**Mandatory Criteria Failures:**")
            for fail in review_info["mandatory_failures"]:
                st.markdown(f"- ❌ {fail}")

        if review_info["unknown_criteria"]:
            st.markdown("**Unknown / Pending Information:**")
            for unk in review_info["unknown_criteria"]:
                st.markdown(f"- ❓ {unk}")

        if report.missing_agents:
            st.markdown(f"**Missing Required Agents:** {', '.join(report.missing_agents)}")

        if report.missing_criteria:
            st.markdown(f"**Missing Required Criteria:** {', '.join(report.missing_criteria)}")

        if report.errors:
            st.markdown("**Recorded Validation / Execution Errors:**")
            for err in report.errors:
                st.markdown(f"- ⚠️ {err}")

    # Criterion-Level Results Table
    st.subheader("3. Criterion-Level Evaluation Findings")
    if not report.criterion_results:
        st.info("No individual criterion evaluation findings were returned by reporting agents.")
    else:
        table_data = prepare_criteria_table_data(report.criterion_results)
        df = pd.DataFrame(table_data)
        st.dataframe(
            df,
            column_config={
                "Criterion ID": st.column_config.TextColumn(width="medium"),
                "Name": st.column_config.TextColumn(width="medium"),
                "Type": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="small"),
                "Observed Value": st.column_config.TextColumn(width="medium"),
                "Expected Value": st.column_config.TextColumn(width="medium"),
                "Explanation": st.column_config.TextColumn(width="large"),
                "Provenance Citation": st.column_config.TextColumn(width="large"),
                "Evaluating Agent": st.column_config.TextColumn(width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Deep Provenance Details
        with st.expander("📄 Evidence Provenance & Audit Citations", expanded=False):
            for c in report.criterion_results:
                st.markdown(f"**Criterion `{c.criterion_id}`** ({c.name or 'No label'}) — Status: **{c.status.value}**")
                if c.evidence:
                    if isinstance(c.evidence, dict):
                        st.json(c.evidence)
                    elif hasattr(c.evidence, "model_dump"):
                        st.json(c.evidence.model_dump())
                    else:
                        st.text(str(c.evidence))
                else:
                    st.caption("No citation record associated with this criterion.")
                st.divider()


def main():
    """Main dashboard execution entrypoint."""
    initialize_page()
    api_url, use_synthetic_demo, selected_scenario = render_sidebar()
    render_header()

    patient_id, trial_id, evaluate_clicked = render_evaluation_inputs(
        use_synthetic_demo, selected_scenario
    )

    if evaluate_clicked:
        if not patient_id or not trial_id:
            st.error("Please provide both a Patient ID and a Clinical Trial ID.")
            return

        client = TrialMatchApiClient(base_url=api_url)

        # Determine agent results to send (if synthetic demo mode is active)
        demo_agent_results = None
        if use_synthetic_demo and selected_scenario:
            demo_agent_results = DEMO_SCENARIOS[selected_scenario]["agent_results"]

        with st.spinner("Connecting to backend and evaluating eligibility..."):
            try:
                report = client.evaluate(
                    patient_id=patient_id,
                    trial_id=trial_id,
                    agent_results=demo_agent_results,
                )
                display_screening_report(report)
            except BackendConnectionError as err:
                st.error(f"Connection Error: {err}")
                st.info(
                    "To start the FastAPI backend, run:\n```bash\nuvicorn src.api.app:app --reload\n```"
                )
            except BackendTimeoutError as err:
                st.error(f"Timeout Error: {err}")
            except BackendHttpError as err:
                st.error(f"Backend Returned HTTP Error: {err.detail}")
            except BackendResponseError as err:
                st.error(f"Invalid Backend Response: {err}")
            except Exception as exc:
                st.error(f"An unexpected error occurred: {exc}")


if __name__ == "__main__":
    main()
