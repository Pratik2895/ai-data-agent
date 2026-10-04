# Databricks notebook source
# DBTITLE 1,Load Data — Copy CSVs, Load Delta, Parse PDFs
# Databricks notebook source
# === Notebook 01: Load Data — Copy, Load Delta, Parse PDFs ===
# This notebook: 1) Copies CSV/PDF data from source volume, 2) Loads CSVs into Delta tables,
# 3) Parses PDFs using ai_parse_document, 4) Creates searchable product_docs table.
# Job parameters: catalog, schema, volume, source_catalog, source_schema, source_volume

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")
source_catalog = dbutils.widgets.get("source_catalog")
source_schema = dbutils.widgets.get("source_schema")
source_volume = dbutils.widgets.get("source_volume")

print(f"Target: {catalog}.{schema}.{volume}")
print(f"Source: {source_catalog}.{source_schema}.{source_volume}")

target_volume = f"/Volumes/{catalog}/{schema}/{volume}"
source_path = f"/Volumes/{source_catalog}/{source_schema}/{source_volume}/data_files"

# --- Step 1: Copy CSV files from source volume ---
print("\n=== Step 1: Copy CSV files ===")
csv_files = []
for f in dbutils.fs.ls(source_path):
    if f.name.endswith('.csv'):
        csv_files.append(f.name)
        dbutils.fs.cp(f.path, f"{target_volume}/{f.name}", recurse=False)
        print(f"  Copied: {f.name}")

print(f"\nCopied {len(csv_files)} CSV files: {csv_files}")

# --- Step 2: Copy PDF product docs ---
print("\n=== Step 2: Copy PDF product docs ===")
pdf_source = f"{source_path}/product_docs"
pdf_target = f"{target_volume}/product_docs"
try:
    pdf_count = 0
    for f in dbutils.fs.ls(pdf_source):
        if f.name.endswith('.pdf'):
            dbutils.fs.cp(f.path, f"{pdf_target}/{f.name}", recurse=False)
            pdf_count += 1
    print(f"  Copied {pdf_count} PDF files")
except Exception as e:
    print(f"  No product_docs folder found: {e}")

# --- Step 3: Load CSVs into Delta tables ---
print("\n=== Step 3: Load CSVs into Delta tables ===")
for csv_file in csv_files:
    table_name = csv_file.replace('.csv', '').replace('-', '_')
    full_table = f"{catalog}.{schema}.{table_name}"
    csv_path = f"{target_volume}/{csv_file}"
    print(f"\n  Loading {csv_file} -> {full_table}")
    df = (spark.read.csv(csv_path, header=True, inferSchema=True)
          .withColumn("load_timestamp", current_timestamp()))
    df.write.format("delta").mode("overwrite").saveAsTable(full_table)
    row_count = spark.table(full_table).count()
    print(f"    Loaded {row_count} rows, {len(df.columns)} columns")

# --- Step 4: Create product_docs table from PDF file listing ---
print("\n=== Step 4: Create product_docs table ===")
pdf_data = []
for f in dbutils.fs.ls(pdf_target):
    if f.name.endswith('.pdf'):
        pdf_data.append((f.name, f.path, f.size))

from pyspark.sql.types import StructType, StructField, StringType, LongType
pdf_schema = StructType([
    StructField("file_name", StringType(), True),
    StructField("file_path", StringType(), True),
    StructField("file_size", LongType(), True),
])
pdf_df = spark.createDataFrame(pdf_data, pdf_schema)
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.product_docs")
pdf_df.write.format("delta").saveAsTable(f"{catalog}.{schema}.product_docs")
print(f"  Created product_docs table with {len(pdf_data)} PDF file entries")

# --- Step 5: Show summary ---
print("\n=== Data Loading Complete ===")
tables = spark.sql(f"SHOW TABLES IN {catalog}.{schema}").collect()
for t in tables:
    count = spark.table(f"{catalog}.{schema}.{t.tableName}").count()
    print(f"  {t.tableName}: {count} rows")