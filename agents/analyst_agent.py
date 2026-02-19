from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from tools.get_schema import get_schema


# ---------------- Analyst Agent ----------------

class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    # 🔥 Limit output tokens
    llm = ChatOpenAI(
        model="gpt-5-nano",
        temperature=0,
        max_tokens=150
    )

    analyst_llm = llm.bind_tools([get_schema])

    # 🔥 Shortened system prompt
    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. "
                "Always call get_schema first. "
                "Then return schema information clearly "
                "and ask exactly 2 insightful questions."
            )
        )
    ]

    def analyst(state: AnalystState) -> AnalystState:
        # 🔥 Limit message history to reduce tokens
        limited_messages = state["messages"][-4:]

        response = analyst_llm.invoke(
            analyst_system_message + limited_messages
        )

        return {"messages": [response]}

    analyst_graph = StateGraph(AnalystState)

    analyst_graph.add_node("analyst", analyst)
    analyst_graph.add_node("tools", ToolNode([get_schema]))

    analyst_graph.add_edge(START, "analyst")
    analyst_graph.add_conditional_edges("analyst", tools_condition)

    # 🔥 After tool call, go to END (no loop)
    analyst_graph.add_edge("tools", END)

    return analyst_graph.compile()
