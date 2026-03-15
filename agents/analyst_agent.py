from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agents.expert_agent import get_expert_app
from agents.reviewer_agent import get_reviewer_app


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    llm = ChatOpenAI(model="gpt-4o-mini")

    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. Understand the user's question "
                "and send the request to the expert agent to query the database. "
                "After receiving the results, send them to the reviewer agent "
                "to generate a summarized report."
            )
        )
    ]

    # ---------------- Analyst Node ----------------

    def analyst(state: AnalystState):

        response = llm.invoke(
            analyst_system_message + state["messages"]
        )

        return {"messages": [response]}

    # ---------------- Expert Agent Call ----------------

    def call_expert(state: AnalystState):

        expert_app = get_expert_app()

        result = expert_app.invoke({
            "messages": state["messages"]
        })

        return result

    # ---------------- Reviewer Agent Call ----------------

    def call_reviewer(state: AnalystState):

        reviewer_app = get_reviewer_app()

        result = reviewer_app.invoke({
            "messages": state["messages"]
        })

        return result

    # ---------------- Graph ----------------

    graph = StateGraph(AnalystState)

    graph.add_node("analyst", analyst)
    graph.add_node("expert", call_expert)
    graph.add_node("reviewer", call_reviewer)

    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", "expert")
    graph.add_edge("expert", "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()