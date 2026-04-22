from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AnyMessage, SystemMessage, AIMessage, ToolMessage, HumanMessage
from langchain_openai import ChatOpenAI
from tools.get_schema  import get_schema_tool
from tools.execute_sql import get_execute_sql_tool


class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _extract_result(msgs) -> str:
    """Get best plain-text data result — ToolMessage first, then plain AIMessage."""
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            c = str(m.content or "").strip()
            if c and c.lower() not in ("none", ""):
                return c[:3000]
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = str(getattr(m, "content", "") or "").strip()
            has_tools = bool(getattr(m, "tool_calls", None))
            if c and not has_tools:
                return c[:3000]
    return "No data returned."


def _safe_messages(msgs):
    """
    FIX: Ensure tool messages always follow an AI message with tool_calls.
    Remove any orphaned ToolMessages that don't have a matching tool_call
    before them — this prevents the 'tool must follow tool_calls' API error.
    """
    safe = []
    for m in msgs:
        if isinstance(m, ToolMessage):
            # Only keep ToolMessage if last message in safe has tool_calls
            if safe and isinstance(safe[-1], AIMessage) and getattr(safe[-1], "tool_calls", None):
                safe.append(m)
            # Otherwise skip the orphaned ToolMessage
        else:
            safe.append(m)
    return safe


def get_expert_app(db_config: dict):
    db_type = db_config.get("db_type", "postgresql").lower()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=400,
                     max_retries=2, request_timeout=40)

    get_schema  = get_schema_tool(db_config)
    execute_sql = get_execute_sql_tool(db_config)
    tools       = [get_schema, execute_sql]
    tool_llm    = llm.bind_tools(tools)

    if db_type == "snowflake":
        prompt = (
            "You are a Snowflake SQL expert.\n"
            "1. Call get_schema once.\n"
            "2. Write SQL with LIMIT 50.\n"
            "3. Call execute_sql once.\n"
            "4. Return ONLY the raw result. No explanation.\n"
            "Use UPPERCASE names. CURRENT_DATE().\n"
            "For metadata/schema/structure queries: query INFORMATION_SCHEMA.COLUMNS "
            "and INFORMATION_SCHEMA.TABLE_CONSTRAINTS to compare columns, "
            "data types, primary keys, and foreign keys between tables."
        )
    else:
        prompt = (
            "You are a PostgreSQL expert.\n"
            "1. Call get_schema once.\n"
            "2. Write SQL with LIMIT 50.\n"
            "3. Call execute_sql once.\n"
            "4. Return ONLY the raw result. No explanation.\n"
            "Use lowercase names. CURRENT_DATE.\n"
            "For metadata/schema/structure/comparison queries: query "
            "information_schema.columns for column names, data types, "
            "and nullable; query information_schema.table_constraints and "
            "information_schema.key_column_usage for primary keys and foreign keys. "
            "Compare the two tables side by side. Do NOT query business data tables."
        )

    sm = [SystemMessage(content=prompt)]

    def expert(state: ExpertState):
        msgs = state["messages"]
        tool_calls = sum(1 for m in msgs if getattr(m, "tool_calls", None))
        if tool_calls >= 3:
            return {"messages": [AIMessage(content=_extract_result(msgs))]}
        # KEY FIX: sanitise message order before sending to OpenAI
        safe = _safe_messages(msgs[-6:] if len(msgs) > 6 else msgs)
        return {"messages": [tool_llm.invoke(sm + safe)]}

    graph = StateGraph(ExpertState)
    graph.add_node("expert", expert)
    graph.add_node("tools",  ToolNode(tools))
    graph.add_edge(START, "expert")
    graph.add_conditional_edges("expert", tools_condition)
    graph.add_edge("tools", "expert")
    return graph.compile()
