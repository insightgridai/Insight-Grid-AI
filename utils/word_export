from docx import Document
from docx.shared import Inches
import os

def create_word(parsed: dict, query: str, chart_path=None):

    doc = Document()
    doc.add_heading("Insight Grid AI Report", 0)

    doc.add_heading("Query", level=1)
    doc.add_paragraph(query)

    summary = parsed.get("summary", "")
    if summary:
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(summary)

    kpis = parsed.get("kpis", [])
    if kpis:
        doc.add_heading("KPIs", level=1)
        for k in kpis:
            doc.add_paragraph(f'{k.get("label","")}: {k.get("value","")}')

    if parsed.get("type") == "table":
        columns = parsed.get("columns", [])
        data = parsed.get("data", [])

        if columns and data:
            doc.add_heading("Data Table", level=1)

            table = doc.add_table(rows=1, cols=len(columns))
            hdr = table.rows[0].cells

            for i, col in enumerate(columns):
                hdr[i].text = str(col)

            for row in data:
                r = table.add_row().cells
                for i, val in enumerate(row):
                    r[i].text = str(val)

    elif parsed.get("type") == "text":
        doc.add_heading("Analysis", level=1)
        doc.add_paragraph(parsed.get("content", ""))

    if chart_path and os.path.exists(chart_path):
        try:
            doc.add_heading("Visualization", level=1)
            doc.add_picture(chart_path, width=Inches(6))
        except:
            pass

    filename = "Insight_Report.docx"
    doc.save(filename)

    return filename
