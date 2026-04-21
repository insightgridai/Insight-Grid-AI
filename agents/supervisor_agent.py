from typing import TypedDict, Annotated, Dict, Any
from langchain_core.messages import AnyMessage
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
    step = state.get("step", 0)
    nodes = ["analyst", "expert", "reviewer", "__end__"]
    return {
        "messages":  state["messages"],
        "step":      step + 1,
        "next_node": nodes[min(step, 3)],
        "db_config": state["db_config"],
    }


def call_analyst(state: SupervisorState):
    try:
        return get_analyst_app().invoke({"messages": state["messages"]})
    except Exception as e:
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content=f"Analyst error: {e}")]}


def call_expert(state: SupervisorState):
    try:
        return get_expert_app(state["db_config"]).invoke(
            {"messages": state["messages"]}
        )
    except Exception as e:
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content=f"Expert error: {e}")]}


def call_reviewer(state: SupervisorState):
    try:
        return get_reviewer_app().invoke({"messages": state["messages"]})
    except Exception as e:
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(
            content='{"type":"text","content":"Could not format result.","kpis":[],"summary":""}'
        )]}


def route_next(state: SupervisorState):
    return state["next_node"]


def get_supervisor_app(db_config):
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
