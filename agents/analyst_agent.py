from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from tools.get_schema import get_schema


# ---------------- State ----------------

class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_calls: int


# ---------------- App Builder ----------------

def get_analyst_app():

    # 🔥 Token-Controlled LLM
    llm = ChatOpenAI(
        model="gpt-5-nano",
        temperature=0,
        max_tokens=200,   # restrict output tokens
    )

    analyst_llm = llm.bind_tools([get_schema])

    # 🔥 Short System Prompt (less tokens every call)
    system_prompt = SystemMessage(
        content=(
            "You are a data analyst. "
            "Use get_schema tool once if needed. "
            "Then ask 2 concise questions for report creation."
        )
    )

    # ---------------- Analyst Node ----------------
    def analyst(state: AnalystState) -> AnalystState:

        # 🔥 Restrict tool loop to max 2 calls
        if state.get("tool_calls", 0) >= 2:
            final_prompt = SystemMessage(
                content="Stop using tools. Generate final 5 concise questions."
            )
            limited_messages = state["messages"][-4:]
            response = llm.invoke([final_prompt] + limited_messages)
            return {"messages": [response]}

        # 🔥 Limit message history to last 4 messages only
        limited_messages = state["messages"][-4:]

        response = analyst_llm.invoke(
            [system_prompt] + limited_messages
        )

        return {"messages": [response]}

    # ---------------- Tool Node ----------------
    tool_node = ToolNode([get_schema])

    def tool_wrapper(state: AnalystState):
        result = tool_node.invoke(state)
        return {
            "messages": result["messages"],
            "tool_calls": state.get("tool_calls", 0) + 1
        }

    # ---------------- Graph ----------------
    graph = StateGraph(AnalystState)

    graph.add_node("analyst", analyst)
    graph.add_node("tools", tool_wrapper)

    graph.add_edge(START, "analyst")
    graph.add_conditional_edges("analyst", tools_condition)
    graph.add_edge("tools", "analyst")

    graph.set_finish_point("analyst")

    return graph.compile()
