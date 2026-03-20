from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI


# ---------------- LLM (CHEAP MODEL) ----------------
# Use nano → very low cost
llm = ChatOpenAI(model="gpt-5-nano")


# ---------------- SYSTEM MESSAGE ----------------

reviewer_system_message = [
    SystemMessage(
        content="""
You are a data reviewer.

Your task is to summarize structured data results.

Rules:
- Keep summary very short (3-4 lines max)
- Focus only on key insights
- No repetition
- No technical details
- No JSON
- No SQL
- No file paths or links

Output only plain text.
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