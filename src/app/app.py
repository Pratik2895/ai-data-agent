"""AI Data Agent — Databricks App (Gradio chat UI).

Browser-based interface for the multi-agent system. The app calls the
Model Serving endpoint which runs the ResponsesAgent wrapping the
LangGraph multi-agent system (AI-DECIDE router + SQL/ETL/Knowledge sub-agents).
"""
import os
import json

import gradio as gr
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "ai_data_agent_endpoint")
CATALOG = os.environ.get("CATALOG", "ai_agent_demo")
SCHEMA = os.environ.get("SCHEMA", "customer_support")

_base_cfg = Config()


def _workspace_client(user_token: str | None) -> WorkspaceClient:
    if user_token:
        return WorkspaceClient(host=_base_cfg.host, token=user_token, auth_type="pat")
    return WorkspaceClient(config=_base_cfg)


def respond(message, history, request: gr.Request):
    """Send user message to the multi-agent serving endpoint and return the response."""
    user_token = None
    if request is not None:
        user_token = request.headers.get("x-forwarded-access-token")

    messages = []
    for turn in history or []:
        if isinstance(turn, dict):
            if turn.get("content"):
                messages.append({"role": turn.get("role", "user"), "content": turn["content"]})
        else:
            user_msg, bot_msg = turn
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if bot_msg:
                messages.append({"role": "assistant", "content": bot_msg})
    messages.append({"role": "user", "content": message})

    try:
        ws = _workspace_client(user_token)
        from urllib.parse import quote
        resp = ws.api_client.do("POST", f"/serving-endpoints/{quote(SERVING_ENDPOINT, safe='')}/invocations",
                                body={"input": messages})
        texts = [part.get("text", "") for item in resp.get("output", [])
                 for part in item.get("content", []) if part.get("type") == "output_text"]
        if not texts:
            raise RuntimeError("Endpoint returned no text output")
        return "\n".join(texts)
    except Exception as e:
        return (
            f"⚠️ Could not reach the agent endpoint `{SERVING_ENDPOINT}`.\n\n"
            f"Details: `{e}`\n\n"
            f"Make sure the setup job has completed and the endpoint is READY."
        )


demo = gr.ChatInterface(
    fn=respond,
    title="🤖 AI Data Agent — Multi-Agent System",
    description=(
        "Ask questions about **customer data** (SQL queries, analytics), "
        "**ETL operations** (extract, transform, load), or **product documentation** (PDF search). "
        "The AI-DECIDE router automatically directs your query to the right sub-agent:\n"
        "• **SQL Analyst** — stateful orchestration with AI-as-judge for safe query execution\n"
        "• **ETL Analyst** — ReAct loop with UC function tools\n"
        "• **Knowledge Search** — searches parsed PDF product documentation"
    ),
    examples=[
        "What are the different types of customer issues in our database?",
        "How many tickets are resolved vs pending?",
        "What does the product documentation say about the BrewMaster 3000?",
        "Analyze customer complaint patterns and find the most common issue types",
        "I want to extract data from an API and save it as CSV",
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    demo.launch(server_name="0.0.0.0", server_port=port)
