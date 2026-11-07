# Enterprise Agentic AI – Data Operations Assistant POC

A small, interview-demo-ready multi-agent workflow for investigating a failed data pipeline.

## What it demonstrates

- Supervisor-style orchestration through a LangGraph workflow
- Data Agent for incident classification
- Knowledge Agent for local RAG-style troubleshooting retrieval
- Planner Agent for remediation steps
- Validation Agent for safety checks
- Human approval before the Action Agent runs
- Action Agent with **simulated-only** pipeline restart
- Reporting Agent for a downloadable incident report
- Optional OpenAI LLM enhancement

## Safety

This POC does not connect to Azure, Databricks, ADF, Snowflake, ServiceNow, or any production environment. The restart is simulated. Do not add real production credentials or connect real tools without enterprise security review, least-privilege identities, audit logging, approval controls, and change-management procedures.

## Prerequisites

- Python 3.10 or newer
- Internet access to install packages
- Optional OpenAI API key for LLM-assisted planning and summaries

## Run locally

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
venv\Scripts\activate
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local Streamlit URL printed in the terminal (usually http://localhost:8501).

## Optional LLM mode

Set environment variables before launching.

PowerShell:

```powershell
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

macOS / Linux:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

Then enable **Optional OpenAI LLM** in the sidebar. If the key is missing or the API call fails, the app continues with deterministic demo logic.

## Suggested demo script (5–7 minutes)

1. Explain the business scenario: a production data pipeline failed and a downstream dashboard is delayed.
2. Keep LLM mode off for a predictable first run.
3. Leave the sample timeout error, or try a schema mismatch:
   `AnalysisException: Cannot resolve column customer_region in source schema`
4. Click **Analyze incident**.
5. Walk through Data, Knowledge, Planner, and Validation agent outputs.
6. Explain why the action is paused for human approval.
7. Check the approval box and click **Submit approval and run simulated action**.
8. Show the simulated action result and download the incident report.
9. Explain what would change in production: authenticated APIs, real vector retrieval, access control, audit storage, monitoring, evaluation, and change approvals.

## Architecture

`Streamlit UI -> LangGraph workflow -> Data Agent -> Knowledge Agent -> Planner Agent -> Validation Agent -> Human approval -> Simulated Action Agent -> Reporting Agent`

## Production-hardening backlog

- Replace keyword retrieval with Azure AI Search or another approved vector/hybrid search service.
- Enforce document-level authorization during retrieval.
- Integrate Azure Databricks / ADF through approved APIs and managed identities.
- Use a durable audit store and centralized observability.
- Add evaluation datasets for retrieval quality, groundedness, tool correctness, and task completion.
- Add policy enforcement outside the LLM, idempotency, retries, timeouts, rate limits, and kill switches.
- Add automated unit, integration, security, and load tests.
- Establish model governance, cost controls, incident response, and human approval policies.
