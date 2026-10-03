"""SQL Analyst Agent — Stateful LangGraph for SQL query generation and execution.

Graph flow:
  START -> curate_question -> prompt_query_context -> generate_sql -> is_safe_sql
    -> [yes] execute_sql -> represent_final_answer -> END
    -> [no]  cancel_sql -> END
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage

from models.schema import AgentSchema, JudgeSchema
from utils.llm_picker import pick_llm
from utils.database import DatabaseUtil


def curate_question(state: AgentSchema) -> AgentSchema:
    user_question = state.user_question
    llm = pick_llm("low")
    response = llm.invoke(f"Curate the following question so that it is clear and well-structured: {user_question}")
    state.curated_question = response.content
    state.messages = state.messages + [HumanMessage(content=response.content)]
    return state


def prompt_query_context(state: AgentSchema) -> AgentSchema:
    curated_question = state.curated_question
    db_config = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "database": os.environ.get("DB_NAME", "postgres"),
    }
    db_util = DatabaseUtil(db_config)
    schema_info = db_util.schema_details(os.environ.get("DB_SCHEMA", "public"))
    db_util.close()

    prompt = f"""You are an SQL analyst agent. Your task is to convert the user's natural language
question into a valid SQL query.

User question: {curated_question}

Database schema details:
{schema_info}

Rules:
- Generate ONLY the SQL query without any explanation.
- Unless the user explicitly asks for specific number of rows, always limit output to 10 rows.
- Use the exact table and column names from the schema above.

SQL query:"""
    state.prompt_query_context = prompt
    return state


def generate_sql(state: AgentSchema) -> AgentSchema:
    llm = pick_llm("medium")
    response = llm.invoke(state.prompt_query_context)
    state.generated_sql_query = response.content.strip()
    return state


def is_safe_sql(state: AgentSchema) -> AgentSchema:
    llm = pick_llm("low")
    llm_judge = llm.with_structured_output(JudgeSchema)
    judge_prompt = f"""You are a SQL judge for data security. Your task is to determine whether
the SQL query is safe or not. The SQL query should only be used for data retrieval
and should not modify the database in any way.

The SQL query should not contain any SQL commands that can modify the database
such as INSERT, UPDATE, DELETE, DROP, TRUNCATE, or any other commands that can
change the structure or contents.

If the query is safe, respond with 'yes'. Otherwise respond with 'no'.
Additionally, provide comments explaining your decision.

Here is the SQL query to validate:
{state.generated_sql_query}"""
    response = llm_judge.invoke(judge_prompt)
    result = response.model_dump()
    state.is_safe = result.get("answer", "no")
    state.comments = result.get("comments", "")
    return state


def execute_sql(state: AgentSchema) -> AgentSchema:
    db_config = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "database": os.environ.get("DB_NAME", "postgres"),
    }
    db_util = DatabaseUtil(db_config)
    result = db_util.execute_query(state.generated_sql_query)
    db_util.close()
    state.sql_query_execution_result = str(result)
    return state


def cancel_sql(state: AgentSchema) -> AgentSchema:
    state.final_answer = f"The generated SQL query was deemed unsafe to execute. Reason: {state.comments}"
    state.messages = state.messages + [AIMessage(content=state.final_answer)]
    return state


def represent_final_answer(state: AgentSchema) -> AgentSchema:
    llm = pick_llm("low")
    prompt = f"""You are an SQL analyst. Provide the final answer based on the execution result.
The final answer should be concise, clear, and address the user's question.
Avoid SQL code in the answer.

User's original question: {state.curated_question}

Execution result:
{state.sql_query_execution_result}"""
    response = llm.invoke(prompt)
    state.final_answer = response.content
    state.messages = state.messages + [AIMessage(content=state.final_answer)]
    return state


def is_safe_sql_edge(state: AgentSchema) -> str:
    if state.is_safe.lower() == "yes":
        return "execute_sql"
    else:
        return "cancel_sql"


sql_analyst_graph = StateGraph(AgentSchema)
sql_analyst_graph.add_node("curate_question", curate_question)
sql_analyst_graph.add_node("prompt_query_context", prompt_query_context)
sql_analyst_graph.add_node("generate_sql", generate_sql)
sql_analyst_graph.add_node("is_safe_sql", is_safe_sql)
sql_analyst_graph.add_node("execute_sql", execute_sql)
sql_analyst_graph.add_node("cancel_sql", cancel_sql)
sql_analyst_graph.add_node("represent_final_answer", represent_final_answer)

sql_analyst_graph.add_edge(START, "curate_question")
sql_analyst_graph.add_edge("curate_question", "prompt_query_context")
sql_analyst_graph.add_edge("prompt_query_context", "generate_sql")
sql_analyst_graph.add_edge("generate_sql", "is_safe_sql")
sql_analyst_graph.add_conditional_edges("is_safe_sql", is_safe_sql_edge,
    {"execute_sql": "execute_sql", "cancel_sql": "cancel_sql"})
sql_analyst_graph.add_edge("execute_sql", "represent_final_answer")
sql_analyst_graph.add_edge("cancel_sql", END)
sql_analyst_graph.add_edge("represent_final_answer", END)

sql_analyst = sql_analyst_graph.compile()
