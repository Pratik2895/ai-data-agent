"""Compatibility entry point for the Databricks runtime."""
from .agent import _build_sql_analyst_graph

def build_agent():
    return _build_sql_analyst_graph()
