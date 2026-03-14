from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from tools.get_schema import get_schema
from agents.expert_agent import get_expert_app


# ---------------- Analyst State ----------------

class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------- Analyst App ----------------

def get_analyst_app():
    """
    Creates and returns the Analyst Agent workflow.
    """

    llm = ChatOpenAI(model="gpt-5-nano")

    analyst_llm = llm.bind_tools([get_schema])

    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. First inspect the database schema. "
                "Then forward the analytical request to the expert agent "
                "to generate SQL queries and retrieve results."
            )
        )
    ]

    # ---------------- Analyst Node ----------------

    def analyst(state: AnalystState):

        response = analyst_llm.invoke(
            analyst_system_message + state["messages"]
        )

        return {"messages": [response]}


    # ---------------- Expert Node ----------------

    def call_expert(state: AnalystState):

        expert_app = get_expert_app()

        result = expert_app.invoke({
            "messages": state["messages"]
        })

        return result


    # ---------------- Graph ----------------

    analyst_graph = StateGraph(AnalystState)

    analyst_graph.add_node("analyst", analyst)

    analyst_graph.add_node(
        "tools",
        ToolNode([get_schema])
    )

    analyst_graph.add_node("expert", call_expert)

    analyst_graph.add_edge(START, "analyst")

    analyst_graph.add_conditional_edges(
        "analyst",
        tools_condition
    )

    analyst_graph.add_edge("tools", "analyst")

    # After schema understanding → send to expert
    analyst_graph.add_edge("analyst", "expert")

    return analyst_graph.compile()