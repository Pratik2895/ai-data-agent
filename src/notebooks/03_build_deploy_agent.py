# Databricks notebook source
# DBTITLE 1,Build and Deploy Multi-Agent System
# Databricks notebook source
# === Notebook 03: Build and Deploy Multi-Agent System ===
# Installs packages, logs the ResponsesAgent to MLflow, deploys to Model Serving.
# This builds the COMPLETE multi-agent system with sub-agents and stateful orchestration.

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
llm_low = dbutils.widgets.get("llm_low")
llm_medium = dbutils.widgets.get("llm_medium")
llm_high = dbutils.widgets.get("llm_high")
agent_model_name = dbutils.widgets.get("agent_model_name")
agent_endpoint = dbutils.widgets.get("agent_endpoint")

print(f"Building agent: {agent_model_name}")
print(f"LLM High: {llm_high}, Medium: {llm_medium}, Low: {llm_low}")
print(f"Serving endpoint: {agent_endpoint}")

# --- Step 1: Install packages ---
print("\n=== Step 1: Installing packages ===")
%pip install -U mlflow==3.6.0 databricks-langchain langgraph==0.3.4 databricks-agents pydantic
dbutils.library.restartPython()

# --- Step 2: Copy agent.py to local path ---
print("\n=== Step 2: Preparing agent code ===")
import shutil
import os

agent_source = "/Workspace/Users/bhikadiya.pratik@gmail.com/ai-data-agent-repo/src/agents/agent.py"
agent_local = "/tmp/agent.py"
shutil.copy2(agent_source, agent_local)
print(f"Copied agent.py to {agent_local}")

# Set environment variables for the agent
os.environ["LLM_HIGH"] = llm_high
os.environ["LLM_MEDIUM"] = llm_medium
os.environ["LLM_LOW"] = llm_low
os.environ["CATALOG"] = catalog
os.environ["SCHEMA"] = schema

# --- Step 3: Log model to MLflow ---
print("\n=== Step 3: Logging agent to MLflow ===")
import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction

mlflow.set_registry_uri("databricks-uc")

# Resources: LLM endpoints + UC functions used as tools
resources = [
    DatabricksServingEndpoint(endpoint_name=llm_high),
    DatabricksServingEndpoint(endpoint_name=llm_medium),
    DatabricksServingEndpoint(endpoint_name=llm_low),
    DatabricksFunction(function_name=f"{catalog}.{schema}.search_product_docs"),
    DatabricksFunction(function_name=f"{catalog}.{schema}.get_schema_info"),
    DatabricksFunction(function_name=f"{catalog}.{schema}.get_cust_service_data"),
    DatabricksFunction(function_name=f"{catalog}.{schema}.analyze_customer_tickets"),
]

# Add table-access functions for any other tables
for table_name in ["policies", "products"]:
    func_name = f"{catalog}.{schema}.get_{table_name}"
    try:
        resources.append(DatabricksFunction(function_name=func_name))
    except Exception:
        pass

with mlflow.start_run(run_name="ai_data_agent_build") as run:
    model_info = mlflow.pyfunc.log_model(
        name="agent",
        python_model=agent_local,
        resources=resources,
        pip_requirements=[
            "mlflow==3.6.0",
            "databricks-langchain",
            "langgraph==0.3.4",
            "databricks-agents",
        ],
        input_example={
            "input": [{"role": "user", "content": "What are the different types of payment methods?"}]
        },
        registered_model_name=agent_model_name,
    )
    print(f"  Model logged: {agent_model_name} (version {model_info.registered_model_version})")
    print(f"  Run ID: {run.info.run_id}")

# --- Step 4: Deploy to Model Serving ---
print("\n=== Step 4: Deploying to Model Serving ===")
from databricks import agents

try:
    agents.deploy(
        agent_model_name,
        version=str(model_info.registered_model_version),
        tags={"source": "dab", "project": "ai-data-agent"},
    )
    print(f"  Deployment initiated for endpoint: {agent_endpoint}")
    print(f"  This takes ~10-15 minutes. Check status in the Model Serving UI.")
except Exception as e:
    print(f"  Deployment note: {e}")
    print(f"  You can deploy manually from the Model Serving UI.")
    print(f"  Model: {agent_model_name} version {model_info.registered_model_version}")

# --- Step 5: Summary ---
print("\n=== Build and Deploy Complete ===")
print(f"  Registered model: {agent_model_name}")
print(f"  Model version: {model_info.registered_model_version}")
print(f"  Serving endpoint: {agent_endpoint}")
print(f"  LLM endpoints: {llm_high} (high), {llm_medium} (medium), {llm_low} (low)")
print("\nArchitecture:")
print("  - AI-DECIDE Router (determines SQL vs ETL vs KNOWLEDGE)")
print("  - SQL Analyst (stateful: curate -> context -> generate -> judge -> execute -> format)")
print("  - ETL Analyst (ReAct loop with UC function tools)")
print("  - Knowledge Search (searches parsed PDF product documentation)")
print("  - Deployed as ResponsesAgent via MLflow Model Serving")
print(f"\nNext: Deploy the Databricks App ({agent_endpoint}) via DAB to get the browser UI.")