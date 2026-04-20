# =============================================================
# agents/reviewer_agent.py
# KEY FIX: data values must be RAW NUMBERS (not "2,110,527")
# so pandas can detect them as numeric for visualization.
# =============================================================

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_reviewer_app():

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = """
Convert the SQL result into JSON. Output JSON ONLY. No markdown. No explanation.

FORMAT 1 — tabular data:
{
  "type": "table",
  "columns": ["Customer Name", "Total Revenue"],
  "data": [
    ["pooja", 2110527],
    ["jyoti", 1332132]
  ],
  "kpis": [
    {"label": "Total Records", "value": "10"},
    {"label": "Max Revenue",   "value": "$2,110,527"},
    {"label": "Min Revenue",   "value": "$688,865"},
    {"label": "Average",       "value": "$1,021,417"}
  ],
  "summary": "One sentence insight about the data."
}

FORMAT 2 — text answer:
{
  "type": "text",
  "content": "Plain text answer here.",
  "kpis": [],
  "summary": ""
}

CRITICAL RULES:
- data values for numeric columns MUST be plain numbers: 2110527  NOT "2,110,527"
- String columns stay as strings: "pooja"
- kpis values are formatted strings for display: "$2,110,527"
- summary is ONE sentence in plain English
- Output ONLY the JSON object — nothing else
"""

    sm = [SystemMessage(content=prompt)]

    def reviewer(state: ReviewerState):
        r = llm.invoke(sm + state["messages"])
        return {"messages": [r]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)

    return g.compile()
