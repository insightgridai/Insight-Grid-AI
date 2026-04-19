from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools.get_schema import get_schema
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

    execute_sql = get_execute_sql_tool(db_config)

    tools = [
        get_schema,
        execute_sql
    ]

    tool_llm = llm.bind_tools(tools)

    system_prompt = """
You are a senior SQL expert for PostgreSQL.

RULES:
1. ALWAYS inspect schema first using get_schema.
2. Then generate SQL.
3. Then execute SQL using execute_sql tool.
4. Return ONLY tool result.
5. No explanations.

OUTPUT FORMAT:

{
  "columns": [],
  "data": []
}

Use PostgreSQL syntax.
Use LIMIT when top requested.
Use current/latest year dynamically if asked.
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
