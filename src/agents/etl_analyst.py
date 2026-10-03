"""ETL Analyst Agent — React/Tool-calling LangGraph for ETL operations.

Graph flow (react loop):
  START -> llm_node <-> tool_node
    -> [has tool calls] -> tool_node -> llm_node (loop)
    -> [no tool calls]  -> END
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.tools import tool

from models.schema import ETLAgentSchema
from utils.llm_picker import pick_llm
from utils.etl_tools import ETLTools

etl_tools_instance = ETLTools()


@tool
def extract_load_tool(url: str, output_folder: str, format: str = "csv") -> str:
    """Extract data from an API URL and load it to the output folder."""
    return etl_tools_instance.extract_load(url, output_folder, format)


@tool
def transform_load_tool(input_file_path: str, output_folder: str, output_format: str = "csv", user_question: str = "") -> str:
    """Transform the data file by generating and executing pandas code."""
    top_rows = etl_tools_instance.transform_load_context(input_file_path)
    llm = pick_llm("claude")
    prompt = f"""You are a Python data analyst. Create pandas code to transform the data
stored in the file: {input_file_path}

The user wants: {user_question}

Here are the top 3 rows of the data for context:
{top_rows}

Output format: {output_format}
Output folder: {output_folder}

Rules:
- Read the file with pandas.
- Apply the requested transformation.
- Save the result to {output_folder}/transformed_data.{output_format}
- Only output the Python code, no explanation.
"""
    response = llm.invoke(prompt)
    pandas_code = response.content.strip()
    if pandas_code.startswith("```python"):
        pandas_code = pandas_code[len("```python"):]
    if pandas_code.startswith("```"):
        pandas_code = pandas_code[3:]
    if pandas_code.endswith("```"):
        pandas_code = pandas_code[:-3]
    pandas_code = pandas_code.strip()
    result = etl_tools_instance.execute_code(pandas_code)
    return f"Data transformed and saved at {output_folder}.\nPandas code executed:\n{pandas_code}\nExecution result: {result}"


tools = [extract_load_tool, transform_load_tool]
tools_by_name = {tool.name: tool for tool in tools}

llm = pick_llm("claude")
llm_bind = llm.bind_tools(tools)


def llm_node(state: ETLAgentSchema) -> ETLAgentSchema:
    messages = state.messages
    system_prompt = (
        "You are a Python data analyst ETL agent. You have access to the following tools:\n"
        "1. extract_load_tool: Extract data from an API URL and save it to a folder.\n"
        "2. transform_load_tool: Transform a data file by generating and executing pandas code.\n"
        "\nWhen the user asks to extract, transform, or load data, use the appropriate tool.\n"
        "If the task is complete or no tool is needed, provide a direct answer."
    )
    all_messages = [HumanMessage(content=system_prompt)] + messages
    final_answer = llm_bind.invoke(all_messages)
    state.messages = state.messages + [final_answer]
    return state


def tool_node(state: ETLAgentSchema) -> ETLAgentSchema:
    tool_calls = state.messages[-1].tool_calls
    tool_results = []
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        tool_results.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
    state.messages = state.messages + tool_results
    return state


def is_tool_call(state: ETLAgentSchema) -> str:
    if hasattr(state.messages[-1], "tool_calls") and state.messages[-1].tool_calls:
        return "tool_node"
    else:
        return END


etl_analyst_graph = StateGraph(ETLAgentSchema)
etl_analyst_graph.add_node("llm_node", llm_node)
etl_analyst_graph.add_node("tool_node", tool_node)
etl_analyst_graph.add_edge(START, "llm_node")
etl_analyst_graph.add_conditional_edges("llm_node", is_tool_call,
    {"tool_node": "tool_node", END: END})
etl_analyst_graph.add_edge("tool_node", "llm_node")

etl_analyst = etl_analyst_graph.compile()
