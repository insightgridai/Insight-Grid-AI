from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage

from langchain_openai import ChatOpenAI


# ---------------------------------------------------
# STATE
# ---------------------------------------------------
class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------
# MAIN APP
# ---------------------------------------------------
def get_reviewer_app():

    llm = ChatOpenAI(model="gpt-4o-mini")

    system_prompt = """
You are a final reviewer agent.

Your responsibility:
Convert previous output into strict valid JSON.

RULES:

1. If tabular result exists:

{
  "type": "table",
  "columns": ["col1","col2"],
  "data": [
    ["v1","v2"]
  ]
}

2. If explanation needed:

{
  "type": "text",
  "content": "message"
}

3. No markdown
4. No extra text
5. Must be valid JSON only
6. Prefer table whenever rows exist
"""

    system_message = [
        SystemMessage(content=system_prompt)
    ]


    def reviewer(state: ReviewerState):

        response = llm.invoke(
            system_message + state["messages"]
        )

        return {
            "messages": [response]
        }


    graph = StateGraph(ReviewerState)

    graph.add_node("reviewer", reviewer)

    graph.add_edge(START, "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()
