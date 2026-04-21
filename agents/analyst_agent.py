from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    # Short output — just rewrite the query, nothing more
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=120)

    prompt = """Rewrite the user query as a precise SQL analytical request.
Be specific: mention metric, grouping, sort order, limit.
One sentence only. No SQL code."""

    sm = [SystemMessage(content=prompt)]

    def analyst(state: AnalystState):
        return {"messages": [llm.invoke(sm + state["messages"])]}

    g = StateGraph(AnalystState)
    g.add_node("analyst", analyst)
    g.add_edge(START, "analyst")
    g.add_edge("analyst", END)
    return g.compile()
