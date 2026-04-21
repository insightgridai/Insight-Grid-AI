from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI


class ReviewerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def get_reviewer_app():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=700,
                     max_retries=2, request_timeout=30)

    prompt = (
        "Convert the data below to JSON only. No markdown. No extra text.\n\n"
        "FORMAT A — tabular data:\n"
        '{"type":"table",'
        '"columns":["Name","Revenue"],'
        '"data":[["pooja",2110527],["jyoti",1332132]],'
        '"kpis":['
        '{"label":"Total Records","value":"10"},'
        '{"label":"Max Revenue","value":"$2,110,527"},'
        '{"label":"Min Revenue","value":"$688,865"},'
        '{"label":"Average","value":"$1,021,417"}'
        '],'
        '"summary":"Top 10 customers by total revenue."}\n\n'
        "FORMAT B — single value or text:\n"
        '{"type":"text","content":"answer here","kpis":[],"summary":""}\n\n'
        "CRITICAL RULES:\n"
        "- data[] numbers MUST be plain integers/floats: 2110527 NOT '2,110,527'\n"
        "- kpi values are formatted strings: '$2,110,527'\n"
        "- Include 2-4 relevant kpis\n"
        "- summary: one plain English sentence\n"
        "- Output ONLY the JSON — nothing before or after it"
    )

    def reviewer(state: ReviewerState):
        msgs = state["messages"]
        # Take only the last message content as the data to format
        last = msgs[-1] if msgs else None
        if last is None:
            return {"messages": [AIMessage(
                content='{"type":"text","content":"No data received.","kpis":[],"summary":""}'
            )]}
        # Extract content string safely
        content = str(getattr(last, "content", str(last)))[:3000]
        # Always send as fresh [system, human] — never pass tool history
        inp = [SystemMessage(content=prompt), HumanMessage(content=content)]
        return {"messages": [llm.invoke(inp)]}

    g = StateGraph(ReviewerState)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()
