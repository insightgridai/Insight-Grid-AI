from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.tools import tool

from tools.sql_tools import get_schema, execute_sql
from config.llm import llm

from fpdf import FPDF


# PDF TOOL
@tool
def generate_pdf_report(text: str, filename: str = "analysis_report.pdf") -> str:
    """Generate a PDF report from text"""

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for line in text.split("\n"):
            pdf.multi_cell(0, 10, line)

        file_path = f"/tmp/{filename}"
        pdf.output(file_path)

        return file_path

    except Exception as e:
        return f"PDF generation failed: {str(e)}"


# Bind tools to LLM
expert_llm = llm.bind_tools([
    get_schema,
    execute_sql,
    generate_pdf_report
])


# System message
expert_system_message = [
    SystemMessage(
        content="""
You are a senior data expert.

Use SQL tools to answer analyst questions.
Return raw results from database queries.
If report is requested generate a PDF.
"""
    )
]


# State
class ExpertState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Expert node
def expert(state: ExpertState):

    response = expert_llm.invoke(
        expert_system_message + state["messages"]
    )

    return {"messages": [response]}


# Graph
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


def get_expert_app():
    return expert_app