from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools.get_schema import get_schema_tool
from tools.execute_sql import get_execute_sql_tool


# ---------------------------------------------------
# STATE
# ---------------------------------------------------
class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------
# MAIN APP
# ---------------------------------------------------
def get_expert_app(db_config):

    llm = ChatOpenAI(model="gpt-5-nano")

    get_schema = get_schema_tool(db_config)
    execute_sql = get_execute_sql_tool(db_config)

    tools = [
        get_schema,
        execute_sql
    ]

    tool_llm = llm.bind_tools(tools)

    system_prompt = """
You are a PostgreSQL senior SQL expert.

RULES:
1. Always inspect schema first.
2. Then generate correct SQL.
3. Then execute SQL.
4. Return tool result only.
5. No explanations.

Use PostgreSQL syntax.
Use LIMIT when needed.
Use latest year dynamically if requested.
"""

    system_message = [
        SystemMessage(content=system_prompt)
    ]


    def expert(state: ExpertState):

        response = tool_llm.invoke(
            system_message + state["messages"]
        )

        return {
            "messages": [response]
        }


    graph = StateGraph(ExpertState)

    graph.add_node("expert", expert)

    graph.add_node(
        "tools",
        ToolNode(tools)
    )

    graph.add_edge(START, "expert")

    graph.add_conditional_edges(
        "expert",
        tools_condition
    )

    graph.add_edge("tools", "expert")

    return graph.compile()
