# Databricks notebook source
# MAGIC %pip install pypdf==6.19.0

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from pyspark.sql.functions import current_timestamp
from pypdf import PdfReader
import re

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")
source_catalog = dbutils.widgets.get("source_catalog")
source_schema = dbutils.widgets.get("source_schema")
source_volume = dbutils.widgets.get("source_volume")
for name in [catalog, schema, volume, source_catalog, source_schema, source_volume]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid catalog/schema/volume identifier")
spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")
target = f"/Volumes/{catalog}/{schema}/{volume}"
source = f"/Volumes/{source_catalog}/{source_schema}/{source_volume}/data_files"
files = dbutils.fs.ls(source)
csvs = [f for f in files if f.name.lower().endswith('.csv')]
if not csvs:
    raise RuntimeError("Source volume has no CSV input files")
for f in csvs:
    table = f.name[:-4]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"Invalid table name: {table}")
    dbutils.fs.cp(f.path, f"{target}/{f.name}")
    frame = spark.read.csv(f"{target}/{f.name}", header=True, inferSchema=True)
    frame.withColumn("load_timestamp", current_timestamp()).write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{schema}.{table}")
# Extract actual PDF text; scanned PDFs require OCR before ingestion.
docs = []
if any(f.name.rstrip('/') == 'product_docs' for f in files):
    dbutils.fs.mkdirs(f"{target}/product_docs")
    for f in dbutils.fs.ls(f"{source}/product_docs"):
        if f.name.lower().endswith('.pdf'):
            path = f"{target}/product_docs/{f.name}"
            dbutils.fs.cp(f.path, path)
            text = [page.extract_text() or '' for page in PdfReader(path).pages]
            docs.append((f.name, path, f.size, text))
spark.createDataFrame(docs, "file_name string, file_path string, file_size long, text_content array<string>").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{schema}.product_docs")
print(f"Loaded {len(csvs)} tables and extracted {len(docs)} PDFs")
