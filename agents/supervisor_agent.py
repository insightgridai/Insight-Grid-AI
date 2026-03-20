from typing import Annotated, TypedDict, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

from agents.analyst_agent import get_analyst_app
from agents.expert_agent import get_expert_app
from agents.reviewer_agent import get_reviewer_app


# ----------------------------------------------------
# STATE
# ----------------------------------------------------

class SupervisorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    step: int


# ----------------------------------------------------
# SUPERVISOR (NO LLM → ZERO COST)
# ----------------------------------------------------

def supervisor(state: SupervisorState):

    step = state.get("step", 0)

    # deterministic flow
    if step == 0:
        next_node = "analyst"
    elif step == 1:
        next_node = "expert"
    elif step == 2:
        next_node = "reviewer"
    else:
        next_node = "__end__"

    return {
        "step": step + 1,
        "next_node": next_node
    }


# ----------------------------------------------------
# AGENT WRAPPERS
# ----------------------------------------------------

def call_analyst(state: SupervisorState):
    analyst_app = get_analyst_app()
    return analyst_app.invoke({"messages": state["messages"]})


def call_expert(state: SupervisorState):
    expert_app = get_expert_app()
    return expert_app.invoke({"messages": state["messages"]})


def call_reviewer(state: SupervisorState):
    reviewer_app = get_reviewer_app()
    return reviewer_app.invoke({"messages": state["messages"]})


# ----------------------------------------------------
# ROUTING
# ----------------------------------------------------

def route_from_supervisor(state: SupervisorState):

    return state["next_node"]


# ----------------------------------------------------
# GRAPH
# ----------------------------------------------------

graph = StateGraph(SupervisorState)

graph.add_node("supervisor", supervisor)
graph.add_node("analyst", call_analyst)
graph.add_node("expert", call_expert)
graph.add_node("reviewer", call_reviewer)

graph.add_edge(START, "supervisor")

graph.add_conditional_edges(
    "supervisor",
    route_from_supervisor
)

graph.add_edge("analyst", "supervisor")
graph.add_edge("expert", "supervisor")
graph.add_edge("reviewer", "supervisor")


supervisor_app = graph.compile()


# ----------------------------------------------------
# EXPORT
# ----------------------------------------------------

def get_supervisor_app():
    return supervisor_app