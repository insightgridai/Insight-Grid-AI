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
You are an expert reviewer tasked with summarizing detailed database analysis results.

Your goal is to produce a concise summary in exactly eight lines.

Focus on key insights such as:
- user counts
- growth
- order statistics
- top performers
- important trends

Avoid repeating tables or raw SQL results.

Keep language simple, professional, and presentation ready.
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