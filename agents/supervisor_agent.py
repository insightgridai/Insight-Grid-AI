from typing import Annotated, TypedDict, Literal

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agents.analyst_agent import get_analyst_app
from agents.expert_agent import get_expert_app
from agents.reviewer_agent import get_reviewer_app


# ----------------------------------------------------
# Decision Schema
# ----------------------------------------------------

class AgentSelector(BaseModel):
    next_node: Literal["analyst", "expert", "reviewer", "END"] = Field(
        description="Choose which agent should run next"
    )


# ----------------------------------------------------
# LLM
# ----------------------------------------------------

llm = ChatOpenAI(model="gpt-5-nano")

agent_selector_llm = llm.with_structured_output(AgentSelector)


# ----------------------------------------------------
# System Prompt
# ----------------------------------------------------

supervisor_system_message = [
    SystemMessage(
        content="""
You are a supervisor coordinating three agents:

1. analyst → understands the question
2. expert → runs SQL queries
3. reviewer → summarizes results

Execution order must be:

analyst → expert → reviewer → END

You only decide routing.
Never generate analysis yourself.
"""
    )
]


# ----------------------------------------------------
# State
# ----------------------------------------------------

class SupervisorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next_node: Literal["analyst", "expert", "reviewer", "END"]


# ----------------------------------------------------
# Supervisor Node
# ----------------------------------------------------

def supervisor(state: SupervisorState):

    response = agent_selector_llm.invoke(
        supervisor_system_message + state["messages"]
    )

    return {"next_node": response.next_node}


# ----------------------------------------------------
# Agent Wrappers
# ----------------------------------------------------

def call_analyst(state: SupervisorState):

    analyst_app = get_analyst_app()

    return analyst_app.invoke({
        "messages": state["messages"]
    })


def call_expert(state: SupervisorState):

    expert_app = get_expert_app()

    return expert_app.invoke({
        "messages": state["messages"]
    })


def call_reviewer(state: SupervisorState):

    reviewer_app = get_reviewer_app()

    return reviewer_app.invoke({
        "messages": state["messages"]
    })


# ----------------------------------------------------
# Routing
# ----------------------------------------------------

def route_from_supervisor(
    state: SupervisorState
) -> Literal["analyst", "expert", "reviewer", "__end__"]:

    next_node = state.get("next_node")

    if next_node == "END":
        return "__end__"

    return next_node


# ----------------------------------------------------
# Graph
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
# Export
# ----------------------------------------------------

def get_supervisor_app():
    return supervisor_app