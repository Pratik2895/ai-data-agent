# Databricks notebook source
# === Notebook 03: Build and Deploy Agent ===
# Registers the AI Data Agent as a Databricks model and deploys it to Model Serving.

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
agent_endpoint = dbutils.widgets.get("agent_endpoint")

print(f"Building agent in {catalog}.{schema}")
print(f"LLM endpoint: {llm_endpoint}")
print(f"Agent endpoint: {agent_endpoint}")

import mlflow
import tempfile
import os

model_name = f"{catalog}.{schema}.ai_data_agent"

agent_code = '''from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
CATALOG = "{}"
SCHEMA = "{}"
LLM_ENDPOINT = "{}"
def llm_chat(messages, model=LLM_ENDPOINT, max_tokens=800):
    ws = WorkspaceClient()
    sdk_messages = []
    for m in messages:
        role = ChatMessageRole.USER if m.get("role") == "user" else ChatMessageRole.ASSISTANT
        sdk_messages.append(ChatMessage(role=role, content=m.get("content", "")))
    resp = ws.serving_endpoints.query(name=model, messages=sdk_messages, max_tokens=max_tokens)
    return resp.choices[0].message.content
def predict(messages):
    response = llm_chat(messages)
    return {"response": response}
'''.format(catalog, schema, llm_endpoint)

agent_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
agent_file.write(agent_code)
agent_file.close()

with mlflow.start_run(run_name="ai_data_agent_setup") as run:
    mlflow.log_artifact(agent_file.name, artifact_path="agent")
    mlflow.log_param("catalog", catalog)
    mlflow.log_param("schema", schema)
    mlflow.log_param("llm_endpoint", llm_endpoint)
    mlflow.register_model(name=model_name, source=f"runs:/{run.info.run_id}/agent")
    print(f"Registered model: {model_name}")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedModelInput

ws = WorkspaceClient()
try:
    ws.serving_endpoints.get(name=agent_endpoint)
    print(f"Endpoint {agent_endpoint} already exists.")
except Exception:
    print(f"Creating endpoint {agent_endpoint}...")
    ws.serving_endpoints.create(
        name=agent_endpoint,
        config=EndpointCoreConfigInput(
            served_models=[ServedModelInput(model_name=model_name, model_version=1, scale_to_zero_enabled=True, workload_size="Small")],
        ),
    )
    print(f"Endpoint {agent_endpoint} created.")

os.unlink(agent_file.name)
print(f"\n=== Agent Build and Deploy Complete ===")
print(f"Model: {model_name}")
print(f"Endpoint: {agent_endpoint}")
