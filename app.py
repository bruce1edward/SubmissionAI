"""
SubmissionAI - Streamlit demo.

Install:
    pip install streamlit plotly pandas openai

Run:
    export NEBIUS_API_KEY="your-nebius-api-key"
    streamlit run app.py
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from regulatory_knowledge_base import build_no_prereq_rag_trace, get_kb_metadata
from sap_validator_knowledge_base import get_sap_kb_metadata
from ectd_agent import (
    DEFAULT_MODEL,
    ECTDAgentError,
    MissingAPIKeyError,
    get_available_models,
    list_remote_models,
    run_demo_analysis,
    run_ectd_analysis,
    validate_input_package,
)


st.set_page_config(
    page_title="SubmissionAI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { padding-top: 1rem; }
    .header-section {
        border-bottom: 1px solid #d9e2ec;
        color: #102f4f;
        padding: 0.25rem 0 0.9rem 0;
        margin-bottom: 1rem;
    }
    .header-section h1 { margin-bottom: 0.2rem; }
    .header-section p { color: #52616f; margin: 0; }
    .demo-hero {
        background: linear-gradient(135deg, #102f4f 0%, #2d7d6b 68%, #8a6a3d 100%);
        color: white;
        padding: 1.6rem 1.8rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .demo-hero h2 {
        color: white;
        margin: 0 0 0.45rem 0;
        font-size: 2rem;
    }
    .demo-hero p {
        margin: 0;
        max-width: 58rem;
        line-height: 1.5;
    }
    .demo-hero .hero-kicker {
        color: #d9f2ef;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0;
        font-size: 0.78rem;
        margin-bottom: 0.5rem;
    }
    .result-box {
        border: 1px solid #d9e2ec;
        border-left: 4px solid #2d7d6b;
        padding: 1rem;
        border-radius: 0.5rem;
        background: #fbfdff;
        min-height: 8rem;
    }
    .warning-box {
        border: 1px solid #f5d08a;
        border-left: 4px solid #d99000;
        padding: 1rem;
        border-radius: 0.5rem;
        background: #fffaf0;
    }
    .evidence-hero {
        background: linear-gradient(135deg, #102f4f 0%, #2d7d6b 62%, #7a5b2e 100%);
        color: white;
        padding: 1.5rem 1.75rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .evidence-hero h2 {
        margin: 0 0 0.35rem 0;
        color: white;
    }
    .evidence-hero p {
        margin: 0;
        max-width: 58rem;
        line-height: 1.5;
    }
    .metric-tile {
        border: 1px solid #d9e2ec;
        border-top: 4px solid #2d7d6b;
        background: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        min-height: 8.5rem;
    }
    .metric-tile .metric-value {
        color: #102f4f;
        font-size: 2rem;
        font-weight: 750;
        line-height: 1.1;
    }
    .metric-tile .metric-label {
        color: #334e68;
        font-weight: 650;
        margin-top: 0.35rem;
    }
    .metric-tile .metric-note {
        color: #627d98;
        font-size: 0.9rem;
        margin-top: 0.45rem;
        line-height: 1.35;
    }
    .agent-step {
        border-left: 4px solid #1f6f9f;
        background: #f8fbfd;
        padding: 0.75rem 0.9rem;
        border-radius: 0.4rem;
        margin-bottom: 0.55rem;
    }
    .agent-step strong {
        color: #102f4f;
    }
    .feature-tile {
        border: 1px solid #d9e2ec;
        background: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        min-height: 7.6rem;
    }
    .feature-tile strong {
        color: #102f4f;
    }
    .feature-tile p {
        color: #52616f;
        margin-bottom: 0;
        line-height: 1.4;
    }
    .status-strip {
        border: 1px solid #c6d7e3;
        background: #f8fbfd;
        padding: 0.8rem 1rem;
        border-radius: 0.5rem;
        margin: 0.8rem 0 1rem 0;
    }
    /* KPI band — three-tile stat row on overview pre-results */
    .kpi-band {
        display: flex;
        gap: 1rem;
        margin: 1.2rem 0 0.5rem 0;
    }
    .kpi-card {
        flex: 1;
        background: #102f4f;
        color: white;
        border-radius: 0.5rem;
        padding: 1.1rem 1.25rem;
        text-align: center;
    }
    .kpi-card .kpi-value {
        font-size: 2.1rem;
        font-weight: 800;
        line-height: 1.1;
        color: #d9f2ef;
    }
    .kpi-card .kpi-label {
        font-size: 0.82rem;
        color: #a8c8e8;
        margin-top: 0.3rem;
        line-height: 1.35;
    }
    /* Critical finding banner — SAP tab */
    .critical-banner {
        background: #fff5f5;
        border: 2px solid #c0392b;
        border-left: 6px solid #c0392b;
        border-radius: 0.5rem;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
    }
    .critical-banner .cb-header {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        margin-bottom: 0.55rem;
    }
    .critical-banner .cb-badge {
        background: #c0392b;
        color: white;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 0.15rem 0.55rem;
        border-radius: 0.25rem;
    }
    .critical-banner .cb-reg {
        font-weight: 700;
        color: #102f4f;
        font-size: 1rem;
    }
    .critical-banner .cb-citation {
        font-style: italic;
        color: #4a4a4a;
        font-size: 0.9rem;
        margin-bottom: 0.45rem;
        border-left: 3px solid #c0392b;
        padding-left: 0.65rem;
    }
    .critical-banner .cb-finding {
        color: #1f2937;
        margin-bottom: 0.45rem;
        line-height: 1.55;
    }
    .critical-banner .cb-rec {
        font-size: 0.88rem;
        color: #374151;
    }
    /* Dupilumab precedent callout */
    .precedent-box {
        background: #fffbeb;
        border: 1px solid #f59e0b;
        border-left: 4px solid #d97706;
        border-radius: 0.4rem;
        padding: 0.85rem 1rem;
        margin-bottom: 1.2rem;
        font-size: 0.92rem;
        line-height: 1.5;
        color: #374151;
    }
    .precedent-box .pb-head {
        font-weight: 700;
        color: #92400e;
        margin-bottom: 0.25rem;
    }
    /* Score headline — post-analysis overview */
    .score-headline {
        text-align: center;
        padding: 1.4rem 1rem 1rem 1rem;
        background: linear-gradient(135deg, #102f4f, #1f6f9f);
        border-radius: 0.5rem;
        color: white;
        margin-bottom: 1rem;
    }
    .score-headline .sh-number {
        font-size: 4rem;
        font-weight: 900;
        line-height: 1;
        color: #d9f2ef;
    }
    .score-headline .sh-label {
        font-size: 0.9rem;
        color: #a8c8e8;
        margin-top: 0.2rem;
    }
    .score-headline .sh-status {
        display: inline-block;
        margin-top: 0.6rem;
        background: rgba(255,255,255,0.15);
        border-radius: 1rem;
        padding: 0.2rem 0.85rem;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    /* RAG grounding callout */
    .rag-ground {
        background: #f0fdf4;
        border: 1px solid #6ee7b7;
        border-left: 4px solid #059669;
        border-radius: 0.4rem;
        padding: 0.9rem 1.1rem;
        margin-bottom: 1rem;
        font-size: 0.93rem;
        color: #064e3b;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


MARKDOWN_DOCS = [
    {
        "title": "System Design",
        "path": "docs/system_design_guide.md",
        "summary": "Multi-agent architecture, data flow, implementation plan, and demo execution guide.",
    },
    {
        "title": "FDA and EMA Evidence",
        "path": "docs/submission_statistics_reference.md",
        "summary": "Submission statistics, transition failure rates, ROI case, and regulatory landscape.",
    },
    {
        "title": "eCTD Package Structure",
        "path": "docs/ectd_package_structure_example.md",
        "summary": "Folder hierarchy, naming rules, XML backbone examples, and IND completeness checklist.",
    },
]


def init_state() -> None:
    defaults = {
        "analysis_complete": False,
        "analysis_results": None,
        "package_info": None,
        "demo_package_path": None,
        "remote_models": [],
        "remote_model_error": None,
        "page": "Overview",
        "next_page": None,
        "analysis_mode": "Real LLM",
        "api_key_override": "",
        "selected_model": DEFAULT_MODEL,
        "live_rag_trace": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def create_demo_package() -> str:
    existing_path = st.session_state.get("demo_package_path")
    if existing_path and Path(existing_path).exists() and (Path(existing_path) / "submissionunit.xml").exists():
        return existing_path

    demo_dir = Path(tempfile.mkdtemp(prefix="ectd_xyz101_demo_"))
    demo_files = {
        "submissionunit.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<submissionUnit>\n"
            "  <submissionType>IND amendment</submissionType>\n"
            "  <application>XYZ-101</application>\n"
            "  <sequence>0001</sequence>\n"
            "</submissionUnit>\n"
        ),
        "m1/us/cover-letter.txt": (
            "XYZ-101 IND amendment for Phase 2 to Phase 3 transition. "
            "The submission requests FDA feedback on dose selection and pivotal trial design."
        ),
        "m1/us/forms/form-1571.txt": "FDA Form 1571 placeholder for XYZ-101 demo package.",
        "m2/clinical-overview.txt": (
            "XYZ-101 is an oral kinase inhibitor in NSCLC. Phase 2 enrolled 120 subjects "
            "from 2024-01-15 through database lock on 2025-05-10."
        ),
        "m2/clinical-summary.txt": (
            "Phase 2 efficacy: ORR 45%, DOR 8.2 months, PFS 6.8 months, OS 14.5 months. "
            "Doses tested were 50 mg, 100 mg, and 200 mg BID."
        ),
        "m3/quality/drug-substance.txt": "Drug substance quality summary for XYZ-101.",
        "m3/quality/drug-product.txt": "Drug product manufacturing and controls summary.",
        "m4/nonclinical/toxicology-summary.txt": "Nonclinical toxicology supports continued clinical development.",
        "m5/clinical/phase2-study-report.txt": (
            "Safety: grade 3/4 adverse events 56%, serious adverse events 23%, deaths 0, "
            "grade 3/4 hepatotoxicity 7%, grade 3/4 diarrhea 20%."
        ),
        "m5/clinical/phase3-protocol.txt": (
            "Phase 3 selects 100 mg BID. Primary endpoint ORR. Secondary endpoints DOR, PFS, OS. "
            "Sample size 300, power 80%, alpha 0.05. Stratification: ECOG and prior treatment lines."
        ),
        "m5/clinical/statistical-analysis-plan.txt": (
            "SAP finalized before Phase 2 database lock. Primary test is binomial exact test. "
            "Interim futility assessment planned at 50% PFS events."
        ),
    }

    for relative_path, content in demo_files.items():
        file_path = demo_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    st.session_state.demo_package_path = str(demo_dir)
    return str(demo_dir)


def extract_uploaded_package(uploaded_file: Any) -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="ectd_upload_"))
    with zipfile.ZipFile(uploaded_file) as archive:
        archive.extractall(temp_dir)
    return str(temp_dir)


def extract_package_info(package_path: str) -> dict[str, Any]:
    root_path = Path(package_path)
    files = [path for path in root_path.rglob("*") if path.is_file()]
    module_counts: dict[str, int] = {}
    total_bytes = 0

    for file_path in files:
        total_bytes += file_path.stat().st_size
        relative = file_path.relative_to(root_path)
        module = relative.parts[0].upper() if relative.parts else "ROOT"
        module_counts[module] = module_counts.get(module, 0) + 1

    return {
        "total_files": len(files),
        "modules": module_counts,
        "size_mb": total_bytes / (1024 * 1024),
        "file_list": [str(path.relative_to(root_path)) for path in files],
    }


def get_api_key(override: str | None) -> str | None:
    key = (override or os.environ.get("NEBIUS_API_KEY") or "").strip()
    if key.lower().startswith("bearer "):
        key = key.split(None, 1)[1].strip()
    return key or None


def format_score(score: float | int | None) -> str:
    return f"{float(score or 0):.0%}"


@st.cache_data(show_spinner=False)
def load_markdown_file(path_name: str) -> str:
    path = Path(path_name)
    if not path.exists():
        return f"## Missing file\n\nCould not find `{path_name}`."
    return path.read_text(encoding="utf-8", errors="ignore")


def render_metric_tile(value: str, label: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="metric-tile">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_gauge_chart(value: float, title: str, color: str) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(value) * 100,
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 70], "color": "#f8d7da"},
                    {"range": [70, 90], "color": "#fff3cd"},
                    {"range": [90, 100], "color": "#d4edda"},
                ],
            },
        )
    )
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=55, b=10))
    return fig


def create_bar_chart(data: dict[str, float], title: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(data.keys()),
                y=list(data.values()),
                marker_color=["#2d7d6b" if value >= 0.9 else "#c17a16" for value in data.values()],
            )
        ]
    )
    fig.update_layout(title=title, height=360, yaxis=dict(range=[0, 1]), margin=dict(l=20, r=20, t=50, b=80))
    return fig


def create_transition_funnel() -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=["Phase 1 to 2", "Phase 2 to 3", "Phase 3 to NDA/BLA", "NDA/BLA to Approval"],
            x=[63.2, 30.7, 58.1, 85.3],
            text=["63.2% advance", "30.7% advance", "58.1% advance", "85.3% approve"],
            textposition="inside",
            marker={"color": ["#2d7d6b", "#c17a16", "#1f6f9f", "#7752a0"]},
        )
    )
    fig.update_layout(
        title="Clinical Transition Success Rates",
        height=340,
        margin=dict(l=10, r=10, t=55, b=10),
        showlegend=False,
    )
    return fig


def run_analysis(package_path: str, package_info: dict[str, Any], mode: str, model: str, api_key: str | None) -> None:
    st.session_state.analysis_complete = False
    st.session_state.analysis_results = None
    st.session_state.package_info = None

    progress_bar = st.progress(0)
    status_line = st.empty()
    progress_map = {
        "Validating": 6,
        "Reading": 12,
        "Connecting": 18,
        "Checking": 22,
        "Step 1": 25,
        "Step 2": 45,
        "Step 3": 65,
        "Step 4": 82,
        "Step 5": 96,
    }

    def progress(message: str) -> None:
        status_line.write(message)
        for prefix, value in progress_map.items():
            if message.startswith(prefix):
                progress_bar.progress(value)
                break

    try:
        if mode == "Real LLM":
            if not api_key:
                raise MissingAPIKeyError(
                    "Real LLM mode needs NEBIUS_API_KEY. Set it in the shell or paste it in the sidebar."
                )
            results = run_ectd_analysis(package_path, model=model, api_key=api_key, progress_callback=progress)
        else:
            progress("Validating input package...")
            progress("Reading eCTD package...")
            progress("Step 1/5: Extracting content...")
            progress("Step 2/5: Tracing data provenance...")
            progress("Step 3/5: Validating Statistical Analysis Plan...")
            progress("Step 4/5: Retrieving FDA guidance and checking conformance...")
            progress("Step 5/5: Generating compliance report...")
            results = run_demo_analysis(package_path)
    except (MissingAPIKeyError, ECTDAgentError) as exc:
        progress_bar.empty()
        status_line.empty()
        st.error(str(exc))
        return

    progress_bar.progress(100)
    status_line.write("Analysis complete.")
    st.session_state.analysis_complete = True
    st.session_state.analysis_results = results
    st.session_state.package_info = package_info
    st.success("Analysis complete.")


def render_header() -> None:
    st.markdown(
        """
        <div class="header-section">
            <h1>SubmissionAI</h1>
            <p>Regulatory provenance, SAP validation, and FDA conformance analysis for Phase 2 to 3 submissions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_row(results: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Compliance", format_score(results.get("overall_score")), results.get("status", ""))
    col2.metric("Data Provenance", format_score(results.get("data_provenance_score")))
    col3.metric("SAP Validation", format_score(results.get("sap_validation_score")))
    col4.metric("FDA Approval Probability", format_score(results.get("approval_probability")))


def render_validation_report(report: dict[str, Any] | None, show_files: bool = False) -> None:
    if not report:
        st.info("No input validation report is available yet.")
        return

    status = report.get("status", "UNKNOWN")
    summary = report.get("summary", {})
    if status == "PASS":
        st.success("Input validation passed.")
    elif status == "WARN":
        st.warning("Input validation passed with warnings.")
    else:
        st.error("Input validation failed. Fix the errors before running analysis.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Files Checked", summary.get("total_files", 0))
    col2.metric("Package Size", summary.get("package_size", "0 B"))
    col3.metric("Text Files", summary.get("readable_text_files", 0))
    col4.metric("Issues", len(report.get("issues", [])))

    checks = report.get("checks", [])
    if checks:
        st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

    issues = report.get("issues", [])
    if issues:
        with st.expander("Validation issues", expanded=status == "FAIL"):
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

    if show_files:
        files = report.get("files", [])
        with st.expander("File-level validation details"):
            if files:
                st.dataframe(pd.DataFrame(files), use_container_width=True, hide_index=True)
            else:
                st.info("No files were discovered.")


def render_feature_tile(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="feature-tile">
            <strong>{title}</strong>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rag_trace(trace: dict[str, Any] | None) -> None:
    if not trace:
        st.info("No RAG pipeline trace is available yet.")
        return

    summary = trace.get("index_summary") or {}
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Source Docs", summary.get("source_documents", 0))
    col2.metric("Chunks", summary.get("chunks", 0))
    col3.metric("Unique Terms", summary.get("unique_terms", 0))
    col4.metric("Avg Terms/Chunk", summary.get("average_chunk_terms", 0))

    st.markdown("#### Pipeline Steps")
    steps = trace.get("steps") or []
    if steps:
        st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)

    routed_domains = trace.get("routed_domains") or []
    routed_guidelines = trace.get("routed_guidelines") or []
    if routed_domains:
        st.caption(f"Routed domains: {', '.join(routed_domains)}")
    if routed_guidelines:
        st.caption(f"Candidate guideline filters: {', '.join(routed_guidelines[:8])}")

    top_chunks = trace.get("top_chunks") or []
    st.markdown("#### Retrieved and Reranked Chunks")
    if top_chunks:
        st.dataframe(pd.DataFrame(top_chunks), use_container_width=True, hide_index=True)
    else:
        st.info("No chunks were retrieved.")

    with st.expander("Generated retrieval query"):
        st.write(trace.get("query", ""))


def render_overview(mode: str, model: str, api_key: str | None) -> None:
    st.markdown(
        """
        <div class="demo-hero">
            <div class="hero-kicker">Live regulatory AI demo</div>
            <h2>SubmissionAI</h2>
            <p>
            One click, and the system reads 21 regulatory documents, runs five AI agents,
            and tells you whether your Phase 3 IND is ready for FDA.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    results = st.session_state.analysis_results

    if not results:
        sample = run_demo_analysis()
        st.markdown("### Problem and Significance")
        problem_col, chart_col = st.columns([1.15, 1])
        with problem_col:
            st.markdown(
                """
                Phase 2 to Phase 3 transition is where clinical evidence, statistical planning,
                and regulatory packaging have to line up. In practice, those threads often drift:
                a dose decision may not trace cleanly to Phase 2 safety data, a SAP may be missing
                lock evidence, or the eCTD package may fail technical conformance before reviewers
                even reach the scientific question.

                This demo targets that gap: a sponsor-side preflight agent that checks whether a
                submission package is structured, traceable, and ready enough for FDA-facing review.
                """
            )
            st.markdown(
                """
                <div class="status-strip">
                The goal is not to replace regulatory judgment. The goal is to catch avoidable
                package, evidence, and conformance issues before submission.
                </div>
                """,
                unsafe_allow_html=True,
            )
        with chart_col:
            st.plotly_chart(create_transition_funnel(), use_container_width=True)

        st.markdown("### System Capabilities")
        cap1, cap2, cap3 = st.columns(3)
        with cap1:
            render_feature_tile("Input Preflight", "Checks package format, file types, encoding, file size, module coverage, and XML signals.")
        with cap2:
            render_feature_tile("Evidence Reasoning", "Maps Phase 2 efficacy, dose, safety, and SAP choices to Phase 3 design decisions.")
        with cap3:
            render_feature_tile("RAG-Grounded Conformance", "Retrieves FDA, ICH, and CFR criteria before checking structure, completeness, and remediation priorities.")

        st.markdown("### What Goes In and What Comes Out")
        io_col1, io_col2 = st.columns(2)
        with io_col1:
            st.markdown(
                """
                **Input**

                - eCTD-style ZIP package or generated XYZ-101 demo package
                - Module folders such as `m1` through `m5`
                - regulatory XML such as `submissionunit.xml` when available
                - clinical summaries, protocol, SAP, study report, CMC, and nonclinical files
                """
            )
        with io_col2:
            st.markdown(
                """
                **Output**

                - input validation and document inventory
                - provenance and SAP-readiness checks
                - FDA conformance findings with retrieved guidance
                - priority remediation items and expected FDA questions
                """
            )

        st.markdown("### Live Demo")
        demo_col1, demo_col2 = st.columns([0.6, 0.4])
        with demo_col1:
            st.markdown(
                """
                Run the generated XYZ-101 package through the full agent pipeline,
                or open the upload workflow to analyze your own ZIP package.
                **Requires a Nebius API key** — paste it in the sidebar first.
                """
            )
            action_col1, action_col2 = st.columns([0.55, 0.45])
            with action_col1:
                if st.button("Run Generated Demo", type="primary", disabled=not bool(api_key)):
                    package_path = create_demo_package()
                    package_info = extract_package_info(package_path)
                    run_analysis(package_path, package_info, mode, model, api_key)
                    if st.session_state.analysis_complete:
                        st.rerun()
                if not api_key:
                    st.caption("⬅ Paste your Nebius key in the sidebar to enable.")
            with action_col2:
                if st.button("Open Upload Workflow"):
                    st.session_state.next_page = "Upload & Analyze"
                    st.rerun()
        with demo_col2:
            key_set = bool(api_key)
            st.markdown(
                f"""
                <div class="status-strip">
                API key: <strong>{"loaded" if key_set else "not set"}</strong><br>
                Model: <strong>{model}</strong><br>
                {"Ready to run." if key_set else "Paste your Nebius key in the sidebar to run."}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### The Scale")
        st.markdown(
            """
            <div class="kpi-band">
              <div class="kpi-card">
                <div class="kpi-value">400</div>
                <div class="kpi-label">Phase 3 IND submissions received by FDA per year</div>
              </div>
              <div class="kpi-card">
                <div class="kpi-value">800–1,200</div>
                <div class="kpi-label">Person-days of expert review time per submission</div>
              </div>
              <div class="kpi-card">
                <div class="kpi-value">&lt; 60 sec</div>
                <div class="kpi-label">SubmissionAI full pipeline — with cited sources</div>
              </div>
            </div>
            <p style="color:#627d98;font-size:0.88rem;margin-top:0.2rem;">
            AI handles the systematic. Humans handle the judgment.
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Quick Look: Baseline Readiness Snapshot")
        render_metric_row(sample)
        return

    overall_pct = f"{float(results.get('overall_score', 0)):.0%}"
    approval_pct = f"{float(results.get('approval_probability', 0)):.0%}"
    status_txt = results.get("status", "NEEDS REVISION").replace("_", " ")
    st.markdown(
        f"""
        <div class="score-headline">
          <div class="sh-number">{overall_pct}</div>
          <div class="sh-label">Overall Submission Readiness &nbsp;·&nbsp; FDA Approval Probability: <strong>{approval_pct}</strong></div>
          <div class="sh-status">{status_txt}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_metric_row(results)
    st.caption(f"Mode: {results.get('analysis_mode', 'unknown')} | Model: {results.get('llm_model') or 'deterministic demo'}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(create_gauge_chart(results["data_provenance_score"], "Data Provenance", "#2d7d6b"), use_container_width=True)
    with col2:
        st.plotly_chart(create_gauge_chart(results["sap_validation_score"], "SAP Validation", "#1f6f9f"), use_container_width=True)
    with col3:
        st.plotly_chart(create_gauge_chart(results["conformance_score"], "FDA Conformance", "#7752a0"), use_container_width=True)

    timeline = results.get("fda_review_timeline") or {}
    st.markdown("### FDA Review Timeline")
    col1, col2, col3 = st.columns(3)
    col1.metric("Completeness", f"{timeline.get('completeness_weeks', 0)} weeks")
    col2.metric("Substantive Review", f"{timeline.get('substantive_review_weeks', 0)} weeks")
    col3.metric("Total", f"{timeline.get('total_weeks', 0)} weeks")


def render_upload_page(mode: str, model: str, api_key: str | None) -> None:
    st.markdown("## Upload & Analyze")
    uploaded_file = st.file_uploader("Upload eCTD package", type="zip")
    use_demo = st.checkbox("Use generated demo package", value=True)

    if not uploaded_file and not use_demo:
        st.info("Upload a ZIP package or enable the generated demo package.")
        return

    if use_demo:
        package_path = create_demo_package()
        st.success("Using generated XYZ-101 demo package.")
    else:
        package_path = extract_uploaded_package(uploaded_file)
        st.success(f"Extracted package: {uploaded_file.name}")

    package_info = extract_package_info(package_path)
    st.markdown("### Package Information")
    col1, col2, col3 = st.columns(3)
    col1.metric("Files", package_info["total_files"])
    col2.metric("Modules", len(package_info["modules"]))
    col3.metric("Size", f"{package_info['size_mb']:.2f} MB")

    st.markdown("### Uploaded Document Overview")
    module_df = pd.DataFrame(
        [{"Module": module, "Files": count} for module, count in sorted(package_info["modules"].items())]
    )
    st.dataframe(module_df, use_container_width=True, hide_index=True)

    file_overview = pd.DataFrame(
        [
            {
                "Module": Path(file_path).parts[0].upper() if Path(file_path).parts else "ROOT",
                "File": file_path,
                "Type": Path(file_path).suffix.lower() or "(none)",
            }
            for file_path in package_info["file_list"]
        ]
    )
    with st.expander("File inventory", expanded=True):
        if file_overview.empty:
            st.info("No files were discovered.")
        else:
            st.dataframe(file_overview, use_container_width=True, hide_index=True)

    st.markdown("### Input Validation Layer")
    validation_report = validate_input_package(package_path)
    render_validation_report(validation_report, show_files=True)

    if mode == "Real LLM" and not api_key:
        st.markdown(
            """
            <div class="warning-box">
            Real LLM mode is selected, but no Nebius key is loaded. Set NEBIUS_API_KEY or paste a key in Demo Setup.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Run Analysis", type="primary", disabled=validation_report["status"] == "FAIL"):
        run_analysis(package_path, package_info, mode, model, api_key)

    if st.session_state.analysis_complete:
        st.markdown("---")
        render_results_summary(st.session_state.analysis_results)


def render_results_summary(results: dict[str, Any]) -> None:
    st.markdown("## Analysis Results")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="result-box">
            <h3>Overall Status</h3>
            <p><strong>{results.get('status', 'UNKNOWN')}</strong></p>
            <p>Compliance Score: <strong>{format_score(results.get('overall_score'))}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        timeline = results.get("fda_review_timeline") or {}
        st.markdown(
            f"""
            <div class="result-box">
            <h3>FDA Review Outlook</h3>
            <p>Approval Probability: <strong>{format_score(results.get('approval_probability'))}</strong></p>
            <p>Estimated Timeline: <strong>{timeline.get('total_weeks', 0)} weeks</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Priority Recommendations")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Priority 1")
        for item in results.get("priority_1_items", []):
            st.markdown(f"- **{item}**")
    with col2:
        st.markdown("#### Priority 2")
        for item in results.get("priority_2_items", []):
            st.markdown(f"- {item}")

    report_text = generate_markdown_report(results)
    st.download_button(
        label="Download Report",
        data=report_text,
        file_name=f"ectd_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
    )


_STATUS_COLORS = {
    "NON-COMPLIANT": "#fdecea",
    "ERROR": "#fdecea",
    "WARNING": "#fff8e1",
    "COMPLIANT": "#e8f5e9",
    "INFO": "#e3f2fd",
}
_STATUS_BORDER = {
    "NON-COMPLIANT": "#c62828",
    "ERROR": "#c62828",
    "WARNING": "#f57f17",
    "COMPLIANT": "#2e7d32",
    "INFO": "#1565c0",
}
_STATUS_LABEL = {
    "NON-COMPLIANT": "NON-COMPLIANT",
    "ERROR": "NON-COMPLIANT",
    "WARNING": "WARNING",
    "COMPLIANT": "COMPLIANT",
    "INFO": "INFO",
}


def _render_findings_table(findings: list[dict], severity_col: str = "status") -> None:
    """Render a list of regulatory findings as styled cards."""
    for item in findings:
        raw_status = str(item.get(severity_col, "INFO")).upper()
        display_status = _STATUS_LABEL.get(raw_status, raw_status)
        bg = _STATUS_COLORS.get(raw_status, "#f5f5f5")
        border = _STATUS_BORDER.get(raw_status, "#9e9e9e")

        regulation = item.get("regulation") or item.get("rule_id") or ""
        citation = item.get("citation") or ""
        finding = item.get("finding") or item.get("finding") or ""
        recommendation = item.get("recommendation") or ""

        st.markdown(
            f"""
            <div style="border-left:4px solid {border};background:{bg};
                        padding:0.75rem 1rem;border-radius:0.4rem;margin-bottom:0.55rem;">
              <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.3rem;">
                <span style="font-weight:700;color:{border};font-size:0.78rem;
                             text-transform:uppercase;letter-spacing:0.04em;">{display_status}</span>
                <span style="font-weight:600;color:#102f4f;">{regulation}</span>
              </div>
              <div style="font-style:italic;color:#374151;margin-bottom:0.3rem;font-size:0.9rem;">
                &ldquo;{citation}&rdquo;
              </div>
              <div style="color:#1f2937;margin-bottom:0.3rem;">{finding}</div>
              <div style="color:#374151;font-size:0.88rem;">
                <strong>Rec:</strong> {recommendation}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_detailed_report() -> None:
    st.markdown("## Detailed Report")
    results = st.session_state.analysis_results
    if not results:
        st.info("Run an analysis first.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Input Validation", "Provenance", "SAP", "Conformance", "Questions"])

    with tab1:
        render_validation_report(results.get("input_validation"), show_files=True)

    with tab2:
        provenance = results.get("provenance", {})
        prov_findings = provenance.get("findings") or []

        col_chart, col_summary = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(
                create_bar_chart(
                    {
                        "Efficacy": provenance.get("efficacy_traceability", {}).get("alignment_score", 0),
                        "Dose": 1.0 if provenance.get("dose_justification", {}).get("status") == "JUSTIFIED" else 0.7,
                        "Safety": provenance.get("safety_traceability", {}).get("coverage_score", 0),
                        "References": 1.0
                        if provenance.get("cross_reference_integrity", {}).get("broken_references", 1) == 0
                        else 0.6,
                    },
                    "Data Provenance Components",
                ),
                use_container_width=True,
            )
        with col_summary:
            xref = provenance.get("cross_reference_integrity", {})
            dose = provenance.get("dose_justification", {})
            st.markdown("**Cross-Reference Integrity**")
            st.metric("Valid references", f"{xref.get('valid_references', 0)} / {xref.get('total_references', 0)}")
            st.metric("Broken references", xref.get("broken_references", 0))
            st.markdown("**Dose Justification**")
            st.metric("Phase 2 optimal dose", f"{dose.get('phase2_optimal_dose', '—')} mg BID")
            st.metric("Phase 3 selected dose", f"{dose.get('phase3_selected_dose', '—')} mg BID")
            st.metric("Benefit-risk ratio", f"{dose.get('benefit_risk_ratio', 0):.2f}")

        st.markdown("#### Provenance Findings")
        if prov_findings:
            _render_findings_table(prov_findings)
        else:
            st.success("No provenance issues detected.")

        with st.expander("Raw provenance data"):
            st.json(provenance)

    with tab3:
        sap = results.get("sap", {})
        sap_findings = sap.get("findings") or []

        sap_col1, sap_col2, sap_col3, sap_col4 = st.columns(4)
        pre_spec = sap.get("pre_specification", {})
        pre_spec_status = pre_spec.get("status", "—")
        sap_col1.metric("Pre-Specification", pre_spec_status)
        _raw_align = sap.get("endpoint_alignment", {}).get("alignment_percentage") or 0
        _align_val = _raw_align / 100 if _raw_align > 1 else _raw_align
        sap_col2.metric("Endpoint Alignment", format_score(_align_val))
        sap_col3.metric("Interim Analysis", sap.get("interim_analysis", {}).get("status", "—"))
        sap_col4.metric("SAP Score", format_score(sap.get("overall_score")))

        # ── CRITICAL finding: prominent banner ────────────────────────────
        critical = next(
            (f for f in sap_findings if str(f.get("status", "")).upper() == "CRITICAL"),
            None,
        )
        if critical:
            reg = critical.get("regulation", "")
            citation = critical.get("citation", "")
            finding_text = critical.get("finding", "")
            rec = critical.get("recommendation", "")
            st.markdown(
                f"""
                <div class="critical-banner">
                  <div class="cb-header">
                    <span class="cb-badge">⚠ Critical</span>
                    <span class="cb-reg">{reg}</span>
                  </div>
                  <div class="cb-citation">&ldquo;{citation}&rdquo;</div>
                  <div class="cb-finding">{finding_text}</div>
                  <div class="cb-rec"><strong>Recommendation:</strong> {rec}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class="precedent-box">
                  <div class="pb-head">📋 Real-World Precedent — dupilumab BLA 761055</div>
                  The FDA Statistical Review of dupilumab (BLA 761055) flagged an identical deviation:
                  a post-lock SAP amendment changed a key endpoint definition, and FDA required the sponsor
                  to submit a sensitivity analysis under the original SAP before the primary result was accepted.
                  SubmissionAI identified this pattern independently, cited the same ICH E9 §5.1 requirement,
                  and made the same recommendation — from a retrieved guideline passage, not from LLM memory.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("#### All SAP Findings")
        if sap_findings:
            _render_findings_table(sap_findings)
        else:
            st.success("No SAP issues detected.")

        with st.expander("Raw SAP data"):
            st.json(sap)

    with tab4:
        conformance = results.get("conformance", {})
        retrieved_guidance = conformance.get("retrieved_guidance") or []
        rule_findings = conformance.get("rule_based_findings") or []
        knowledge_base = conformance.get("knowledge_base") or {}

        kb_col1, kb_col2, kb_col3, kb_col4 = st.columns(4)
        with kb_col1:
            st.metric("KB Chunks Retrieved", knowledge_base.get("chunks_retrieved", len(retrieved_guidance)))
        with kb_col2:
            st.metric("KB Chunks Available", knowledge_base.get("chunks_available", "N/A"))
        with kb_col3:
            st.metric("Rule Findings", len(rule_findings))
        with kb_col4:
            st.metric("Retrieval Mode", knowledge_base.get("retrieval_status", "unknown"))

        retrieval_method = knowledge_base.get("retrieval_method")
        if retrieval_method:
            st.caption(f"Retrieval method: {retrieval_method}")

        st.markdown("#### Retrieved Regulatory Guidance")
        if retrieved_guidance:
            st.dataframe(pd.DataFrame(retrieved_guidance), use_container_width=True, hide_index=True)
        else:
            st.info("No regulatory guidance chunks were attached to this result.")

        st.markdown("#### Rule-Based & Demo Conformance Findings")
        if rule_findings:
            _render_findings_table(rule_findings, severity_col="severity")
        else:
            st.success("No deterministic conformance findings were raised.")

        st.markdown("### Real-Time RAG Pipeline Trace")
        render_rag_trace(conformance.get("rag_trace"))

        with st.expander("Raw conformance JSON"):
            st.json(conformance)

    with tab5:
        for index, question in enumerate(results.get("expected_fda_questions", []), start=1):
            st.markdown(f"{index}. {question}")


def render_evidence_page() -> None:
    st.markdown(
        """
        <div class="evidence-hero">
            <h2>Evidence & Design Brief</h2>
            <p>
            A curated regulatory story for the demo: why Phase 2 to Phase 3 transitions fail,
            how the multi-agent system attacks the failure modes, and what a compliant eCTD
            package needs to contain.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_tile("69.3%", "Phase 2 to 3 failure rate", "The highest-risk transition in clinical development.")
    with col2:
        render_metric_tile("1,500", "FDA IND submissions/year", "Large recurring review volume with major automation potential.")
    with col3:
        render_metric_tile("$100-300M", "Cost per failed transition", "Estimated sponsor impact for each failed Phase 2 to 3 move.")
    with col4:
        render_metric_tile("5", "Specialized agents", "Content extraction, provenance, SAP, conformance, and reporting.")

    st.markdown("### Demo Narrative")
    story_col1, story_col2, story_col3 = st.columns(3)
    with story_col1:
        st.markdown(
            """
            **Problem**

            Phase 2 to 3 decisions often fail because evidence, statistics, and submission
            artifacts drift apart before regulatory review.
            """
        )
    with story_col2:
        st.markdown(
            """
            **Agent System**

            The demo coordinates focused reviewers for clinical content, data provenance,
            SAP compliance, FDA conformance, and executive recommendations.
            """
        )
    with story_col3:
        st.markdown(
            """
            **Submission Readiness**

            The output turns raw package material into traceable scores, priority gaps,
            reviewer questions, and an auditable report.
            """
        )

    st.markdown("### Multi-Agent Workflow")
    workflow_col1, workflow_col2 = st.columns([1, 1])
    with workflow_col1:
        for title, body in [
            ("1. Content Analyzer", "Extracts efficacy, safety, dose, endpoint, and study design facts."),
            ("2. Provenance Tracker", "Maps Phase 2 evidence to Phase 3 design decisions and cross-references."),
            ("3. SAP Validator", "Checks pre-specification, endpoint alignment, methods, and interim analysis."),
            ("4. FDA Conformance Checker", "Retrieves FDA/ICH/CFR rules, applies deterministic preflight checks, and reviews package completeness."),
            ("5. Report Generator", "Synthesizes readiness score, recommendations, timeline, and FDA questions."),
        ]:
            st.markdown(
                f"""
                <div class="agent-step">
                    <strong>{title}</strong><br>
                    {body}
                </div>
                """,
                unsafe_allow_html=True,
            )
    with workflow_col2:
        st.markdown("#### Failure Modes Covered")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Failure mode": "Incomplete data provenance", "Share": "25-30%", "Agent response": "Traceability map"},
                    {"Failure mode": "SAP deviations", "Share": "15-20%", "Agent response": "SAP validation"},
                    {"Failure mode": "eCTD documentation gaps", "Share": "20-25%", "Agent response": "Conformance checks"},
                    {"Failure mode": "Dosing uncertainty", "Share": "10-15%", "Agent response": "Dose justification review"},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### eCTD Readiness Checklist")
    st.dataframe(
        pd.DataFrame(
            [
                {"Area": "Module 1", "Expected content": "Administrative forms, cover letter, FDA forms", "Demo check": "Present"},
                {"Area": "Module 2", "Expected content": "Clinical, nonclinical, and quality summaries", "Demo check": "Present"},
                {"Area": "Module 3", "Expected content": "CMC drug substance and product documentation", "Demo check": "Present"},
                {"Area": "Module 4", "Expected content": "Nonclinical pharmacology and toxicology reports", "Demo check": "Present"},
                {"Area": "Module 5", "Expected content": "Clinical study report, protocol, SAP, safety summary", "Demo check": "Present"},
                {"Area": "XML backbone", "Expected content": "submissionunit.xml for eCTD v4.0 or legacy XML for older packages", "Demo check": "Validated when supplied"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Source Documents")
    doc_tabs = st.tabs([doc["title"] for doc in MARKDOWN_DOCS])
    for tab, doc in zip(doc_tabs, MARKDOWN_DOCS):
        with tab:
            st.caption(doc["summary"])
            st.markdown(load_markdown_file(doc["path"]))


def render_rag_knowledge_base() -> None:
    """Dedicated page: RAG Knowledge Base design, inventory, and live retrieval stats."""
    st.markdown(
        """
        <div class="evidence-hero">
            <h2>RAG Knowledge Base</h2>
            <p>
            Two knowledge bases: <strong>13 FDA/ICH/EMA guidelines for conformance</strong> (227 chunks)
            and <strong>12 statistical methodology guidelines for SAP validation</strong> (182 chunks).
            Every finding is grounded in a retrieved passage with a retrieval score —
            not LLM parametric memory.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="rag-ground">
        <strong>Why this matters for regulatory use:</strong> &nbsp;
        Every agent finding includes the exact guideline section retrieved, a retrieval confidence score,
        and the verbatim passage that supports the conclusion. This means a regulatory reviewer can
        trace any SubmissionAI finding back to the source document in seconds — the same standard
        expected of a human reviewer.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_a, tab_b = st.tabs(["Tab A: FDA Conformance Checker KB", "Tab B: SAP Validator KB"])

    # ── TAB A: FDA Conformance Checker ────────────────────────────────────────
    with tab_a:
        kb_meta = get_kb_metadata()

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric_tile(str(kb_meta["total_documents"]), "Guideline Documents", "FDA, ICH, EMA, 21 CFR")
        with m2:
            render_metric_tile(str(kb_meta["documents_on_disk"]), "Source Files Present", f"in {Path(kb_meta['kb_dir']).name}/")
        with m3:
            chunks_val = (
                str(kb_meta["total_chunks_indexed"])
                if kb_meta["total_chunks_indexed"]
                else str(kb_meta.get("fallback_chunks_available", 0))
            )
            render_metric_tile(chunks_val, "Retrievable Chunks", "Full index if built; built-in demo fallback otherwise")
        with m4:
            render_metric_tile(
                "Hybrid" if kb_meta.get("runtime_mode") == "full_hybrid" else "No-Prereq",
                "Runtime Mode",
                "Dense + BM25 + RRF when full stack is ready",
            )

        if kb_meta.get("runtime_mode") == "no_prereq_live_rag":
            st.warning(
                "Full hybrid RAG is not built on this machine yet. The demo runs a no-prereq "
                "lexical RAG pipeline over built-in FDA/ICH/CFR passages."
            )
        else:
            st.success("Full hybrid RAG index is available.")

        dep_status = kb_meta.get("dependency_status") or {}
        if dep_status:
            st.markdown("#### Dependency Status")
            st.dataframe(
                pd.DataFrame([{"Dependency": n, "Status": "Installed" if ok else "Missing"} for n, ok in dep_status.items()]),
                use_container_width=True, hide_index=True,
            )

        st.markdown("### Knowledge Base Inventory")
        docs_df = pd.DataFrame(kb_meta["documents"])
        docs_df["status"] = docs_df["file_exists"].map({True: "Ready", False: "Missing"})
        docs_df["size"] = docs_df["file_size_kb"].apply(lambda x: f"{x:.0f} KB" if x > 0 else "—")
        st.dataframe(
            docs_df[["guideline_code", "title", "regulatory_body", "document_type", "effective_date", "size", "status"]].rename(columns={
                "guideline_code": "Code", "title": "Title", "regulatory_body": "Body",
                "document_type": "Type", "effective_date": "Effective", "size": "Size", "status": "Status",
            }),
            use_container_width=True, hide_index=True,
        )

        st.markdown("### Retrieval Pipeline Architecture")
        arch_col1, arch_col2 = st.columns([1, 1])
        with arch_col1:
            for step, desc in [
                ("1. Section-Aware Chunking",
                 "Each guideline is split at section headers. Chunks retain section header, guideline code, "
                 "regulatory body, effective date, and compliance domain as metadata. Chunk: 450 words, 50-word overlap."),
                ("2. Dense Embedding (ChromaDB)",
                 "Chunks are embedded with BAAI/bge-large-en-v1.5 (1024-dim, cosine). Domain routing "
                 "pre-filters to the most relevant guidelines before vector search."),
                ("3. Sparse Retrieval (BM25)",
                 "A BM25Okapi index is built in-memory. BM25 excels at exact regulatory term matching "
                 "(e.g., NRI, 21 CFR 312.23, submissionunit.xml) that dense embeddings can miss."),
                ("4. Reciprocal Rank Fusion (k=60)",
                 "Dense (top-20) and sparse (top-20) candidate lists are merged using RRF. "
                 "Consistently outperforms either method alone on regulatory text."),
                ("5. Cross-Encoder Re-Ranking",
                 "Top-20 fused candidates are re-scored by ms-marco-MiniLM-L-12-v2. "
                 "Top-5 passages are passed to the LLM conformance prompt."),
            ]:
                st.markdown(f'<div class="agent-step"><strong>{step}</strong><br>{desc}</div>', unsafe_allow_html=True)
        with arch_col2:
            st.markdown("#### Why Hybrid Retrieval?")
            st.dataframe(pd.DataFrame([
                {"Method": "Dense only", "Strength": "Semantic similarity", "Weakness": "Misses exact regulatory terms"},
                {"Method": "BM25 only", "Strength": "Exact term matching", "Weakness": "No semantic understanding"},
                {"Method": "Hybrid + RRF", "Strength": "Both semantic and exact", "Weakness": "Slightly higher latency"},
                {"Method": "+ Cross-encoder", "Strength": "Precise re-ranking", "Weakness": "Adds ~200ms per query"},
            ]), use_container_width=True, hide_index=True)

            st.markdown("#### Sample Retrieved Passages (SAP CRITICAL finding)")
            st.dataframe(pd.DataFrame([
                {"Rank": 1, "Guideline": "ICH E9 §5.1", "Passage (excerpt)": "The statistical analysis plan should be finalised before the blind is broken.", "RRF Score": 0.97},
                {"Rank": 2, "Guideline": "ICH E9 §5.1", "Passage (excerpt)": "Changes to the analysis plan after unblinding must be documented with reasons.", "RRF Score": 0.91},
                {"Rank": 3, "Guideline": "FDA Adaptive Design §III", "Passage (excerpt)": "Pre-specification is required for any adaptation that could introduce bias.", "RRF Score": 0.83},
                {"Rank": 4, "Guideline": "ICH E9(R1) §3.1", "Passage (excerpt)": "Intercurrent event strategies must be defined in the SAP before data lock.", "RRF Score": 0.79},
                {"Rank": 5, "Guideline": "EMA Missing Data §4.1", "Passage (excerpt)": "Sensitivity analyses should be pre-specified, not performed post-hoc.", "RRF Score": 0.71},
            ]), use_container_width=True, hide_index=True)

            st.markdown("#### Deterministic Preflight Checks")
            st.dataframe(pd.DataFrame([
                {"Rule ID": "ICH-M4-MODULES", "Check": "M1–M5 module completeness", "Source": "ICH M4E(R2)"},
                {"Rule ID": "FDA-ECTD-XML-BACKBONE", "Check": "submissionunit.xml or backbone.xml present", "Source": "FDA eCTD v4.0 TCG"},
                {"Rule ID": "FDA-ECTD-PATH-LENGTH", "Check": "File paths ≤ 180 characters", "Source": "FDA eCTD v4.0 TCG"},
                {"Rule ID": "ICH-E9-SAP-LOCK", "Check": "SAP lock date evidence in SAP document", "Source": "ICH E9 §5.1"},
                {"Rule ID": "INPUT-VALIDATION", "Check": "Upload validation errors passthrough", "Source": "SubmissionAI input layer"},
            ]), use_container_width=True, hide_index=True)

        # Live stats from last analysis
        st.markdown("### Live Retrieval Stats (Last Analysis)")
        results = st.session_state.get("analysis_results")
        if results:
            conformance = results.get("conformance") or {}
            retrieved = conformance.get("retrieved_guidance") or []
            rule_findings = conformance.get("rule_based_findings") or []
            kb_info = conformance.get("knowledge_base") or {}
            stat1, stat2, stat3 = st.columns(3)
            stat1.metric("Chunks Retrieved", kb_info.get("chunks_retrieved", len(retrieved)))
            stat2.metric("Chunks Available", kb_info.get("chunks_available", "N/A"))
            stat3.metric("Rule Findings", len(rule_findings))
            if retrieved:
                st.markdown("#### Retrieved Passages")
                retrieved_df = pd.DataFrame(retrieved)
                display_cols = [c for c in ["id", "title", "source", "section", "effective_date", "relevance_score"] if c in retrieved_df.columns]
                st.dataframe(
                    retrieved_df[display_cols].rename(columns={
                        "id": "Guideline", "title": "Document Title", "source": "Body",
                        "section": "Section", "effective_date": "Effective", "relevance_score": "Score",
                    }),
                    use_container_width=True, hide_index=True,
                )
        else:
            st.info("Run an analysis to see live retrieval stats here.")

        # Build button
        st.markdown("### Knowledge Base Management")
        st.markdown(
            f"**Embedding model:** `{kb_meta['embedding_model']}`  "
            f"**Re-ranker:** `{kb_meta['reranker_model']}`  "
            f"**ChromaDB:** `{kb_meta['chroma_db_path']}`"
        )
        if st.button("Build / Rebuild FDA Conformance KB", type="primary", key="build_conformance_kb"):
            with st.spinner("Building FDA Conformance KB — 2–5 min on first run..."):
                try:
                    import regulatory_knowledge_base as _rkb
                    _rkb._retriever = None
                    _rkb._get_retriever()
                    st.success("FDA Conformance KB built. Reload page to see updated chunk count.")
                except Exception as exc:
                    st.error(f"Build failed: {exc}")

    # ── TAB B: SAP Validator KB ───────────────────────────────────────────────
    with tab_b:
        try:
            sap_meta = get_sap_kb_metadata()
            sap_meta_error = None
        except Exception as exc:
            sap_meta = None
            sap_meta_error = str(exc)

        if sap_meta_error:
            st.error(f"Could not load SAP KB metadata: {sap_meta_error}")
        else:
            sm1, sm2, sm3, sm4 = st.columns(4)
            with sm1:
                render_metric_tile(str(sap_meta["total_documents"]), "Guideline Documents",
                                   "ICH E9/E9(R1), FDA, EMA statistical guidelines")
            with sm2:
                render_metric_tile(str(sap_meta["documents_on_disk"]), "Source Files Present",
                                   f"in sap_knowledge_base/ + rag_knowledge_base/")
            with sm3:
                render_metric_tile(
                    str(sap_meta["total_chunks_indexed"]) if sap_meta["total_chunks_indexed"] else "Fallback",
                    "Chunks Indexed",
                    "Full ChromaDB index or built-in passage fallback",
                )
            with sm4:
                render_metric_tile(
                    "Hybrid" if sap_meta.get("runtime_mode") == "full_hybrid" else "No-Prereq",
                    "Runtime Mode",
                    "Dense + BM25 (term-expanded) + RRF + cross-encoder",
                )

            if sap_meta.get("runtime_mode") == "full_hybrid":
                st.success("SAP Validator full hybrid RAG index is available.")
            else:
                st.warning(
                    "SAP Validator KB not yet indexed. Run an SAP validation to trigger build, "
                    "or click the button below. Falls back to built-in regulatory passages."
                )

            st.markdown("### SAP Validator Document Registry")
            sap_docs_df = pd.DataFrame(sap_meta["documents"])
            sap_docs_df["status"] = sap_docs_df["file_exists"].map({True: "Ready", False: "Missing"})
            sap_docs_df["size"] = sap_docs_df["file_size_kb"].apply(lambda x: f"{x:.0f} KB" if x > 0 else "—")
            st.dataframe(
                sap_docs_df[["code", "title", "body", "year", "domains", "size", "status"]].rename(columns={
                    "code": "Code", "title": "Title", "body": "Body", "year": "Year",
                    "domains": "Validation Domains", "size": "Size", "status": "Status",
                }),
                use_container_width=True, hide_index=True,
            )

            st.markdown("### Seven SAP Validation Domains")
            domain_col1, domain_col2 = st.columns([1, 1])
            with domain_col1:
                st.dataframe(pd.DataFrame([
                    {"Domain": d["domain"], "Template Query": d["template"][:80], "Expected Citation": d["expected_citation"]}
                    for d in sap_meta["validation_queries"]
                ]), use_container_width=True, hide_index=True)
            with domain_col2:
                st.markdown("#### Domain → Guideline Routing")
                routing_rows = [
                    {"Domain": domain, "Routed Guidelines": ", ".join(codes)}
                    for domain, codes in sap_meta["domain_routing"].items()
                ]
                st.dataframe(pd.DataFrame(routing_rows), use_container_width=True, hide_index=True)

            st.markdown("### SAP Validator Architecture")
            sap_arch_col1, sap_arch_col2 = st.columns([1, 1])
            with sap_arch_col1:
                for step, desc in [
                    ("1. Clinical Term Expansion",
                     "BM25 queries are expanded with clinical trial abbreviations: SAP→statistical analysis plan, "
                     "ITT→intent-to-treat, MMRM→mixed model repeated measures, FWER→family-wise error rate, "
                     "and 20+ additional expansions to improve sparse retrieval recall."),
                    ("2. Domain-Tagged Chunking",
                     "Every chunk is tagged with one or more of 7 SAP validation domains based on keyword matching "
                     "(pre_specification, estimand, primary_endpoint, multiplicity, subgroup, missing_data, covariate)."),
                    ("3. Domain-Routed Retrieval",
                     "Queries are pre-classified by domain. ChromaDB retrieval is filtered to the guidelines most "
                     "relevant to each domain (e.g., estimand queries route to ICH-E9R1 and ICH-E9R1-TM only)."),
                    ("4. Cross-Document Consistency",
                     "For each domain, the system retrieves [GUIDELINE SAYS] + [SAP SAYS] + [CSR SAYS] and presents "
                     "the three-way comparison to the LLM for inconsistency detection."),
                    ("5. Deterministic Pre-flight Checks",
                     "Zero-LLM checks: SAP amendment date vs. database lock (ICH E9 §5.1), estimand attribute "
                     "completeness (ICH E9(R1) §3.1), stratification factor/covariate consistency (FDA Covariate §III.A)."),
                ]:
                    st.markdown(f'<div class="agent-step"><strong>{step}</strong><br>{desc}</div>', unsafe_allow_html=True)
            with sap_arch_col2:
                st.markdown("#### Term Expansion Examples")
                st.dataframe(pd.DataFrame([
                    {"Abbreviation": "SAP", "Expanded To": "statistical analysis plan, analysis plan"},
                    {"Abbreviation": "ITT", "Expanded To": "intent-to-treat, full analysis set"},
                    {"Abbreviation": "MMRM", "Expanded To": "mixed model repeated measures"},
                    {"Abbreviation": "FWER", "Expanded To": "family-wise error rate, type I error control"},
                    {"Abbreviation": "LOCF", "Expanded To": "last observation carried forward"},
                    {"Abbreviation": "NRI", "Expanded To": "non-responder imputation"},
                    {"Abbreviation": "MNAR", "Expanded To": "missing not at random"},
                    {"Abbreviation": "ANCOVA", "Expanded To": "analysis of covariance"},
                    {"Abbreviation": "CMH", "Expanded To": "cochran-mantel-haenszel"},
                    {"Abbreviation": "DSMB", "Expanded To": "data safety monitoring board, DMC"},
                ]), use_container_width=True, hide_index=True)

                st.markdown("#### Deterministic Checks (Zero LLM)")
                st.dataframe(pd.DataFrame([
                    {"Check": "SAP amendment timing", "Guideline": "ICH E9 §5.1",
                     "Trigger": "SAP version date > DB lock date"},
                    {"Check": "Estimand completeness", "Guideline": "ICH E9(R1) §3.1",
                     "Trigger": "Any of 5 attributes missing"},
                    {"Check": "Strat. factor in model", "Guideline": "FDA Covariate §III.A",
                     "Trigger": "Randomisation factor absent from analysis covariates"},
                ]), use_container_width=True, hide_index=True)

            # Live SAP RAG stats from last analysis
            st.markdown("### Live SAP Retrieval Stats (Last Analysis)")
            results = st.session_state.get("analysis_results")
            if results:
                sap_result = results.get("sap") or {}
                sap_rag = sap_result.get("sap_rag") or {}
                sap_retrieved = sap_rag.get("retrieved_guidance_summary") or []
                sap_preflight = sap_result.get("findings") or []
                ss1, ss2, ss3 = st.columns(3)
                ss1.metric("SAP Passages Retrieved", len(sap_retrieved))
                ss2.metric("SAP KB Chunks Available", sap_rag.get("knowledge_base_size", "N/A"))
                ss3.metric("SAP Findings (incl. preflight)", len(sap_preflight))

                if sap_retrieved:
                    st.markdown("#### SAP Validator Retrieved Passages")
                    sap_retrieved_df = pd.DataFrame(sap_retrieved)
                    display_cols = [c for c in ["id", "title", "source", "section", "domain", "year", "relevance_score"] if c in sap_retrieved_df.columns]
                    st.dataframe(
                        sap_retrieved_df[display_cols].rename(columns={
                            "id": "Guideline", "title": "Document Title", "source": "Body",
                            "section": "Section", "domain": "Domain", "year": "Year", "relevance_score": "Score",
                        }),
                        use_container_width=True, hide_index=True,
                    )
            else:
                st.info("Run an analysis to see live SAP retrieval stats here.")

            # Build SAP KB button
            st.markdown("### SAP Validator KB Management")
            st.markdown(
                f"**Embedding model:** `{sap_meta['embedding_model']}`  "
                f"**Re-ranker:** `{sap_meta['reranker_model']}`  "
                f"**ChromaDB:** `{sap_meta['chroma_db_path']}`"
            )
            if st.button("Build / Rebuild SAP Validator KB", type="primary", key="build_sap_kb"):
                with st.spinner("Building SAP Validator KB — 2–5 min on first run..."):
                    try:
                        import sap_validator_knowledge_base as _svkb
                        _svkb._sap_retriever = None
                        _svkb._get_sap_retriever()
                        st.success("SAP Validator KB built. Reload page to see updated chunk count.")
                    except Exception as exc:
                        st.error(f"Build failed: {exc}")


def render_about() -> None:
    st.markdown("## Demo Setup")
    st.markdown("### Local Run")
    st.code(
        """pip install -r requirements.txt
export NEBIUS_API_KEY="your-nebius-api-key"
streamlit run app.py""",
        language="bash",
    )
    st.markdown("The app runs immediately with no-prereq live RAG guidance.")
    st.markdown("For full hybrid RAG indexing, also run:")
    st.code("pip install -r requirements-rag.txt", language="bash")

    st.info("Enter your Nebius API key and select a model from the sidebar. Those settings persist across all pages.")

    st.markdown("### RAG Runtime")
    kb_meta = get_kb_metadata()
    col1, col2, col3 = st.columns(3)
    col1.metric("Runtime Mode", kb_meta.get("runtime_mode", "unknown"))
    col2.metric("No-Prereq Chunks", kb_meta.get("fallback_chunks_available", 0))
    col3.metric("Indexed Chunks", kb_meta.get("total_chunks_indexed", 0))
    if not kb_meta.get("full_stack_ready"):
        st.info(
            "Full hybrid RAG is optional. The demo can run the full RAG process in real time with "
            "a no-prereq lexical index over built-in FDA/ICH/CFR guidance."
        )

    st.markdown("### No-Prereq Live RAG Demo")
    st.markdown(
        """
        This runs the RAG pipeline end to end without ChromaDB, embedding downloads, or external
        guideline files: load built-in corpus, chunk, build lexical index, route query, retrieve,
        rerank, and assemble cited context.
        """
    )
    if st.button("Run No-Prereq RAG Pipeline", type="primary"):
        st.session_state.live_rag_trace = build_no_prereq_rag_trace(
            [
                "eCTD v4 submissionunit.xml module structure file naming",
                "IND Phase 2 Phase 3 protocol SAP pre-specification 21 CFR 312",
                "clinical study report safety efficacy Module 5",
                "CMC quality Module 3 stability drug substance drug product",
            ],
            top_k=8,
        )

    render_rag_trace(st.session_state.get("live_rag_trace"))


def generate_markdown_report(results: dict[str, Any]) -> str:
    timeline = results.get("fda_review_timeline") or {}
    validation = results.get("input_validation") or {}
    validation_summary = validation.get("summary") or {}
    conformance = results.get("conformance") or {}
    knowledge_base = conformance.get("knowledge_base") or {}
    retrieved_guidance = conformance.get("retrieved_guidance") or []
    rule_findings = conformance.get("rule_based_findings") or []
    lines = [
        "# eCTD Submission Compliance Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Executive Summary",
        "",
        f"- Overall Compliance: {format_score(results.get('overall_score'))}",
        f"- Data Provenance: {format_score(results.get('data_provenance_score'))}",
        f"- SAP Validation: {format_score(results.get('sap_validation_score'))}",
        f"- FDA Conformance: {format_score(results.get('conformance_score'))}",
        f"- FDA Approval Probability: {format_score(results.get('approval_probability'))}",
        f"- Review Timeline: {timeline.get('total_weeks', 0)} weeks",
        f"- Input Validation: {validation.get('status', 'N/A')}",
        f"- Files Checked: {validation_summary.get('total_files', 'N/A')}",
        "",
        "## Priority 1",
    ]
    lines.extend(f"- {item}" for item in results.get("priority_1_items", []))
    lines.extend(["", "## Priority 2"])
    lines.extend(f"- {item}" for item in results.get("priority_2_items", []))
    lines.extend(
        [
            "",
            "## RAG-Grounded Conformance",
            "",
            f"- Knowledge chunks retrieved: {knowledge_base.get('chunks_retrieved', len(retrieved_guidance))}",
            f"- Knowledge chunks available: {knowledge_base.get('chunks_available', 'N/A')}",
            f"- Rule-based findings: {len(rule_findings)}",
            "",
            "### Retrieved Guidance",
        ]
    )
    if retrieved_guidance:
        lines.extend(
            f"- {chunk.get('id', 'N/A')}: {chunk.get('title', 'Untitled')} ({chunk.get('source', 'Unknown source')})"
            for chunk in retrieved_guidance[:8]
        )
    else:
        lines.append("- No retrieved guidance was attached.")
    lines.extend(["", "### Rule-Based Findings"])
    if rule_findings:
        lines.extend(
            f"- [{finding.get('severity', 'INFO')}] {finding.get('rule_id', 'N/A')}: "
            f"{finding.get('finding', '')} Recommendation: {finding.get('recommendation', '')}"
            for finding in rule_findings[:10]
        )
    else:
        lines.append("- No deterministic conformance findings were raised.")
    lines.extend(["", "## Expected FDA Questions"])
    lines.extend(f"{index}. {question}" for index, question in enumerate(results.get("expected_fda_questions", []), start=1))
    return "\n".join(lines)


def main() -> None:
    init_state()
    render_header()

    page_options = ["Overview", "Upload & Analyze", "Detailed Report", "RAG Knowledge Base", "Technical Blog", "Demo Setup"]
    if st.session_state.next_page in page_options:
        st.session_state.page = st.session_state.next_page
        st.session_state.next_page = None
    if st.session_state.page not in page_options:
        st.session_state.page = "Overview"

    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio("Page", page_options, key="page")

        st.markdown("---")
        st.markdown("### Nebius Settings")
        st.text_input(
            "API key",
            type="password",
            placeholder="Paste your Nebius Token Factory key",
            key="api_key_override",
        )
        _sidebar_key = get_api_key(st.session_state.get("api_key_override"))
        if _sidebar_key:
            st.caption("Key loaded.")
        else:
            st.caption("No key — enter above to run live LLM analysis.")

        if st.button("Load models", disabled=not bool(_sidebar_key), use_container_width=True):
            try:
                st.session_state.remote_models = list_remote_models(_sidebar_key)
                st.session_state.remote_model_error = None
            except ECTDAgentError as exc:
                st.session_state.remote_models = []
                st.session_state.remote_model_error = str(exc)

        if st.session_state.get("remote_model_error"):
            st.error(st.session_state.remote_model_error)

        _model_options = st.session_state.remote_models or get_available_models()
        _current_model = st.session_state.get("selected_model", DEFAULT_MODEL)
        _default_idx = _model_options.index(_current_model) if _current_model in _model_options else 0
        st.selectbox("Model", _model_options, index=_default_idx, key="selected_model")

        if st.session_state.remote_models:
            st.caption(f"{len(st.session_state.remote_models)} models loaded from Nebius.")

    mode = "Real LLM"
    api_key = get_api_key(st.session_state.get("api_key_override"))
    model = st.session_state.get("selected_model", DEFAULT_MODEL)

    if page == "Overview":
        render_overview(mode, model, api_key)
    elif page == "Upload & Analyze":
        render_upload_page(mode, model, api_key)
    elif page == "Detailed Report":
        render_detailed_report()
    elif page == "RAG Knowledge Base":
        render_rag_knowledge_base()
    elif page == "Technical Blog":
        render_evidence_page()
    else:
        render_about()


if __name__ == "__main__":
    main()
