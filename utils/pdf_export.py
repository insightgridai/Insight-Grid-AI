# =============================================================
# utils/pdf_export.py
# FIX 1: White background, dark text — readable on paper
# FIX 2: _safe() strips all unicode outside latin-1 range
#         (fixes "\u2014 can't encode" crash)
# =============================================================

import os
from fpdf import FPDF

# ── Unicode safety map ──────────────────────────────────────
_UNICODE_MAP = {
    "\u2014": "-", "\u2013": "-",
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2026": "...", "\u00a0": " ",
    "\u20ac": "EUR", "\u2022": "-",
    "\u2212": "-", "\u00b0": "deg",
    "\u00d7": "x",  "\u00f7": "/",
}

def _safe(text) -> str:
    """Return a latin-1 safe string."""
    text = str(text) if not isinstance(text, str) else text
    for ch, rep in _UNICODE_MAP.items():
        text = text.replace(ch, rep)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── PDF class ───────────────────────────────────────────────
class InsightPDF(FPDF):

    def header(self):
        self.set_fill_color(0, 77, 128)          # dark blue band
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Arial", "B", 13)
        self.set_text_color(255, 255, 255)
        self.set_y(4)
        self.cell(0, 10, "Insight Grid AI -- Analytics Report", ln=True, align="C")
        self.set_text_color(0, 0, 0)             # reset to black for body
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def create_pdf(parsed: dict, query: str, chart_path: str = None) -> str:

    pdf = InsightPDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()

    # ── Query ──────────────────────────────────────────────
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 77, 128)
    pdf.cell(0, 8, "Query", ln=True)

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.set_fill_color(235, 245, 255)
    pdf.multi_cell(0, 7, _safe(query or "—"), fill=True)
    pdf.ln(4)

    # ── Summary ────────────────────────────────────────────
    summary = _safe(parsed.get("summary", ""))
    if summary:
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 8, "Summary", ln=True)
        pdf.set_font("Arial", "I", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 7, summary)
        pdf.ln(4)

    # ── KPIs ───────────────────────────────────────────────
    kpis = parsed.get("kpis", [])
    if kpis:
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 8, "Key Performance Indicators", ln=True)
        pdf.ln(2)

        kpi_w  = min(185 / len(kpis), 46)
        # Value row
        pdf.set_font("Arial", "B", 11)
        for i, kpi in enumerate(kpis):
            pdf.set_fill_color(0, 119, 182)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(kpi_w, 10, _safe(str(kpi.get("value",""))), border=1, fill=True, align="C")
        pdf.ln()
        # Label row
        pdf.set_font("Arial", "", 8)
        for i, kpi in enumerate(kpis):
            pdf.set_fill_color(220, 235, 248)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(kpi_w, 6, _safe(str(kpi.get("label",""))), border=1, fill=True, align="C")
        pdf.ln(8)

    # ── Table ──────────────────────────────────────────────
    if parsed.get("type") == "table":
        columns = parsed.get("columns", [])
        data    = parsed.get("data", [])
        if columns and data:
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(0, 77, 128)
            pdf.cell(0, 8, "Data Table", ln=True)
            pdf.ln(2)

            col_w = min(185 / len(columns), 55)

            # Header row
            pdf.set_fill_color(0, 77, 128)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 9)
            for col in columns:
                pdf.cell(col_w, 8, _safe(str(col))[:20], border=1, fill=True, align="C")
            pdf.ln()

            # Data rows — alternating light blue / white
            pdf.set_font("Arial", "", 8)
            for idx, row in enumerate(data):
                if idx % 2 == 0:
                    pdf.set_fill_color(235, 245, 255)
                else:
                    pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(30, 30, 30)
                for item in row:
                    pdf.cell(col_w, 7, _safe(str(item))[:22], border=1, fill=True)
                pdf.ln()
            pdf.ln(8)

    # ── Text ───────────────────────────────────────────────
    elif parsed.get("type") == "text":
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 8, "Analysis Result", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 7, _safe(parsed.get("content", "")))
        pdf.ln(4)

    # ── Chart ──────────────────────────────────────────────
    if chart_path and os.path.exists(chart_path):
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 8, "Visualization", ln=True)
        pdf.ln(2)
        # Make sure chart fits on page
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.image(chart_path, x=10, w=185)

    out = "Insight_Report.pdf"
    pdf.output(out)
    return out