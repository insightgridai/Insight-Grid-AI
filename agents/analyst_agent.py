# agents/analyst_agent.py
# Rewrites user query into a precise SQL request description.
# Cost: max_tokens=80 — very cheap, one call only.

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=80,       # tiny — just rephrases the query
        max_retries=1,
        request_timeout=15,
    )
    system = SystemMessage(content=(
        "Rewrite the user query as a precise SQL request. "
        "Include metric, table, grouping, sort, limit. "
        "One sentence only. No SQL code."
    ))

    def analyst(state: AnalystState):
        msgs = state["messages"]
        # Only send the latest human message — saves tokens
        last = next((m for m in reversed(msgs)
                     if isinstance(m, HumanMessage)), None)
        input_msgs = [system, last] if last else [system] + msgs[-1:]
        return {"messages": [llm.invoke(input_msgs)]}

    g = StateGraph(AnalystState)
    g.add_node("analyst", analyst)
    g.add_edge(START, "analyst")
    g.add_edge("analyst", END)
    return g.compile()
