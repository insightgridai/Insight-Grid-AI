# =============================================================
# agents/expert_agent.py
# Token-optimised SQL Expert — PostgreSQL + Snowflake
#
# OPTIMISATIONS vs previous version:
# - max_tokens=600 on LLM → hard cap on output tokens
# - Short, precise system prompt → fewer input tokens
# - max_iterations=4 → stops infinite tool-call loops
# - request_timeout=30 → fail fast instead of hanging
# - Always LIMIT 100 on Snowflake to avoid huge result sets
# - Schema prompt tells model the table name upfront when known
# =============================================================

from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools.get_schema  import get_schema_tool
from tools.execute_sql import get_execute_sql_tool


class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_expert_app(db_config: dict):

    db_type = db_config.get("db_type", "postgresql").lower()

    # Tight token budget — gpt-4o-mini is fast and cheap
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=600,          # hard output cap
        request_timeout=45,      # fail fast, don't hang
        max_retries=1,           # one retry on rate limit
    )

    get_schema  = get_schema_tool(db_config)
    execute_sql = get_execute_sql_tool(db_config)
    tools       = [get_schema, execute_sql]
    tool_llm    = llm.bind_tools(tools)

    # ── System prompt — kept SHORT to save input tokens ──
    if db_type == "snowflake":
        prompt = """You are a Snowflake SQL expert.
Steps: 1) call get_schema 2) write SQL 3) call execute_sql 4) return result only.
Rules:
- UPPERCASE column/table names
- Always add LIMIT 100
- Use CURRENT_DATE() for today
- Return ONLY the raw query result. No explanation."""
    else:
        prompt = """You are a PostgreSQL expert.
Steps: 1) call get_schema 2) write SQL 3) call execute_sql 4) return result only.
Rules:
- lowercase column/table names
- Always add LIMIT 100
- Use CURRENT_DATE for today
- Return ONLY the raw query result. No explanation."""

    sm = [SystemMessage(content=prompt)]

    # Track iterations to prevent infinite loops
    def expert(state: ExpertState):
        msgs = state["messages"]
        # Count how many times expert has already responded
        # If > 4 tool calls already, force stop
        tool_calls_made = sum(
            1 for m in msgs
            if hasattr(m, "tool_calls") and m.tool_calls
        )
        if tool_calls_made >= 4:
            # Return a stop message to break the loop
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(
                content="Query complete. See tool results above."
            )]}
        response = tool_llm.invoke(sm + msgs)
        return {"messages": [response]}

    graph = StateGraph(ExpertState)
    graph.add_node("expert", expert)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "expert")
    graph.add_conditional_edges("expert", tools_condition)
    graph.add_edge("tools", "expert")

    return graph.compile()
