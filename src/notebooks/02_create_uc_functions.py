# Databricks notebook source
# DBTITLE 1,Create UC Functions (Agent Tools)
# Databricks notebook source
# === Notebook 02: Create UC Functions (Agent Tools) ===
# Creates Unity Catalog SQL functions that serve as tools for the AI agents.
# These functions are loaded via UCFunctionToolkit in the agent code.

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

print(f"Creating UC functions in {catalog}.{schema}")

tables = spark.sql(f"SHOW TABLES IN {catalog}.{schema}").collect()
table_names = [t.tableName for t in tables]
print(f"Available tables: {table_names}")

# --- Function 1: search_product_docs ---
# Searches parsed PDF product documentation using AI functions.
print("\n--- Creating search_product_docs function ---")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.search_product_docs(query STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Search parsed product documentation (PDFs) for information relevant to the query. Returns a summary answer based on product manuals and spec sheets.'
RETURN (
  SELECT coalesce(concat_ws(' | ', collect_list(concat(file_name, ': ', content))), 'No documentation found')
  FROM (
    SELECT file_name, substring(array_join(text_content, ' '), 1, 8000) AS content
    FROM {catalog}.{schema}.product_docs
    WHERE exists(split(lower(query), ' '), term -> length(term) > 3
      AND instr(lower(concat(file_name, ' ', array_join(text_content, ' '))), term) > 0)
    ORDER BY file_name
    LIMIT 4
  )
)
""")
print(f"  Created: {catalog}.{schema}.search_product_docs")

# Capture only this project's schemas during setup, avoiding system-catalog access at inference.
schema_info = "\n".join(
    f"Table: {catalog}.{schema}.{name} | Columns: " + ", ".join(
        f"{field.name} ({field.dataType.simpleString()})"
        for field in spark.table(f"{catalog}.{schema}.{name}").schema.fields)
    for name in table_names
)
escaped_schema = schema_info.replace("'", "''")
spark.sql(f"""CREATE OR REPLACE FUNCTION {catalog}.{schema}.get_schema_info()
RETURNS STRING LANGUAGE SQL
COMMENT 'Returns the project table schemas captured during setup. Rerun setup after schema changes.'
RETURN '{escaped_schema}'""")

# --- Function 3: Table access functions ---
print("\n--- Creating table access functions ---")
for table_name in table_names:
    if table_name == 'product_docs':
        continue
    func_name = f"get_{table_name}"
    full_func = f"{catalog}.{schema}.{func_name}"
    spark.sql(f"CREATE OR REPLACE FUNCTION {full_func}() RETURNS STRING LANGUAGE SQL COMMENT 'Returns rows from {table_name} table (limited to 100). Use for data analysis.' RETURN (SELECT to_json(collect_list(struct(*))) FROM (SELECT * FROM {catalog}.{schema}.{table_name} LIMIT 100))")
    print(f"  Created: {full_func}()")

