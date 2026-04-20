# =============================================================
# agents/expert_agent.py
# SQL Expert — supports PostgreSQL and Snowflake
# =============================================================

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
def get_expert_app(db_config: dict):

    # gpt-4o-mini: good balance of cost + SQL quality
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    get_schema  = get_schema_tool(db_config)
    execute_sql = get_execute_sql_tool(db_config)

    tools    = [get_schema, execute_sql]
    tool_llm = llm.bind_tools(tools)

    db_type = db_config.get("db_type", "postgresql").lower()

    if db_type == "snowflake":
        sql_dialect = "Snowflake SQL"
        extra_rules = """
- Use LIMIT for large tables.
- Use TO_DATE / DATEADD / DATE_TRUNC for date logic.
- Schema is usually PUBLIC unless specified.
- Use CURRENT_DATE() for today's date.
- Column names are UPPERCASE in Snowflake by default.
"""
    else:
        sql_dialect = "PostgreSQL"
        extra_rules = """
- Use LIMIT for large results.
- Use DATE_TRUNC / EXTRACT for date logic.
- Use NOW() or CURRENT_DATE for today's date.
- Use lowercase table/column names.
"""

    system_prompt = f"""
You are a senior {sql_dialect} expert embedded in a multi-agent analytics system.

RULES:
1. Always call get_schema first to inspect available tables and columns.
2. Write correct, optimised {sql_dialect} based on the schema.
3. Execute the SQL with execute_sql.
4. Return ONLY the raw tool result — no commentary, no markdown.
5. Never guess column names; always verify via schema first.
{extra_rules}
"""

    system_message = [SystemMessage(content=system_prompt)]

    def expert(state: ExpertState):
        response = tool_llm.invoke(system_message + state["messages"])
        return {"messages": [response]}

    graph = StateGraph(ExpertState)
    graph.add_node("expert", expert)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "expert")
    graph.add_conditional_edges("expert", tools_condition)
    graph.add_edge("tools", "expert")

    return graph.compile()
