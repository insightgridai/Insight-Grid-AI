from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_reviewer_app():

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=800)

    prompt = """Convert SQL result to JSON only. No markdown. No explanation.

Table format:
{"type":"table","columns":["Col1","Col2"],"data":[["a",123]],"kpis":[{"label":"Total","value":"10"}],"summary":"One sentence."}

Text format:
{"type":"text","content":"answer here","kpis":[],"summary":""}

CRITICAL:
- Numeric data values must be plain numbers: 2110527 NOT "2,110,527"
- kpi values are formatted strings: "$2,110,527"
- Output JSON only — nothing else"""

    sm = [SystemMessage(content=prompt)]

    def reviewer(state: ReviewerState):
        return {"messages": [llm.invoke(sm + state["messages"])]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()
