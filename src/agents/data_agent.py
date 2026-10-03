"""Data Agent — Parent router that orchestrates SQL Analyst and ETL Analyst.

Graph flow:
  START -> router_node
    -> [SQL] sql_node -> END
    -> [ETL] etl_node -> END
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage

from models.schema import DataAgentSchema, RouterSchema, AgentSchema
from utils.llm_picker import pick_llm
from agents.sql_analyst import sql_analyst
from agents.etl_analyst import etl_analyst

llm = pick_llm("low")
llm_router = llm.with_structured_output(RouterSchema)


def router_node(state: DataAgentSchema) -> DataAgentSchema:
    """Router node — classifies the user query as SQL or ETL."""
    message = state.messages[-1].content
    router_prompt = f"""You are a router for a data agent. Your task is to determine whether
the user's question is related to SQL data retrieval or ETL operations.

- Answer 'SQL' if the question is about querying, analyzing, or retrieving data from a database.
- Answer 'ETL' if the question is about extracting, transforming, loading, or fetching data
  from external sources like APIs, files, or data pipelines.

User question: {message}"""
    response = llm_router.invoke(router_prompt)
    route_dict = response.model_dump()
    state.route_response = route_dict.get("answer", "SQL")
    return state


def sql_node(state: DataAgentSchema) -> DataAgentSchema:
    """SQL node — invokes the SQL Analyst sub-agent."""
    message = state.messages[-1].content
    sql_input = AgentSchema(messages=[], user_question=message)
    response = sql_analyst.invoke(sql_input)
    final_answer = response.final_answer if hasattr(response, 'final_answer') else str(response)
    state.final_answer = final_answer
    state.messages = state.messages + [AIMessage(content=final_answer)]
    return state


def etl_node(state: DataAgentSchema) -> DataAgentSchema:
    """ETL node — invokes the ETL Analyst sub-agent."""
    message = state.messages[-1].content
    etl_input = {"messages": [HumanMessage(content=message)]}
    response = etl_analyst.invoke(etl_input)
    if hasattr(response, 'messages') and response.messages:
        final_answer = response.messages[-1].content
    else:
        final_answer = str(response)
    state.final_answer = final_answer
    state.messages = state.messages + [AIMessage(content=final_answer)]
    return state


def router_edge(state: DataAgentSchema) -> str:
    if state.route_response.upper() == "ETL":
        return "etl_node"
    else:
        return "sql_node"


data_agent_graph = StateGraph(DataAgentSchema)
data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("sql_node", sql_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_edge(START, "router_node")
data_agent_graph.add_conditional_edges("router_node", router_edge,
    {"sql_node": "sql_node", "etl_node": "etl_node"})
data_agent_graph.add_edge("sql_node", END)
data_agent_graph.add_edge("etl_node", END)

data_agent = data_agent_graph.compile()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_query = "What are the different types of payment methods we have?"
    print(f"Test query: {test_query}")
    response = data_agent.invoke({"messages": [HumanMessage(content=test_query)]})
    print(f"\nFinal answer: {response.final_answer}")
    print(f"\nAll messages: {response.messages}")
