# =============================================================
# agents/supervisor_agent.py
#
# THE KEY FIX:
# call_reviewer() extracts the CLEAN TEXT from expert output
# and sends it as a FRESH HumanMessage to the reviewer.
# The reviewer NEVER sees tool_calls, ToolMessages, or
# AIMessages with tool_calls. This was the root cause of
# "Could not format result."
# =============================================================

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


def _extract_best_text(msgs) -> str:
    """
    Scan message list and return the best plain-text data result.
    Priority order:
      1. Last ToolMessage with real content  (execute_sql result)
      2. Last plain AIMessage (no tool_calls)
    """
    # Priority 1: last ToolMessage
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            c = str(getattr(m, "content", "") or "").strip()
            if c and c.lower() not in ("none", ""):
                return c[:3000]
    # Priority 2: last plain AIMessage
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = str(getattr(m, "content", "") or "").strip()
            has_tools = bool(getattr(m, "tool_calls", None))
            if c and not has_tools:
                return c[:3000]
    return "No data returned."


def call_analyst(state: SupervisorState):
    try:
        r = get_analyst_app().invoke({"messages": state["messages"]})
        return {"messages": r["messages"]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Analyst error: {e}")]}


def call_expert(state: SupervisorState):
    """
    Run expert. After it finishes, extract the clean data text
    and return it as a single plain AIMessage.
    This ensures the supervisor message list stays clean.
    """
    try:
        r          = get_expert_app(state["db_config"]).invoke(
            {"messages": state["messages"]}
        )
        clean_text = _extract_best_text(r.get("messages", []))
        return {"messages": [AIMessage(content=clean_text)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Expert error: {str(e)[:200]}")]}


def call_reviewer(state: SupervisorState):
    """
    Extract the last clean AIMessage content and send it as
    a FRESH HumanMessage to the reviewer.
    This guarantees reviewer never sees tool_calls or ToolMessages.
    """
    try:
        msgs = state["messages"]
        # Get the last plain AIMessage (expert's clean result)
        data_text = ""
        for m in reversed(msgs):
            if isinstance(m, AIMessage):
                c = str(getattr(m, "content", "") or "").strip()
                has_tools = bool(getattr(m, "tool_calls", None))
                if c and not has_tools:
                    data_text = c
                    break

        if not data_text:
            data_text = "No data returned."

        # Send ONLY this as a fresh HumanMessage — no history, no tool noise
        r = get_reviewer_app().invoke(
            {"messages": [HumanMessage(content=data_text)]}
        )
        return {"messages": r["messages"]}

    except Exception as e:
        return {"messages": [AIMessage(content=(
            '{"type":"text",'
            f'"content":"Analysis complete. Data could not be formatted: {str(e)[:100]}",'
            '"kpis":[],"summary":""}'
        ))]}


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
