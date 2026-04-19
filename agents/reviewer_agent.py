# -----------------------------------------
# Convert final output to JSON
# -----------------------------------------

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_reviewer_app():

    llm = ChatOpenAI(model="gpt-4o-mini")

    prompt = """
Convert final response into JSON only.

Table:
{
"type":"table",
"columns":["A"],
"data":[["x"]]
}

Text:
{
"type":"text",
"content":"..."
}
"""

    sm = [SystemMessage(content=prompt)]

    def reviewer(state):

        r = llm.invoke(sm + state["messages"])

        return {"messages":[r]}

    g = StateGraph(ReviewerState)

    g.add_node("reviewer", reviewer)

    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)

    return g.compile()