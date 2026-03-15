from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from tools.generate_pdf_report import generate_pdf_report


# LLM
llm = ChatOpenAI(model="gpt-4o-mini")


# Bind tool
reviewer_llm = llm.bind_tools([generate_pdf_report])


# System message
reviewer_system_message = [
    SystemMessage(
        content="""
You are an expert reviewer tasked with summarizing detailed database analysis reports.

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


# State
class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Reviewer node
def reviewer(state: ReviewerState):

    response = reviewer_llm.invoke(
        reviewer_system_message + state["messages"]
    )

    return {"messages": [response]}


# Graph
reviewer_graph = StateGraph(ReviewerState)

reviewer_graph.add_node("reviewer", reviewer)

reviewer_graph.add_node(
    "tools",
    ToolNode([generate_pdf_report])
)

reviewer_graph.add_edge(START, "reviewer")

reviewer_graph.add_conditional_edges(
    "reviewer",
    tools_condition
)

reviewer_graph.add_edge("tools", "reviewer")

reviewer_app = reviewer_graph.compile()


def get_reviewer_app():
    return reviewer_app