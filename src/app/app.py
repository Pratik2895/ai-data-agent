"""AI Data Agent — Databricks App (Gradio chat UI)."""
import os

import gradio as gr
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "ai_data_agent_endpoint")

_base_cfg = Config()


def _workspace_client(user_token: str | None) -> WorkspaceClient:
    if user_token:
        return WorkspaceClient(host=_base_cfg.host, token=user_token, auth_type="pat")
    return WorkspaceClient(config=_base_cfg)


def respond(message, history, request: gr.Request):
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
        sdk_messages = []
        for m in messages:
            r_str = m["role"].lower()
            if r_str == "user":
                role = ChatMessageRole.USER
            elif r_str == "assistant":
                role = ChatMessageRole.ASSISTANT
            elif r_str == "system":
                role = ChatMessageRole.SYSTEM
            else:
                role = ChatMessageRole.USER
            sdk_messages.append(ChatMessage(role=role, content=m["content"]))
        resp = ws.serving_endpoints.query(
            name=SERVING_ENDPOINT,
            messages=sdk_messages,
            max_tokens=800,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Could not reach the agent endpoint `{SERVING_ENDPOINT}`.\n\nDetails: `{e}`"


demo = gr.ChatInterface(
    fn=respond,
    title="AI Data Agent",
    description=(
        "Ask about **data retrieval** (SQL queries, analytics, aggregations) or "
        "**ETL operations** (extract, transform, load data from APIs). "
        "Powered by a multi-agent system with SQL Analyst and ETL Analyst sub-agents."
    ),
    examples=[
        "What are the different types of payment methods we have?",
        "How many orders did we get last month?",
        "I want to extract data from an API and save it as CSV",
        "Transform the data file and remove all null values",
    ],
    theme=gr.themes.Soft(),
)

if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    demo.launch(server_name="0.0.0.0", server_port=port)
