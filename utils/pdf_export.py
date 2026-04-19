# -----------------------------------------
# Export PDF report
# -----------------------------------------

from fpdf import FPDF

def create_pdf(parsed, query):

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)

    # Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Insight Grid AI Report", ln=True)

    pdf.ln(5)

    # Query
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 8, f"Query: {query}")

    pdf.ln(5)

    # Table Result
    if parsed["type"] == "table":

        cols = parsed["columns"]
        rows = parsed["data"]

        width = 190 / len(cols)

        pdf.set_font("Arial", "B", 10)

        for c in cols:
            pdf.cell(width, 8, str(c), border=1)

        pdf.ln()

        pdf.set_font("Arial", "", 9)

        for row in rows:
            for item in row:
                pdf.cell(width, 8, str(item)[:20], border=1)
            pdf.ln()

    else:
        pdf.multi_cell(0, 8, parsed["content"])

    file = "report.pdf"
    pdf.output(file)

    return file