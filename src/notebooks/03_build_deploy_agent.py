# Databricks notebook source
# MAGIC %pip install mlflow==3.6.0 databricks-langchain==0.3.0 langgraph==1.2.12 databricks-agents sqlglot pandas requests

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
llm_low = dbutils.widgets.get("llm_low")
llm_medium = dbutils.widgets.get("llm_medium")
llm_high = dbutils.widgets.get("llm_high")
agent_model_name = dbutils.widgets.get("agent_model_name")
agent_endpoint = dbutils.widgets.get("agent_endpoint")

warehouse_id = dbutils.widgets.get("warehouse_id")
# --- Step 2: Copy agent.py to local path ---
print("\n=== Step 2: Preparing agent code ===")
import shutil
import os

agent_source = dbutils.widgets.get("agent_source")
agent_local = "/tmp/agent.py"
shutil.copy2(agent_source, agent_local)
print(f"Copied agent.py to {agent_local}")

# Set environment variables for the agent
os.environ["LLM_HIGH"] = llm_high
os.environ["LLM_MEDIUM"] = llm_medium
os.environ["LLM_LOW"] = llm_low
os.environ["CATALOG"] = catalog
os.environ["SCHEMA"] = schema
os.environ["DATABRICKS_WAREHOUSE_ID"] = warehouse_id

# --- Step 3: Log model to MLflow ---
print("\n=== Step 3: Logging agent to MLflow ===")
import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction, DatabricksSQLWarehouse, DatabricksTable

mlflow.set_registry_uri("databricks-uc")

# Resources: LLM endpoints + UC functions used as tools
resources = [
    DatabricksSQLWarehouse(warehouse_id=warehouse_id),
    *[DatabricksTable(table_name=f"{catalog}.{schema}.{t}") for t in ["cust_service_data", "products", "policies", "product_docs"]],
    DatabricksServingEndpoint(endpoint_name=llm_high),
    DatabricksServingEndpoint(endpoint_name=llm_medium),
    DatabricksServingEndpoint(endpoint_name=llm_low),
    DatabricksFunction(function_name=f"{catalog}.{schema}.search_product_docs"),
    DatabricksFunction(function_name=f"{catalog}.{schema}.get_schema_info"),
    DatabricksFunction(function_name=f"{catalog}.{schema}.get_cust_service_data"),
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
        code_paths=[os.path.join(os.path.dirname(agent_source), "runtime.py")],
        pip_requirements=[
            "mlflow==3.6.0",
            "databricks-langchain==0.3.0",
            "sqlglot", "pandas", "requests",
            "langgraph==1.2.12",
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

agents.deploy(
    agent_model_name,
    model_version=int(model_info.registered_model_version),
    endpoint_name=agent_endpoint,
    scale_to_zero=True,
    environment_vars={"CATALOG": catalog, "SCHEMA": schema, "LLM_HIGH": llm_high,
                      "LLM_MEDIUM": llm_medium, "LLM_LOW": llm_low,
                      "DATABRICKS_WAREHOUSE_ID": warehouse_id},
    tags={"source": "dab", "project": "ai-data-agent"},
)

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