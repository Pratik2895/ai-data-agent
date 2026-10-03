# Databricks notebook source
# === Notebook 02: Create UC Functions ===
# Creates Unity Catalog SQL functions that serve as tools for the SQL Analyst agent.

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

print(f"Creating UC functions in {catalog}.{schema}")

tables = spark.sql(f"SHOW TABLES IN {catalog}.{schema}").collect()
table_names = [t.tableName for t in tables]
print(f"Available tables: {table_names}")

for table_name in table_names:
    func_name = f"get_{table_name}_data"
    full_func = f"{catalog}.{schema}.{func_name}"
    spark.sql(f"DROP FUNCTION IF EXISTS {full_func}")
    spark.sql(f"CREATE FUNCTION {full_func}() RETURNS TABLE RETURN SELECT * FROM {catalog}.{schema}.{table_name} LIMIT 100")
    print(f"  Created function: {full_func}()")

print("\n=== UC Functions Created ===")
funcs = spark.sql(f"SHOW USER FUNCTIONS IN {catalog}.{schema}").collect()
for f in funcs:
    print(f"  {f.function}")
