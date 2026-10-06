# Databricks notebook source
# UC tool setup uses the metadata/SQL APIs; no Spark session is needed.
import re
import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

catalog = dbutils.widgets.get('catalog')
schema = dbutils.widgets.get('schema')
warehouse_id = dbutils.widgets.get('warehouse_id')
for identifier in (catalog, schema):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', identifier):
        raise ValueError('Invalid catalog/schema identifier')
client = WorkspaceClient()
tables = list(client.tables.list(catalog_name=catalog, schema_name=schema))
table_names = [table.name for table in tables]


def execute(statement):
    result = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout='30s')
    deadline = time.monotonic() + 120
    while result.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() > deadline:
            client.statement_execution.cancel_execution(result.statement_id)
            raise TimeoutError('UC tool creation timed out')
        time.sleep(1)
        result = client.statement_execution.get_statement(result.statement_id)
    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f'UC tool creation failed: {result.status.error}')


schema_info = '\n'.join(
    f'Table: {catalog}.{schema}.{name} | Columns: ' + ', '.join(
        f'{column.name} ({column.type_text})'
        for column in client.tables.get(f'{catalog}.{schema}.{name}').columns)
    for name in table_names)
escaped_schema = schema_info.replace("'", "''")
execute(f"""CREATE OR REPLACE FUNCTION {catalog}.{schema}.get_schema_info()
RETURNS STRING LANGUAGE SQL
COMMENT 'Returns project schemas captured during setup. Rerun setup after schema changes.'
RETURN '{escaped_schema}'""")
execute(f"""CREATE OR REPLACE FUNCTION {catalog}.{schema}.search_product_docs(query STRING)
RETURNS STRING LANGUAGE SQL
COMMENT 'Returns relevant product PDF filenames and extracted source text.'
RETURN (
  SELECT coalesce(nullif(concat_ws(' | ', collect_list(concat(file_name, ': ', content))), ''), 'No documentation found')
  FROM (
    SELECT file_name, substring(array_join(text_content, ' '), 1, 8000) AS content
    FROM {catalog}.{schema}.product_docs
    WHERE exists(split(lower(query), ' '), term -> length(term) > 3
      AND instr(lower(concat(file_name, ' ', array_join(text_content, ' '))), term) > 0)
    ORDER BY file_name LIMIT 4
  )
)""")
for name in table_names:
    if name == 'product_docs':
        continue
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise ValueError(f'Invalid table name: {name}')
    execute(f"""CREATE OR REPLACE FUNCTION {catalog}.{schema}.get_{name}()
    RETURNS STRING LANGUAGE SQL
    COMMENT 'Returns at most 100 rows from the {name} table as JSON.'
    RETURN (SELECT to_json(collect_list(struct(*)))
            FROM (SELECT * FROM {catalog}.{schema}.{name} LIMIT 100))""")
print(f'Created schema, document, and {len(table_names) - 1} table tools')
