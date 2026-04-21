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
        max_tokens=700,
        max_retries=2,
        request_timeout=30,
    )

    prompt = (
        "Convert the SQL result to JSON only. No markdown. No explanation.\n\n"
        "Table format:\n"
        '{"type":"table","columns":["Col1","Col2"],"data":[["val",123]],'
        '"kpis":[{"label":"Total Records","value":"5"}],"summary":"One sentence."}\n\n'
        "Text format:\n"
        '{"type":"text","content":"answer here","kpis":[],"summary":""}\n\n'
        "RULES:\n"
        "- Numeric column values must be plain numbers: 2110527 NOT '2,110,527'\n"
        "- kpi values are display strings: '$2,110,527'\n"
        "- Include 2-4 kpis (Total Records, Max, Min, Average)\n"
        "- summary: one plain English sentence\n"
        "- Output JSON ONLY — nothing else"
    )

    sm = [SystemMessage(content=prompt)]

    def reviewer(state: ReviewerState):
        msgs = state["messages"]
        # Safe slice — works even if only 1 message
        recent = msgs[-2:] if len(msgs) >= 2 else msgs
        return {"messages": [llm.invoke(sm + recent)]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()
