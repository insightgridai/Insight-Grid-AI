# =============================================================
# agents/reviewer_agent.py
# Converts raw SQL output → clean JSON (table + KPIs)
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
You are a data reviewer. Convert the SQL query result into a strict JSON response.

Choose ONE of the two formats below:

FORMAT 1 — when data is tabular (rows + columns):
{
  "type": "table",
  "columns": ["Col1", "Col2", "Col3"],
  "data": [
    ["val1", "val2", "val3"]
  ],
  "kpis": [
    {"label": "Total Records",    "value": "42"},
    {"label": "Top Value",        "value": "$1,234"},
    {"label": "Average",          "value": "308.5"},
    {"label": "Date Range",       "value": "2022 – 2024"}
  ],
  "summary": "One sentence insight about this data."
}

FORMAT 2 — when result is text / no rows:
{
  "type": "text",
  "content": "Plain text answer here.",
  "kpis": []
}

RULES:
- Output JSON ONLY. No markdown. No explanation.
- kpis: always include 3-4 meaningful KPIs derived from the data.
  Good KPI examples: Total Rows, Sum of revenue column, Max value, Min value,
  Average, Date range, Top item name.
- All values in kpis must be strings (formatted nicely, e.g. "$1,234" not 1234).
- summary: one sentence in plain English about what the data shows.
- data values must be plain strings or numbers (no nested objects).
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
