# -----------------------------------------
# Analyst Agent
# Converts user query to analytical query
# -----------------------------------------

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    # Fast model
    llm = ChatOpenAI(model="gpt-4o-mini")

    prompt = """
You are senior business analyst.

Rewrite user query into clear business analytical request.

Return only rewritten request.
"""

    sm = [SystemMessage(content=prompt)]

    def analyst(state):

        r = llm.invoke(sm + state["messages"])

        return {"messages":[r]}

    g = StateGraph(AnalystState)

    g.add_node("analyst", analyst)

    g.add_edge(START, "analyst")
    g.add_edge("analyst", END)

    return g.compile()