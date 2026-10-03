"""ETL tools — extract, transform, and load utilities for the ETL Analyst agent."""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
import pandas as pd


class ETLTools:
    """Collection of ETL utility functions for the ETL Analyst agent."""

    def __init__(self):
        pass

    def extract_load(self, url: str, output_folder: str, format: str = "csv") -> str:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            df = pd.json_normalize(data)
            os.makedirs(output_folder, exist_ok=True)
            file_path = os.path.join(output_folder, f"extracted_data.{format}")
            if format.lower() == "csv":
                df.to_csv(file_path, index=False)
            elif format.lower() == "json":
                df.to_json(file_path, orient="records", indent=2)
            elif format.lower() == "parquet":
                df.to_parquet(file_path, index=False)
            else:
                return f"Unsupported format: {format}"
            return f"Data successfully extracted and saved to {file_path}"
        except Exception as e:
            return f"Error extracting data: {e}"

    def transform_load_context(self, file_path: str) -> str:
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension == ".csv":
                df = pd.read_csv(file_path)
            elif file_extension == ".json":
                df = pd.read_json(file_path)
            elif file_extension == ".parquet":
                df = pd.read_parquet(file_path)
            else:
                return f"Unsupported file format: {file_extension}"
            return str(df.head(3))
        except Exception as e:
            return f"Error reading file: {e}"

    def execute_code(self, code: str) -> str:
        try:
            exec(code)
            return "Code executed successfully"
        except Exception as e:
            return f"Failed to execute code: {e}"
