# agents/supervisor_agent.py
#
# ROOT CAUSE FIX:
#   Previously call_reviewer() passed state["messages"] — the ENTIRE
#   message history including tool call objects from expert.
#   This overwhelmed the reviewer LLM causing it to crash → fallback
#   → "Could not format result."
#
# FIX:
#   call_expert() now returns a single clean AIMessage with just the
#   data text (via _extract_clean_result).
#   call_reviewer() extracts only that last clean AI message and sends
#   it as a fresh HumanMessage to the reviewer — keeping it tiny.

from typing import TypedDict, Annotated, Dict, Any
from langchain_core.messages import (
    AnyMessage, AIMessage, HumanMessage, ToolMessage
)
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from agents.analyst_agent  import get_analyst_app
from agents.expert_agent   import get_expert_app
from agents.reviewer_agent import get_reviewer_app


class SupervisorState(TypedDict):
    messages:  Annotated[list[AnyMessage], add_messages]
    step:      int
    next_node: str
    db_config: Dict[str, Any]


# ── Routing ────────────────────────────────────────────────
def supervisor(state: SupervisorState):
    step  = state.get("step", 0)
    nodes = ["analyst", "expert", "reviewer", "__end__"]
    return {
        "messages":  state["messages"],
        "step":      step + 1,
        "next_node": nodes[min(step, 3)],
        "db_config": state["db_config"],
    }

def route_next(state: SupervisorState):
    return state["next_node"]


# ── Helper: pull clean text from a message list ────────────
def _extract_clean_result(msgs) -> str:
    """
    Returns the best plain-text result from the expert's message list.
    Priority: last ToolMessage → last non-tool-call AIMessage.
    Truncated to 1500 chars to keep reviewer prompt small.
    """
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            c = str(m.content or "").strip()
            if c and c.lower() != "none":
                return c[:1500]
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = str(getattr(m, "content", "") or "").strip()
            if c and not (hasattr(m, "tool_calls") and m.tool_calls):
                return c[:1500]
    return "No data returned."


# ── Agent callers ──────────────────────────────────────────
def call_analyst(state: SupervisorState):
    try:
        result = get_analyst_app().invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Analyst error: {e}")]}


def call_expert(state: SupervisorState):
    """
    Run expert agent, then REPLACE its full message chain with a
    single clean AIMessage containing just the result text.
    This is what gets passed to the reviewer — nothing else.
    """
    try:
        result      = get_expert_app(state["db_config"]).invoke(
            {"messages": state["messages"]}
        )
        expert_msgs = result.get("messages", [])
        clean_text  = _extract_clean_result(expert_msgs)
        # Return ONE clean message — reviewer will see only this
        return {"messages": [AIMessage(content=clean_text)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Expert error: {e}")]}


def call_reviewer(state: SupervisorState):
    """
    Pass ONLY the last clean message (expert result) to reviewer.
    Never pass tool call history.
    """
    try:
        msgs = state["messages"]

        # Get the last meaningful AI message (the clean expert result)
        last_content = ""
        for m in reversed(msgs):
            if isinstance(m, AIMessage):
                c = str(getattr(m, "content", "") or "").strip()
                if c and not (hasattr(m, "tool_calls") and m.tool_calls):
                    last_content = c
                    break

        if not last_content:
            last_content = "No data returned."

        # Send as a fresh HumanMessage so reviewer formats it cleanly
        reviewer_input = {"messages": [HumanMessage(content=last_content)]}
        result = get_reviewer_app().invoke(reviewer_input)
        return {"messages": result["messages"]}

    except Exception as e:
        return {"messages": [AIMessage(
            content=(
                '{"type":"text",'
                f'"content":"Reviewer error: {str(e)[:100]}",'
                '"kpis":[],"summary":""}'
            )
        )]}


# ── Graph assembly ─────────────────────────────────────────
def get_supervisor_app(db_config: dict):
    graph = StateGraph(SupervisorState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("analyst",    call_analyst)
    graph.add_node("expert",     call_expert)
    graph.add_node("reviewer",   call_reviewer)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_next)
    graph.add_edge("analyst",  "supervisor")
    graph.add_edge("expert",   "supervisor")
    graph.add_edge("reviewer", "supervisor")
    app = graph.compile()

    class Wrapped:
        def invoke(self, payload):
            payload["db_config"] = db_config
            return app.invoke(payload)

    return Wrapped()
