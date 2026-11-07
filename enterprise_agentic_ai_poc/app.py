import os
from typing import TypedDict, Optional, List, Dict, Any

import streamlit as st
from langgraph.graph import StateGraph, END

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None


# -----------------------------
# Demo knowledge base (RAG-style)
# -----------------------------
KNOWLEDGE_BASE = [
    {
        "title": "Transient network or service timeout",
        "keywords": ["timeout", "connection", "network", "temporarily unavailable", "503"],
        "guidance": "Check upstream service health and network connectivity. If the failure is transient, retry with bounded exponential backoff. Confirm that the previous run did not partially commit data before retrying."
    },
    {
        "title": "Schema mismatch",
        "keywords": ["schema", "column", "datatype", "cast", "analysisexception"],
        "guidance": "Compare source and target schemas, identify added/removed columns or datatype changes, and validate the agreed schema evolution policy. Do not silently drop unexpected columns."
    },
    {
        "title": "Permission or authentication failure",
        "keywords": ["permission", "forbidden", "unauthorized", "access denied", "credential"],
        "guidance": "Verify the workload identity or service principal, secret validity, and least-privilege permissions on the target resource. Do not expose secrets in logs."
    },
    {
        "title": "Out of memory or executor failure",
        "keywords": ["out of memory", "oom", "executor lost", "memory", "spill"],
        "guidance": "Inspect Spark executor metrics, skewed partitions, shuffle volume, and cluster sizing. Consider repartitioning, skew handling, and right-sizing only after reviewing metrics."
    },
    {
        "title": "Duplicate or partial data after retry",
        "keywords": ["duplicate", "partial", "merge", "upsert", "retry"],
        "guidance": "Check whether the load is idempotent. Prefer deterministic batch identifiers and MERGE/upsert patterns where appropriate. Reconcile source and target counts before declaring recovery."
    },
]


class AgentState(TypedDict, total=False):
    incident_id: str
    pipeline_name: str
    environment: str
    error_text: str
    business_impact: str
    use_llm: bool
    approved: bool
    findings: Dict[str, Any]
    knowledge: List[Dict[str, str]]
    plan: List[str]
    validation: Dict[str, Any]
    action_result: str
    report: str
    status: str


