from langchain.tools import tool
from fpdf import FPDF
import os

@tool
def generate_pdf_report(text: str, filename: str = "analysis_report.pdf") -> str:
    """
    Generate a PDF report and return the file path
    """

    # Create folder if not exists
    output_dir = "generated_reports"
    os.makedirs(output_dir, exist_ok=True)

    file_path = os.path.join(output_dir, filename)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)

    pdf.output(file_path)

    return file_path