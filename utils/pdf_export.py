# =============================================================
# utils/pdf_export.py
# Export analysis results to a styled PDF report
# =============================================================

import os
from fpdf import FPDF


class InsightPDF(FPDF):
    """Custom PDF with header/footer branding."""

    def header(self):
        self.set_font("Arial", "B", 13)
        self.set_text_color(30, 144, 255)
        self.cell(0, 10, "Insight Grid AI — Analytics Report", ln=True, align="C")
        self.set_draw_color(30, 144, 255)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def create_pdf(parsed: dict, query: str, chart_path: str = None) -> str:
    """
    Build a PDF report.
    Returns the output file path.
    """

    pdf = InsightPDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()

    # ----------------------------------------------------------
    # Query section
    # ----------------------------------------------------------
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(255, 165, 0)
    pdf.cell(0, 8, "Query", ln=True)

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(30, 30, 30)
    pdf.multi_cell(0, 7, query, fill=True)
    pdf.ln(4)

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    summary = parsed.get("summary", "")
    if summary:
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(255, 165, 0)
        pdf.cell(0, 8, "Summary", ln=True)

        pdf.set_font("Arial", "I", 10)
        pdf.set_text_color(220, 220, 220)
        pdf.multi_cell(0, 7, summary)
        pdf.ln(4)

    # ----------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------
    kpis = parsed.get("kpis", [])
    if kpis:
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(255, 165, 0)
        pdf.cell(0, 8, "Key Performance Indicators", ln=True)
        pdf.ln(2)

        kpi_w = 44
        for i, kpi in enumerate(kpis):
            pdf.set_fill_color(20, 20, 60)
            pdf.set_text_color(30, 144, 255)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(kpi_w, 7, str(kpi.get("value", "")), border=1, fill=True, align="C")

            if (i + 1) % 4 == 0:
                pdf.ln()

        pdf.ln(6)

        for i, kpi in enumerate(kpis):
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(180, 180, 180)
            pdf.cell(kpi_w, 5, str(kpi.get("label", "")), align="C")

            if (i + 1) % 4 == 0:
                pdf.ln()

        pdf.ln(8)

    # ----------------------------------------------------------
    # Table
    # ----------------------------------------------------------
    if parsed.get("type") == "table":
        columns = parsed.get("columns", [])
        data    = parsed.get("data", [])

        if columns and data:
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(255, 165, 0)
            pdf.cell(0, 8, "Data Table", ln=True)
            pdf.ln(2)

            col_w = min(190 / len(columns), 55)

            # Header row
            pdf.set_fill_color(30, 30, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 9)
            for col in columns:
                pdf.cell(col_w, 8, str(col)[:20], border=1, fill=True, align="C")
            pdf.ln()

            # Data rows (alternate shading)
            pdf.set_font("Arial", "", 8)
            for idx, row in enumerate(data):
                if idx % 2 == 0:
                    pdf.set_fill_color(25, 25, 50)
                else:
                    pdf.set_fill_color(15, 15, 35)

                pdf.set_text_color(220, 220, 220)
                for item in row:
                    pdf.cell(col_w, 7, str(item)[:22], border=1, fill=True)
                pdf.ln()

            pdf.ln(8)

    # ----------------------------------------------------------
    # Text content
    # ----------------------------------------------------------
    elif parsed.get("type") == "text":
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(255, 165, 0)
        pdf.cell(0, 8, "Analysis Result", ln=True)

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(220, 220, 220)
        pdf.multi_cell(0, 7, parsed.get("content", ""))
        pdf.ln(4)

    # ----------------------------------------------------------
    # Chart image
    # ----------------------------------------------------------
    if chart_path and os.path.exists(chart_path):
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(255, 165, 0)
        pdf.cell(0, 8, "Visualization", ln=True)
        pdf.ln(2)
        pdf.image(chart_path, x=10, w=190)

    # ----------------------------------------------------------
    # Save
    # ----------------------------------------------------------
    out = "Insight_Report.pdf"
    pdf.output(out)
    return out