def maybe_llm(prompt: str, enabled: bool) -> Optional[str]:
    """Optional LLM enhancement. The workflow remains usable without credentials."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not enabled or not api_key or ChatOpenAI is None:
        return None
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(model=model, temperature=0, api_key=api_key)
        response = llm.invoke(prompt)
        return str(response.content)
    except Exception as exc:
        return f"LLM enhancement unavailable; using deterministic demo logic. ({type(exc).__name__})"


def data_agent(state: AgentState) -> AgentState:
    error = state.get("error_text", "").lower()
    if any(x in error for x in ["timeout", "503", "connection"]):
        category = "Transient connectivity/service issue"
        severity = "High"
        likely_cause = "An upstream service or network dependency may be unavailable."
    elif any(x in error for x in ["schema", "column", "analysisexception", "datatype"]):
        category = "Schema or data contract issue"
        severity = "High"
        likely_cause = "The incoming data structure may not match the expected schema."
    elif any(x in error for x in ["permission", "unauthorized", "forbidden", "credential"]):
        category = "Access or identity issue"
        severity = "Critical"
        likely_cause = "The workload identity may lack access or have an expired credential."
    elif any(x in error for x in ["memory", "oom", "executor"]):
        category = "Spark resource issue"
        severity = "High"
        likely_cause = "Executor memory pressure, skew, or excessive shuffle may be involved."
    else:
        category = "Unknown / requires investigation"
        severity = "Medium"
        likely_cause = "The error does not match a known signature; inspect full logs and recent changes."

    state["findings"] = {
        "category": category,
        "severity": severity,
        "likely_cause": likely_cause,
        "pipeline": state.get("pipeline_name", "Unknown"),
        "environment": state.get("environment", "Unknown"),
        "impact": state.get("business_impact", "Not provided"),
    }
    return state


def knowledge_agent(state: AgentState) -> AgentState:
    text = (state.get("error_text", "") + " " + state.get("findings", {}).get("category", "")).lower()
    scored = []
    for item in KNOWLEDGE_BASE:
        score = sum(1 for keyword in item["keywords"] if keyword in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    state["knowledge"] = [item for _, item in scored[:3]]
    return state


def planner_agent(state: AgentState) -> AgentState:
    finding = state.get("findings", {})
    category = finding.get("category", "")
    plan = [
        "Confirm the incident scope, affected downstream jobs, and business impact.",
        "Review the latest successful run, recent deployments, configuration changes, and relevant logs.",
    ]
    if "connectivity" in category.lower():
        plan += [
            "Check upstream service health, network path, and endpoint availability.",
            "If the dependency is healthy and the previous run is confirmed safe, retry using the approved retry policy.",
        ]
    elif "schema" in category.lower():
        plan += [
            "Compare source and target schemas and identify the exact column or datatype difference.",
            "Confirm the schema evolution decision with the data owner before changing mappings or target structures.",
        ]
    elif "access" in category.lower():
        plan += [
            "Verify the workload identity and required resource permissions without exposing credentials.",
            "Request an approved least-privilege access correction from the platform/security owner.",
        ]
    elif "spark" in category.lower():
        plan += [
            "Inspect executor memory, shuffle, skew, and partition metrics.",
            "Tune partitioning or cluster resources only after validating the bottleneck with Spark metrics.",
        ]
    else:
        plan += [
            "Collect driver and executor logs, job metrics, and the latest code/configuration changes.",
            "Route the incident to the owning engineering lead if the root cause remains unclear.",
        ]
    plan += [
        "Reconcile source and target record counts and validate data quality after recovery.",
        "Record the root cause, actions, approvals, and evidence in the incident ticket.",
    ]

    if state.get("use_llm"):
        prompt = (
            "You are an enterprise data operations planning assistant. "
            "Improve this remediation plan without inventing facts. "
            "Do not recommend destructive actions or bypassing approvals. "
            f"Incident findings: {finding}. Existing plan: {plan}. "
            "Return a concise numbered action plan."
        )
        enhanced = maybe_llm(prompt, True)
        if enhanced and not enhanced.startswith("LLM enhancement unavailable"):
            plan = [line.strip(" -0123456789.\t") for line in enhanced.splitlines() if line.strip()]
    state["plan"] = plan
    return state


def validation_agent(state: AgentState) -> AgentState:
    severity = state.get("findings", {}).get("severity", "Medium")
    checks = {
        "read_only_diagnostics": True,
        "approval_required_for_restart": True,
        "destructive_actions_allowed": False,
        "severity": severity,
        "decision": "Awaiting human approval before simulated restart.",
    }
    state["validation"] = checks
    state["status"] = "AWAITING_APPROVAL"
    return state


def action_agent(state: AgentState) -> AgentState:
    if not state.get("approved", False):
        state["action_result"] = "No action taken. Human approval has not been provided."
        state["status"] = "AWAITING_APPROVAL"
        return state

    # Safe demo: no real cloud or production system is called.
    state["action_result"] = (
        "SIMULATION ONLY: Restart request approved and simulated successfully. "
        "No real Databricks, ADF, or production pipeline was modified."
    )
    state["status"] = "SIMULATED_RECOVERY"
    return state


def reporting_agent(state: AgentState) -> AgentState:
    f = state.get("findings", {})
    knowledge = state.get("knowledge", [])
    report_lines = [
        f"# Incident report: {state.get('incident_id', 'INC-DEMO-001')}",
        "",
        f"- **Pipeline:** {state.get('pipeline_name', 'Unknown')}",
        f"- **Environment:** {state.get('environment', 'Unknown')}",
        f"- **Severity:** {f.get('severity', 'Unknown')}",
        f"- **Classification:** {f.get('category', 'Unknown')}",
        f"- **Likely cause:** {f.get('likely_cause', 'Unknown')}",
        f"- **Business impact:** {f.get('impact', 'Not provided')}",
        f"- **Workflow status:** {state.get('status', 'Unknown')}",
        "",
        "## Recommended actions",
    ]
    report_lines += [f"{i}. {item}" for i, item in enumerate(state.get("plan", []), 1)]
    report_lines += ["", "## Retrieved operational knowledge"]
    if knowledge:
        report_lines += [f"- **{item['title']}:** {item['guidance']}" for item in knowledge]
    else:
        report_lines += ["- No matching knowledge article found. Manual investigation is required."]
    report_lines += ["", "## Action result", state.get("action_result", "No action executed.")]
    report_lines += ["", "> Demo safety note: this POC uses simulated actions only. Production integration requires approved APIs, identity controls, audit logging, and operational change procedures."]
    state["report"] = "\n".join(report_lines)

    if state.get("use_llm"):
        summary = maybe_llm(
            "Summarize this incident report for an enterprise operations manager in 3 concise bullets. "
            "Do not add facts.\n\n" + state["report"],
            True,
        )
        if summary and not summary.startswith("LLM enhancement unavailable"):
            state["report"] += "\n\n## Executive summary (LLM-assisted)\n" + summary
    return state


def build_graph(include_action: bool = False):
    graph = StateGraph(AgentState)
    graph.add_node("data_agent", data_agent)
    graph.add_node("knowledge_agent", knowledge_agent)
    graph.add_node("planner_agent", planner_agent)
    graph.add_node("validation_agent", validation_agent)
    graph.add_node("action_agent", action_agent)
    graph.add_node("reporting_agent", reporting_agent)

    graph.set_entry_point("data_agent")
    graph.add_edge("data_agent", "knowledge_agent")
    graph.add_edge("knowledge_agent", "planner_agent")
    graph.add_edge("planner_agent", "validation_agent")
    if include_action:
        graph.add_edge("validation_agent", "action_agent")
        graph.add_edge("action_agent", "reporting_agent")
    else:
        graph.add_edge("validation_agent", "reporting_agent")
    graph.add_edge("reporting_agent", END)
    return graph.compile()


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Enterprise Agentic AI POC", page_icon="🤖", layout="wide")
st.title("🤖 Enterprise Agentic AI – Data Operations Assistant")
st.caption("Multi-agent incident investigation, RAG-style knowledge retrieval, human approval, and simulated remediation.")

with st.sidebar:
    st.header("Demo configuration")
    use_llm = st.toggle("Enable optional OpenAI LLM", value=False)
    if use_llm and not os.getenv("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY is not set. The app will use deterministic demo logic.")
    st.info("All pipeline actions are simulated. No production system is connected.")

col1, col2 = st.columns(2)
with col1:
    incident_id = st.text_input("Incident ID", "INC-2026-1042")
    pipeline_name = st.text_input("Pipeline name", "Customer_Daily_Load")
    environment = st.selectbox("Environment", ["Production", "UAT", "Development"])
with col2:
    business_impact = st.text_input("Business impact", "Daily customer dashboard refresh is delayed.")
    error_text = st.text_area(
        "Pipeline error / log excerpt",
        "Job failed with ConnectionTimeout: upstream API returned 503 Service Unavailable after 3 retries.",
        height=130,
    )

if "workflow_state" not in st.session_state:
    st.session_state.workflow_state = None
if "approved" not in st.session_state:
    st.session_state.approved = False

run_col, reset_col = st.columns([1, 5])
with run_col:
    analyze = st.button("🔍 Analyze incident", type="primary", use_container_width=True)
with reset_col:
    if st.button("Reset demo"):
        st.session_state.workflow_state = None
        st.session_state.approved = False
        st.rerun()

if analyze:
    initial_state: AgentState = {
        "incident_id": incident_id,
        "pipeline_name": pipeline_name,
        "environment": environment,
        "error_text": error_text,
        "business_impact": business_impact,
        "use_llm": use_llm,
        "approved": False,
    }
    with st.spinner("Agents are collaborating..."):
        st.session_state.workflow_state = build_graph(include_action=False).invoke(initial_state)
    st.session_state.approved = False

state = st.session_state.workflow_state
if state:
    st.divider()
    st.subheader("Agent execution results")
    findings = state.get("findings", {})
    a, b, c = st.columns(3)
    a.metric("Severity", findings.get("severity", "N/A"))
    b.metric("Classification", findings.get("category", "N/A"))
    c.metric("Workflow status", state.get("status", "N/A"))

    with st.expander("1. Data Agent – incident analysis", expanded=True):
        st.write("**Likely cause:**", findings.get("likely_cause"))
        st.write("**Business impact:**", findings.get("impact"))

    with st.expander("2. Knowledge Agent – retrieved guidance", expanded=True):
        if state.get("knowledge"):
            for item in state["knowledge"]:
                st.markdown(f"**{item['title']}**")
                st.write(item["guidance"])
        else:
            st.info("No matching knowledge article. Manual investigation is required.")

    with st.expander("3. Planner Agent – remediation plan", expanded=True):
        for i, item in enumerate(state.get("plan", []), 1):
            st.write(f"{i}. {item}")

    with st.expander("4. Validation Agent – safety checks", expanded=True):
        st.json(state.get("validation", {}))

    st.warning("Human approval is required before the simulated restart action.")
    approved = st.checkbox("I approve the simulated pipeline restart for this demo.", value=st.session_state.approved)
    st.session_state.approved = approved

    if st.button("✅ Submit approval and run simulated action", disabled=not approved, type="primary"):
        approved_state = dict(state)
        approved_state["approved"] = True
        with st.spinner("Action Agent and Reporting Agent are running..."):
            final_state = build_graph(include_action=True).invoke(approved_state)
        st.session_state.workflow_state = final_state
        st.rerun()

    if state.get("status") == "SIMULATED_RECOVERY":
        st.success(state.get("action_result"))
        st.subheader("5. Reporting Agent – incident report")
        st.markdown(state.get("report", ""))
        st.download_button(
            "Download incident report",
            data=state.get("report", ""),
            file_name=f"{incident_id}_incident_report.md",
            mime="text/markdown",
        )

st.divider()
st.caption("POC limitations: local keyword-based retrieval rather than production vector search; simulated tool execution; optional LLM enhancement. Add enterprise identity, approved connectors, persistent audit storage, evaluation datasets, and security review before production.")
