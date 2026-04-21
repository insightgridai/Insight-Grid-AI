from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=80,        # very small — just rewrite query
        max_retries=2,
        request_timeout=20,
    )

    sm = [SystemMessage(content=(
        "Rewrite user query as a precise SQL request. "
        "Include: metric, table, grouping, sort, limit. "
        "One sentence only. No SQL code."
    ))]

    def analyst(state: AnalystState):
        return {"messages": [llm.invoke(sm + state["messages"][-1:])]}

    g = StateGraph(AnalystState)
    g.add_node("analyst", analyst)
    g.add_edge(START, "analyst")
    g.add_edge("analyst", END)
    return g.compile()