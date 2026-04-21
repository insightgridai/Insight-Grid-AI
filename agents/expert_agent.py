# agents/expert_agent.py
# Runs schema lookup + SQL execution.
# FIX: After tool loop ends, extracts the last clean text result
#      and stores it as a simple AIMessage so the reviewer only
#      receives a short, clean string — not the full tool call chain.
# Cost: max_tokens=400, max 3 tool calls, last 6 messages only.

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import (
    AnyMessage, SystemMessage, AIMessage, ToolMessage, HumanMessage
)
from langchain_openai import ChatOpenAI
from tools.get_schema  import get_schema_tool
from tools.execute_sql import get_execute_sql_tool


class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_expert_app(db_config: dict):
    db_type = db_config.get("db_type", "postgresql").lower()

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=400,
        max_retries=2,
        request_timeout=40,
    )

    get_schema  = get_schema_tool(db_config)
    execute_sql = get_execute_sql_tool(db_config)
    tools       = [get_schema, execute_sql]
    tool_llm    = llm.bind_tools(tools)

    if db_type == "snowflake":
        prompt = (
            "You are a Snowflake SQL expert.\n"
            "Step 1: call get_schema once.\n"
            "Step 2: write SQL with LIMIT 50.\n"
            "Step 3: call execute_sql once.\n"
            "Step 4: return ONLY the raw tabular result as plain text. "
            "No explanation. Just the data rows.\n"
            "Use UPPERCASE column/table names. Use CURRENT_DATE()."
        )
    else:
        prompt = (
            "You are a PostgreSQL expert.\n"
            "Step 1: call get_schema once.\n"
            "Step 2: write SQL with LIMIT 50.\n"
            "Step 3: call execute_sql once.\n"
            "Step 4: return ONLY the raw tabular result as plain text. "
            "No explanation. Just the data rows.\n"
            "Use lowercase names. Use CURRENT_DATE."
        )

    sm = [SystemMessage(content=prompt)]

    def expert(state: ExpertState):
        msgs = state["messages"]
        tool_call_count = sum(
            1 for m in msgs
            if hasattr(m, "tool_calls") and m.tool_calls
        )
        if tool_call_count >= 3:
            # Cap reached — extract best result from tool messages
            result_text = _extract_tool_result(msgs)
            return {"messages": [AIMessage(content=result_text)]}

        safe_msgs = msgs[-6:] if len(msgs) > 6 else msgs
        return {"messages": [tool_llm.invoke(sm + safe_msgs)]}

    graph = StateGraph(ExpertState)
    graph.add_node("expert", expert)
    graph.add_node("tools",  ToolNode(tools))
    graph.add_edge(START, "expert")
    graph.add_conditional_edges("expert", tools_condition)
    graph.add_edge("tools", "expert")
    return graph.compile()


def _extract_tool_result(msgs) -> str:
    """
    Pull the most useful text out of the message list.
    Priority: last ToolMessage content → last AIMessage text content.
    Returns a short clean string for the reviewer.
    """
    # Last ToolMessage (execute_sql result) is the gold
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            content = str(m.content or "").strip()
            if content and content != "None":
                # Truncate to 1500 chars so reviewer stays within token budget
                return content[:1500]

    # Fallback: last AI text message
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            content = str(getattr(m, "content", "") or "").strip()
            if content and not (hasattr(m, "tool_calls") and m.tool_calls):
                return content[:1500]

    return "No data returned."
