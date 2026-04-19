from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage

from langchain_openai import ChatOpenAI


# ---------------------------------------------------
# STATE
# ---------------------------------------------------
class AnalystState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------
# APP
# ---------------------------------------------------
def get_analyst_app():

    llm = ChatOpenAI(model="gpt-5-nano")

    system_prompt = """
You are a senior business data analyst.

Your task:
1. Understand the user's question.
2. Rewrite it into a clean analytical request.
3. Make it easier for SQL generation.

Examples:

User:
Show top 10 customers latest year

Output:
Find latest year in sales data and return top 10 customers by revenue.

User:
Monthly sales trend

Output:
Show monthly total revenue ordered by month.

IMPORTANT:
- Return only rewritten request.
- No explanations.
- No bullets.
"""

    system_message = [
        SystemMessage(content=system_prompt)
    ]


    def analyst(state: AnalystState):

        response = llm.invoke(
            system_message + state["messages"]
        )

        return {
            "messages": [response]
        }


    graph = StateGraph(AnalystState)

    graph.add_node("analyst", analyst)

    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", END)

    return graph.compile()
