# agents/supervisor_agent.py

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
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            c = str(getattr(m, "content", "") or "").strip()
            if c and c.lower() not in ("none", ""):
                return c[:3000]
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = str(getattr(m, "content", "") or "").strip()
            has_tools = bool(getattr(m, "tool_calls", None))
            if c and not has_tools:
                return c[:3000]
    return "No data returned."


def _get_last_human_text(msgs) -> str:
    """Get the last human message content for retry."""
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            return str(getattr(m, "content", "") or "").strip()
    return ""


def call_analyst(state: SupervisorState):
    try:
        r = get_analyst_app().invoke({"messages": state["messages"]})
        return {"messages": r["messages"]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Analyst error: {e}")]}


def call_expert(state: SupervisorState):
    """
    Run expert. If tool message ordering error occurs,
    retry with a single clean HumanMessage — this always works.
    """
    try:
        r = get_expert_app(state["db_config"]).invoke(
            {"messages": state["messages"]}
        )
        clean_text = _extract_best_text(r.get("messages", []))
        return {"messages": [AIMessage(content=clean_text)]}

    except Exception as e:
        err = str(e).lower()
        # Tool message ordering error — retry with clean single message
        if "tool" in err or "missing" in err or "role" in err or "400" in err:
            try:
                # Get just the last human question and retry fresh
                last_q = _get_last_human_text(state["messages"])
                if not last_q:
                    last_q = "Run the requested analysis."
                r2 = get_expert_app(state["db_config"]).invoke(
                    {"messages": [HumanMessage(content=last_q)]}
                )
                clean_text = _extract_best_text(r2.get("messages", []))
                return {"messages": [AIMessage(content=clean_text)]}
            except Exception as e2:
                return {"messages": [AIMessage(content=f"Expert error: {str(e2)[:200]}")]}
        else:
            return {"messages": [AIMessage(content=f"Expert error: {str(e)[:200]}")]}


def call_reviewer(state: SupervisorState):
    try:
        msgs = state["messages"]
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
