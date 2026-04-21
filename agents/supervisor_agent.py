# agents/supervisor_agent.py
# Orchestrates: analyst → expert → reviewer
# KEY FIX: reviewer only receives the clean data text, never tool history.

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


def _best_text(msgs) -> str:
    """Extract best plain-text result from a message list."""
    for m in reversed(msgs):
        if isinstance(m, ToolMessage):
            c = str(m.content or "").strip()
            if c and c.lower() not in ("none", ""):
                return c[:2000]
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = str(getattr(m, "content", "") or "").strip()
            if c and not (hasattr(m, "tool_calls") and m.tool_calls):
                return c[:2000]
    return "No data returned."


def call_analyst(state: SupervisorState):
    try:
        result = get_analyst_app().invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Analyst error: {e}")]}


def call_expert(state: SupervisorState):
    """Run expert; return ONE clean message so reviewer stays small."""
    try:
        result     = get_expert_app(state["db_config"]).invoke(
            {"messages": state["messages"]}
        )
        clean_text = _best_text(result.get("messages", []))
        return {"messages": [AIMessage(content=clean_text)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Expert error: {e}")]}


def call_reviewer(state: SupervisorState):
    """Pass only the last clean AI message to reviewer as a HumanMessage."""
    try:
        msgs = state["messages"]
        last_content = ""
        for m in reversed(msgs):
            if isinstance(m, AIMessage):
                c = str(getattr(m, "content", "") or "").strip()
                if c and not (hasattr(m, "tool_calls") and m.tool_calls):
                    last_content = c
                    break
        if not last_content:
            last_content = "No data returned."

        result = get_reviewer_app().invoke(
            {"messages": [HumanMessage(content=last_content)]}
        )
        return {"messages": result["messages"]}
    except Exception as e:
        return {"messages": [AIMessage(
            content=(
                '{"type":"text",'
                f'"content":"Reviewer error: {str(e)[:120]}",'
                '"kpis":[],"summary":""}'
            )
        )]}


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
