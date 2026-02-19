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

    llm = ChatOpenAI(
        model="gpt-5-nano",
        temperature=0,
        max_tokens=120
    )

    analyst_llm = llm.bind_tools([get_schema])

    analyst_system_message = [
        SystemMessage(
            content=(
                "Call get_schema tool first."
            )
        )
    ]

    def analyst(state: AnalystState):
        limited_messages = state["messages"][-3:]
        response = analyst_llm.invoke(
            analyst_system_message + limited_messages
        )
        return {"messages": [response]}

    # Tool node
    tool_node = ToolNode([get_schema])

    def tools(state: AnalystState):
        result = tool_node.invoke(state)
        return {"messages": result["messages"]}

    # 🔥 Final visible response node
    def final_response(state: AnalystState):
        limited_messages = state["messages"][-3:]

        response = llm.invoke([
            SystemMessage(
                content=(
                    "Using the schema result, give:\n"
                    "1 line schema summary.\n"
                    "Then ask exactly 2 insightful questions.\n"
                    "Keep answer short."
                )
            )
        ] + limited_messages)

        return {"messages": [response]}

    # Build graph
    analyst_graph = StateGraph(AnalystState)

    analyst_graph.add_node("analyst", analyst)
    analyst_graph.add_node("tools", tools)
    analyst_graph.add_node("final", final_response)

    analyst_graph.add_edge(START, "analyst")
    analyst_graph.add_conditional_edges("analyst", tools_condition)
    analyst_graph.add_edge("tools", "final")
    analyst_graph.add_edge("final", END)

    return analyst_graph.compile()
