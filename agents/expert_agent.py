from typing import TypedDict, Annotated

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain.tools import tool
from langchain_openai import ChatOpenAI

from fpdf import FPDF

# SQL tools
from tools.get_schema import get_schema
from tools.execute_sql import execute_sql


# ---------------- LLM ----------------

# IMPORTANT: use gpt-4o-mini (stable for tools)
llm = ChatOpenAI(model="gpt-4o-mini")


# ---------------- PDF TOOL ----------------

@tool
def generate_pdf_report(text: str, filename: str = "analysis_report.pdf") -> str:
    """Generate a PDF report from text"""

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)

    path = f"/tmp/{filename}"
    pdf.output(path)

    return path


# ---------------- LLM WITH TOOLS ----------------

expert_llm = llm.bind_tools([
    get_schema,
    execute_sql,
    generate_pdf_report
])


# ---------------- SYSTEM MESSAGE ----------------

expert_system_message = [
    SystemMessage(
        content="""
You are a senior data expert.

Your job is to answer analytical questions using the database.

Steps:
1. Understand the question.
2. Use the schema tool to inspect database structure if needed.
3. Generate SQL queries using the execute_sql tool.
4. Return the results clearly.

If the user asks for a report, generate a PDF.
"""
    )
]


# ---------------- STATE ----------------

class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------- EXPERT NODE ----------------

def expert(state: ExpertState):

    response = expert_llm.invoke(
        expert_system_message + state["messages"]
    )

    return {"messages": [response]}


# ---------------- GRAPH ----------------

expert_graph = StateGraph(ExpertState)

expert_graph.add_node("expert", expert)

expert_graph.add_node(
    "tools",
    ToolNode([
        get_schema,
        execute_sql,
        generate_pdf_report
    ])
)

expert_graph.add_edge(START, "expert")

expert_graph.add_conditional_edges(
    "expert",
    tools_condition
)

expert_graph.add_edge("tools", "expert")

expert_app = expert_graph.compile()


# ---------------- EXPORT ----------------

def get_expert_app():
    return expert_app