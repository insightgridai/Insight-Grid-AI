# =============================================================
# agents/analyst_agent.py
# Rewrites vague user query → precise business analytical query
# =============================================================

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_analyst_app():

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = """
You are a senior business analyst.

Your job: rewrite the user's query into a precise, actionable analytical request
that a SQL expert can execute directly.

Rules:
- Be specific about metrics (e.g. "total revenue", "order count", "average order value")
- Mention time period if implied (e.g. "latest year", "last 12 months")
- Mention sort order and limit if relevant (e.g. "top 10 by revenue descending")
- Keep it concise — one clear sentence or two at most
- Do NOT write SQL yourself — just rewrite the business question clearly
"""

    sm = [SystemMessage(content=prompt)]

    def analyst(state: AnalystState):
        r = llm.invoke(sm + state["messages"])
        return {"messages": [r]}

    g = StateGraph(AnalystState)
    g.add_node("analyst", analyst)
    g.add_edge(START, "analyst")
    g.add_edge("analyst", END)

    return g.compile()
