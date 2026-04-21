from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_reviewer_app():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=600,
        max_retries=2,
        request_timeout=30,
    )

    prompt = (
        'Output JSON only. No markdown.\n'
        'Table: {"type":"table","columns":["A","B"],"data":[["x",123]],'
        '"kpis":[{"label":"Total","value":"5"}],"summary":"One sentence."}\n'
        'Text: {"type":"text","content":"answer","kpis":[],"summary":""}\n'
        'RULES: numeric data = plain numbers 2110527 NOT "2,110,527". '
        'kpi values = formatted strings "$2,110,527". Max 4 kpis. JSON only.'
    )

    sm = [SystemMessage(content=prompt)]

    def reviewer(state: ReviewerState):
        # Only pass last 2 messages to keep input tokens low
        return {"messages": [llm.invoke(sm + state["messages"][-2:])]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()
