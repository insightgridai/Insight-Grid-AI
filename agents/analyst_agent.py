from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, create_react_agent, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from tools.execute_sql import execute_sql
from tools.get_schema import get_schema


# ---------------- Analyst Agent ----------------

class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():
    """
    Creates and returns the Analyst Agent workflow.
    """

    llm = ChatOpenAI(model="gpt-4o-mini")

    analyst_llm = llm.bind_tools([get_schema])

    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. Start by understanding the database schema "
                "using tools. Then ask at least 10 insightful questions in a single "
                "response that will help in creating a comprehensive report."
            )
        )
    ]

    def analyst(state: AnalystState) -> AnalystState:
        response = analyst_llm.invoke(analyst_system_message + state["messages"])
        return {"messages": [response]}

    analyst_graph = StateGraph(AnalystState)

    analyst_graph.add_node("analyst", analyst)
    analyst_graph.add_node("tools", ToolNode([get_schema]))

    analyst_graph.add_edge(START, "analyst")
    analyst_graph.add_conditional_edges("analyst", tools_condition)
    analyst_graph.add_edge("tools", "analyst")

    return analyst_graph.compile()
