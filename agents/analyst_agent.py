from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    llm = ChatOpenAI(model="gpt-5-nano")

    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. Your task is to understand the user's "
                "question and determine what data is required from the database "
                "to answer it. Provide a clear analysis request that the expert "
                "agent can execute using SQL."
            )
        )
    ]

    # ---------------- Analyst Node ----------------

    def analyst(state: AnalystState):

        response = llm.invoke(
            analyst_system_message + state["messages"]
        )

        return {"messages": [response]}

    # ---------------- Graph ----------------

    graph = StateGraph(AnalystState)

    graph.add_node("analyst", analyst)

    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", END)

    return graph.compile()