"""Compatibility entry point for the Databricks runtime."""
from .agent import _build_data_agent_graph

def build_agent():
    return _build_data_agent_graph()
