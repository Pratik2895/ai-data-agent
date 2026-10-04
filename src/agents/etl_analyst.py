"""Compatibility entry point for the Databricks runtime."""
from .agent import _build_etl_analyst_graph

def build_agent():
    return _build_etl_analyst_graph()
