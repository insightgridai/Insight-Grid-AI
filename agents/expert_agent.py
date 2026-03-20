from typing import TypedDict, Annotated

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_openai import ChatOpenAI

# SQL tools
from tools.get_schema import get_schema
from tools.execute_sql import execute_sql


# ---------------- LLM ----------------

llm = ChatOpenAI(model="gpt-5-nano")


# ---------------- LLM WITH TOOLS ----------------

expert_llm = llm.bind_tools([
    get_schema,
    execute_sql
])


# ---------------- SYSTEM MESSAGE ----------------

expert_system_message = [
    SystemMessage(
        content="""
You are a senior data expert.

Your job is to answer analytical questions using SQL tools.

STRICT RULES (VERY IMPORTANT):

1. Always use tools (get_schema, execute_sql).
2. ALWAYS return output ONLY in JSON format.
3. DO NOT add explanations, summaries, or text.
4. DO NOT modify the tool output.
5. DO NOT wrap JSON inside text.
6. RETURN ONLY the JSON response from execute_sql.

Expected format:

{
  "columns": ["col1", "col2"],
  "data": [
    [value1, value2],
    [value1, value2]
  ]
}

If query is not SELECT:
Return JSON with status.

DO NOT say anything else.
"""
    )
]


# ---------------- STATE ----------------

class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------- EXPERT NODE ----------------

def expert(state: ExpertState):

    response = expert_llm.invoke(
        expert_system_message + state["messages"]
    )

    return {"messages": [response]}


# ---------------- GRAPH ----------------

expert_graph = StateGraph(ExpertState)

expert_graph.add_node("expert", expert)

expert_graph.add_node(
    "tools",
    ToolNode([
        get_schema,
        execute_sql
    ])
)

expert_graph.add_edge(START, "expert")

expert_graph.add_conditional_edges(
    "expert",
    tools_condition
)

expert_graph.add_edge("tools", "expert")

expert_app = expert_graph.compile()


# ---------------- EXPORT ----------------

def get_expert_app():
    return expert_app