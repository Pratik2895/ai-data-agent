"""Bounded SQL execution and declarative ETL tools shared by serving and local runs."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse


def validate_sql(sql):
    import sqlglot
    from sqlglot import exp
    statements = sqlglot.parse(sql, read="databricks")
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("Only one SELECT query is allowed")
    tree = statements[0]
    for node in tree.walk():
        if isinstance(node, (exp.DDL, exp.DML, exp.Command, exp.Into)):
            raise ValueError("Database changes are prohibited")
        if isinstance(node, exp.Anonymous):
            raise ValueError("Unapproved SQL function")
    catalog = os.getenv("CATALOG", "ai_agent_demo")
    schema = os.getenv("SCHEMA", "customer_support")
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not table.db and not table.catalog and table.name in ctes:
            continue
        if table.catalog != catalog or table.db != schema:
            raise ValueError("Queries must stay within the configured catalog and schema")
    return tree.sql(dialect="databricks")


def execute_statement(client, sql):
    from databricks.sdk.service.sql import StatementState
    warehouse = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if not warehouse:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is required")
    result = client.statement_execution.execute_statement(
        warehouse_id=warehouse, statement=sql, wait_timeout="30s", row_limit=100,
        byte_limit=1000000)
    deadline = time.monotonic() + 90
    while result.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() >= deadline:
            client.statement_execution.cancel_execution(result.statement_id)
            raise TimeoutError("SQL execution exceeded 90 seconds")
        time.sleep(1)
        result = client.statement_execution.get_statement(result.statement_id)
    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"SQL failed: {result.status.error}")
    columns = [c.name for c in result.manifest.schema.columns] if result.manifest and result.manifest.schema else []
    rows = result.result.data_array if result.result else []
    return json.dumps({"columns": columns, "rows": rows or [], "truncated": bool(result.manifest and result.manifest.truncated)})


def data_path(name):
    root = Path(os.getenv("ETL_DATA_ROOT", "/tmp/ai-data-agent")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.csv", name):
        raise ValueError("Dataset must be a simple CSV filename")
    return root / name


def extract_api(url: str, dataset: str = "extracted.csv") -> str:
    """Extract an allowlisted HTTPS JSON API into a CSV dataset. Redirects are prohibited."""
    import requests
    import pandas as pd
    parsed = urlparse(url)
    hosts = {h.strip() for h in os.getenv("ETL_ALLOWED_HOSTS", "jsonplaceholder.typicode.com").split(",")}
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("API URL must use HTTPS and an explicitly allowlisted hostname")
    path = data_path(dataset)
    with requests.get(url, timeout=30, allow_redirects=False, stream=True) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("API redirects are prohibited")
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 5_000_000:
                raise ValueError("API response exceeds 5 MB")
    data = json.loads(body)
    if isinstance(data, dict):
        data = data.get("results", [data])
    frame = pd.json_normalize(data)
    if len(frame) > 10000:
        raise ValueError("Dataset exceeds 10000 rows")
    frame.to_csv(path, index=False)
    return json.dumps({"dataset": dataset, "rows": len(frame), "columns": list(frame.columns)})


def inspect_dataset(dataset: str) -> str:
    """Inspect column names and the first three rows of a CSV dataset."""
    import pandas as pd
    frame = pd.read_csv(data_path(dataset))
    return frame.head(3).to_json(orient="records")


def transform_dataset(dataset: str, output: str, columns: list[str] | None = None,
                      drop_duplicates: bool = False, drop_nulls: bool = False) -> str:
    """Select columns, drop duplicates or null rows, and save a transformed CSV without executing generated code."""
    import pandas as pd
    frame = pd.read_csv(data_path(dataset))
    if columns:
        frame = frame[columns]
    if drop_duplicates:
        frame = frame.drop_duplicates()
    if drop_nulls:
        frame = frame.dropna()
    frame.to_csv(data_path(output), index=False)
    return json.dumps({"dataset": output, "rows": len(frame), "columns": list(frame.columns)})


def etl_tools():
    from langchain_core.tools import tool
    return [tool(extract_api), tool(inspect_dataset), tool(transform_dataset)]
