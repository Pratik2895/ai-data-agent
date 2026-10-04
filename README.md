# AI Data Agent

Databricks-native LangGraph agent with a SQL analyst, a bounded ETL tool loop, and product-document search. Gradio calls the MLflow ResponsesAgent endpoint with conversation history.

## Setup

Requires Python 3.11 and Databricks CLI >=1.0. Authenticate to the selected workspace:

```powershell
databricks auth login --profile dev-52d59088
uv venv --python 3.11
uv pip install --python .venv/Scripts/python.exe -r requirements.txt pytest
.venv/Scripts/python.exe -m pytest -q tests
databricks bundle validate --strict --profile dev-52d59088
databricks bundle deploy --profile dev-52d59088
databricks bundle run setup_ai_data_agent --profile dev-52d59088
databricks bundle run ai_data_agent_app --profile dev-52d59088
```

The app uses the GitHub branch configured in `resources/app.yml`; push source changes there before deploying the app. The workspace requires Git-backed Apps.

Serving provisioning is asynchronous: check that `state.ready` is `READY` and `state.config_update` is `NOT_UPDATING` before querying the endpoint.

The setup job copies the existing customer-service CSVs from the configured source volume, creates the target catalog/schema/volume, loads Delta tables, extracts text from PDFs, registers UC tools, logs the agent, and deploys the named serving endpoint. Supply `--var warehouse_id=<id>` for another SQL warehouse and override catalog/schema/source variables for another environment. Deployment errors fail the job instead of reporting success.

## Runtime

SQL runs through question curation, schema context, generation, deterministic SELECT-only catalog/schema validation, an LLM judge, bounded warehouse execution, and answer formatting. Results include column names and truncation status. Resource dependencies are declared to MLflow for serving authentication.

ETL supports HTTPS JSON extraction, CSV inspection, column selection, duplicate removal, null removal, and CSV loading into its working directory. The default allowlist contains `jsonplaceholder.typicode.com`; configure `ETL_ALLOWED_HOSTS` explicitly for other APIs. Redirects, path traversal, oversized inputs, and arbitrary generated Python execution are rejected. Outputs are temporary serving-instance files; they are not durable Unity Catalog tables or user downloads. Configure a durable execution service before using this ETL workflow in production. Tool loops stop after 20 graph steps.

Knowledge search uses the extracted PDF text via a UC function. Text extraction uses pypdf; scanned PDFs need OCR preprocessing. This implementation does not provision a Vector Search index.

Local invocation uses the same agent runtime and Databricks authentication; no separate OpenAI or Anthropic key is required. Load `.env` from `.env.example` with python-dotenv if desired, and invoke `src.agents.agent.DataAgent` with `ResponsesAgentRequest`. Run `.venv/Scripts/python.exe main.py "How many customer service tickets are there?" --profile dev-52d59088` after copying `.env.example` to `.env`. The local runner obtains CLI OAuth credentials in memory without writing or displaying them.

## Validation

GitHub Actions runs the offline tests and Python compilation on pushes and pull requests.

`tests/test_runtime.py` covers unsafe SQL, cross-catalog queries, CTEs, path traversal, API URL boundaries, SQL failures, CSV transformations, the SQL graph, and ResponsesAgent output. Cloud deployment additionally requires source-data access, catalog/schema create rights, SQL warehouse usage, UC function execution, and available model-serving compute.
