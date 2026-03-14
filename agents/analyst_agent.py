from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agents.expert_agent import get_expert_app


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    llm = ChatOpenAI(model="gpt-5-nano")

    analyst_system_message = [
        SystemMessage(
            content=(
                "You are a data analyst. Understand the user's question "
                "and forward it to the expert agent for SQL execution."
            )
        )
    ]

    def analyst(state: AnalystState):

        response = llm.invoke(
            analyst_system_message + state["messages"]
        )

        return {"messages": [response]}

    def call_expert(state: AnalystState):

        expert_app = get_expert_app()

        result = expert_app.invoke({
            "messages": state["messages"]
        })

        return result

    graph = StateGraph(AnalystState)

    graph.add_node("analyst", analyst)
    graph.add_node("expert", call_expert)

    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", "expert")
    graph.add_edge("expert", END)

    return graph.compile()