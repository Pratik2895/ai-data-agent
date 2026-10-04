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
spark.sql(f"DROP FUNCTION IF EXISTS {catalog}.{schema}.search_product_docs")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.search_product_docs(query STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Search parsed product documentation (PDFs) for information relevant to the query. Returns a summary answer based on product manuals and spec sheets.'
RETURN (
  SELECT ai_gen(concat(
    'You are a product knowledge assistant. Answer the question based on the product documentation below. If the answer is not found, say No relevant documentation found. Question: ',
    query,
    ' Product documentation: ',
    (
      SELECT concat_ws(' | ', collect_list(concat(file_name, ': ', array_join(text_content, ' '))))
      FROM {catalog}.{schema}.product_docs
      LIMIT 20
    )
  ))
)
""")
print(f"  Created: {catalog}.{schema}.search_product_docs")

# --- Function 2: get_schema_info ---
# Returns table schema info for context engineering.
print("\n--- Creating get_schema_info function ---")
spark.sql(f"DROP FUNCTION IF EXISTS {catalog}.{schema}.get_schema_info")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.get_schema_info()
RETURNS STRING
LANGUAGE SQL
COMMENT 'Returns schema info for all tables: table names, column names, data types. Used for context engineering in the SQL Analyst agent.'
RETURN (
  SELECT concat_ws('\n', collect_list(
    concat('Table: {catalog}.{schema}.', table_name, ' | Columns: ',
      (
        SELECT concat_ws(', ', collect_list(concat(col_name, ' (', data_type, ')')))
        FROM {catalog}.information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = t.table_name
      )
    )
  ))
  FROM {catalog}.information_schema.tables t
  WHERE table_schema = '{schema}'
)
""")
print(f"  Created: {catalog}.{schema}.get_schema_info")

# --- Function 3: Table access functions ---
print("\n--- Creating table access functions ---")
for table_name in table_names:
    if table_name == 'product_docs':
        continue
    func_name = f"get_{table_name}"
    full_func = f"{catalog}.{schema}.{func_name}"
    spark.sql(f"DROP FUNCTION IF EXISTS {full_func}")
    spark.sql(f"CREATE OR REPLACE FUNCTION {full_func}() RETURNS TABLE LANGUAGE SQL COMMENT 'Returns rows from {table_name} table (limited to 100). Use for data analysis.' RETURN SELECT * FROM {catalog}.{schema}.{table_name} LIMIT 100")
    print(f"  Created: {full_func}()")

# --- Function 4: analyze_customer_tickets ---
print("\n--- Creating analyze_customer_tickets function ---")
spark.sql(f"DROP FUNCTION IF EXISTS {catalog}.{schema}.analyze_customer_tickets")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.analyze_customer_tickets(query STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Analyze customer service tickets using AI. Pass a natural language question about customer issues or service patterns.'
RETURN (
  SELECT ai_gen(concat(
    'You are a customer service analyst. Answer based on the customer service data below. Question: ',
    query,
    ' Customer service data: ',
    (
      SELECT concat_ws(' | ', collect_list(cast(Ticket_ID as string)))
      FROM {catalog}.{schema}.cust_service_data
      LIMIT 50
    )
  ))
)
""")
print(f"  Created: {catalog}.{schema}.analyze_customer_tickets")

# --- Summary ---
print("\n=== UC Functions Created ===")
funcs = spark.sql(f"SHOW USER FUNCTIONS IN {catalog}.{schema}").collect()
for f in funcs:
    print(f"  {f.function}")
print(f"\nTotal functions: {len(funcs)}")