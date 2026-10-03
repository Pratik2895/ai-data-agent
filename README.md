# AI Data Agent

An **agentic AI solution** built on **Databricks** that automates the work of a junior data professional.

The system uses a **multi-agent architecture** with a parent router that classifies user queries and routes them to the appropriate sub-agent:

- **SQL Analyst** (Stateful LangGraph): Curates questions, adds database context, generates SQL, validates safety with AI-as-judge, executes, and presents results.
- **ETL Analyst** (React/Tool-Calling): Extracts data from APIs, transforms it with generated pandas code, and loads it to the destination.

All orchestrated by a single **Databricks Asset Bundle (DAB)**.

---

## Architecture

```
User Query
    |
+---------------+
|  Router Node  |  (LLM + RouterSchema -> 'SQL' or 'ETL')
+---------------+
    |                    |
    v                    v
+---------------+    +---------------+
| SQL Analyst   |    | ETL Analyst   |
| (Stateful)    |    | (React)       |
+---------------+    +---------------+
    |                    |
    v                    v
+---------------+
| Final Answer  |
+---------------+
```

### SQL Analyst (Stateful LangGraph)

```
START -> curate_question -> prompt_query_context -> generate_sql -> is_safe_sql
  -> [yes] execute_sql -> represent_final_answer -> END
  -> [no]  cancel_sql -> END
```

### ETL Analyst (React/Tool-Calling)

```
START -> llm_node <-> tool_node (loop)
  -> [has tool calls] -> tool_node -> llm_node (repeat)
  -> [no tool calls]  -> END
```

---

## Project Structure

```
ai-data-agent/
+-- databricks.yml                  # Bundle configuration
+-- resources/
|   +-- setup.job.yml               # Setup job DAG
|   +-- app.yml                     # Databricks App resource
+-- src/
|   +-- agents/
|   |   +-- sql_analyst.py           # SQL Analyst (stateful LangGraph)
|   |   +-- etl_analyst.py           # ETL Analyst (react LangGraph)
|   |   +-- data_agent.py            # Parent router agent
|   +-- models/
|   |   +-- schema.py                # Pydantic state schemas
|   +-- utils/
|   |   +-- llm_picker.py            # LLM model picker (low/medium/high/claude)
|   |   +-- database.py              # Database utility (schema introspection + query execution)
|   |   +-- etl_tools.py             # ETL tools (extract, transform, execute code)
|   +-- app/
|       +-- app.py                   # Gradio chat UI
|       +-- app.yaml                 # App runtime config
|       +-- requirements.txt         # Python dependencies
+-- .gitignore
+-- README.md
```

---

## Quick Start

### Deploy

```bash
git clone https://github.com/Pratik2895/ai-data-agent.git
cd ai-data-agent
databricks bundle deploy
databricks bundle run setup_ai_data_agent
databricks apps deploy ai-data-agent-app --auto-approve
```

### Run Locally

```bash
uv add langchain langgraph langchain-openai langchain-anthropic pydantic psycopg2-binary requests pandas python-dotenv
export OPENAI_API_KEY=your-key
export ANTHROPIC_API_KEY=your-key
python src/agents/data_agent.py
```

---

## AI Routing Decision (ai_decide)

| Query | Route | Agent |
|-------|-------|-------|
| "What are the different payment methods?" | SQL | SQL Analyst (stateful) |
| "Extract data from this API and save as CSV" | ETL | ETL Analyst (react) |

---

## Key Concepts

- **Stateful Orchestration**: SQL Analyst uses Pydantic state schema carried through every node
- **React Architecture**: ETL Analyst uses a reasoning+acting loop with tool calling
- **AI-as-Judge**: SQL safety validated by LLM with structured output (JudgeSchema)
- **LLM Cost Optimization**: Different LLM tiers for different tasks (low/medium/high/claude)
- **Context Engineering**: Database schema, column types, and sample data injected into prompts

---

## License

MIT
