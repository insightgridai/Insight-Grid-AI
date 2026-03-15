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

llm = ChatOpenAI(model="gpt-4o-mini")


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

Your job is to answer analytical questions using the database.

Steps:
1. Understand the question.
2. Use the schema tool to inspect database structure if needed.
3. Generate SQL queries using the execute_sql tool.
4. Return the results clearly.

Do NOT generate PDF reports.
Just return the analysis result.
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