from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AnyMessage, SystemMessage, AIMessage
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
            "1. Call get_schema once.\n"
            "2. Write SQL with LIMIT 50 always.\n"
            "3. Call execute_sql once.\n"
            "4. Return raw result only. No explanation.\n"
            "Use UPPERCASE column names. Use CURRENT_DATE()."
        )
    else:
        prompt = (
            "You are a PostgreSQL expert.\n"
            "1. Call get_schema once.\n"
            "2. Write SQL with LIMIT 50 always.\n"
            "3. Call execute_sql once.\n"
            "4. Return raw result only. No explanation.\n"
            "Use lowercase names. Use CURRENT_DATE."
        )

    sm = [SystemMessage(content=prompt)]

    def expert(state: ExpertState):
        msgs = state["messages"]
        # Hard stop after 3 tool calls to prevent token explosion
        tool_calls_made = sum(
            1 for m in msgs
            if hasattr(m, "tool_calls") and getattr(m, "tool_calls", None)
        )
        if tool_calls_made >= 3:
            return {"messages": [AIMessage(content="Done. See results above.")]}
        # Only send last 4 messages to limit input tokens
        return {"messages": [tool_llm.invoke(sm + msgs[-4:])]}

    graph = StateGraph(ExpertState)
    graph.add_node("expert", expert)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "expert")
    graph.add_conditional_edges("expert", tools_condition)
    graph.add_edge("tools", "expert")
    return graph.compile()
