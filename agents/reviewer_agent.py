from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI


# ---------------- LLM ----------------

llm = ChatOpenAI(model="gpt-4o-mini")


# ---------------- SYSTEM MESSAGE ----------------

reviewer_system_message = [
    SystemMessage(
        content="""
You are a reviewer agent responsible for formatting final outputs.

STRICT OUTPUT RULES:

1. If the result contains structured data (tables, SQL results, aggregations):
Return ONLY JSON in this format:
{
  "type": "table",
  "columns": ["column1", "column2"],
  "data": [
    ["value1", "value2"]
  ]
}

2. If the result is insights:
Return:
{
  "type": "list",
  "items": [
    "insight 1",
    "insight 2"
  ]
}

3. If the result is explanation:
Return:
{
  "type": "text",
  "content": "your explanation"
}

IMPORTANT RULES:
- Do NOT return plain paragraphs for data queries
- Do NOT add extra text outside JSON
- Always prefer table format when data exists
- Output MUST be valid JSON
"""
    )
]


# ---------------- STATE ----------------

class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------- REVIEWER NODE ----------------

def reviewer(state: ReviewerState):

    response = llm.invoke(
        reviewer_system_message + state["messages"]
    )

    return {"messages": [response]}


# ---------------- GRAPH ----------------

reviewer_graph = StateGraph(ReviewerState)

reviewer_graph.add_node("reviewer", reviewer)

reviewer_graph.add_edge(START, "reviewer")
reviewer_graph.add_edge("reviewer", END)

reviewer_app = reviewer_graph.compile()


# ---------------- EXPORT ----------------

def get_reviewer_app():
    return reviewer_app
