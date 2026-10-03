# Databricks notebook source
# === Notebook 01: Load Data ===
# Loads CSV files from the Unity Catalog volume into Delta tables.
# Job parameters (widgets): catalog, schema, volume, llm_endpoint, agent_endpoint

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")

print(f"Catalog: {catalog}, Schema: {schema}, Volume: {volume}")

volume_path = f"/Volumes/{catalog}/{schema}/{volume}"

try:
    files = dbutils.fs.ls(volume_path)
    csv_files = [f.name for f in files if f.name.endswith('.csv')]
    print(f"Found CSV files: {csv_files}")
except Exception as e:
    print(f"Volume not accessible yet: {e}")
    csv_files = []

for csv_file in csv_files:
    table_name = csv_file.replace('.csv', '').replace('-', '_')
    full_table = f"{catalog}.{schema}.{table_name}"
    csv_path = f"{volume_path}/{csv_file}"
    print(f"\nLoading {csv_file} -> {full_table}")
    df = spark.read.csv(csv_path, header=True, inferSchema=True)
    df.write.format("delta").mode("overwrite").saveAsTable(full_table)
    row_count = spark.table(full_table).count()
    print(f"  Loaded {row_count} rows into {full_table}")

print("\n=== Data Loading Complete ===")
tables = spark.sql(f"SHOW TABLES IN {catalog}.{schema}").collect()
for t in tables:
    count = spark.table(f"{catalog}.{schema}.{t.tableName}").count()
    print(f"  {t.tableName}: {count} rows")
