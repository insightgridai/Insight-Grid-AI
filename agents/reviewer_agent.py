# agents/reviewer_agent.py
# Converts raw SQL result → structured JSON for the UI.
#
# ROOT CAUSE OF "Could not format result":
#   The reviewer was receiving the FULL message history including
#   all tool call objects (get_schema, execute_sql responses).
#   This caused the LLM to exceed context / get confused and crash.
#
# FIX:
#   supervisor_agent.py now passes only the CLEAN result text to
#   the reviewer (not the full chain). The reviewer just formats it.
#   max_tokens=600 is enough for a 10-row JSON table with KPIs.

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
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
        "Convert the data below to JSON only. No markdown. No explanation.\n\n"
        "If it is tabular data use:\n"
        '{"type":"table","columns":["Col1","Col2"],"data":[["val",123]],'
        '"kpis":[{"label":"Total Records","value":"10"},{"label":"Max","value":"$2,110,527"},'
        '{"label":"Min","value":"$688,865"},{"label":"Average","value":"$1,021,417"}],'
        '"summary":"One plain English sentence."}\n\n'
        "If it is a single value or non-tabular answer use:\n"
        '{"type":"text","content":"answer here","kpis":[],"summary":""}\n\n'
        "STRICT RULES:\n"
        "- data[] values: plain numbers only — 2110527 NOT '2,110,527'\n"
        "- kpi values: formatted display strings — '$2,110,527'\n"
        "- Include 2-4 kpis relevant to the data\n"
        "- summary: one sentence, plain English\n"
        "- Output valid JSON ONLY — absolutely nothing else before or after"
    )

    def reviewer(state: ReviewerState):
        msgs = state["messages"]
        # Only use the last message (the clean SQL result from expert)
        # This is the critical fix — do NOT send tool call history
        last = msgs[-1] if msgs else None
        if last is None:
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(
                content='{"type":"text","content":"No data to format.","kpis":[],"summary":""}'
            )]}

        # Build a fresh 2-message conversation: system + data to format
        content = getattr(last, "content", str(last))
        input_msgs = [
            SystemMessage(content=prompt),
            HumanMessage(content=str(content)[:2000]),  # hard cap — safety
        ]
        return {"messages": [llm.invoke(input_msgs)]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()
