# =============================================================
# utils/pdf_export.py
# FIX 1: White background, dark text — readable on paper
# FIX 2: _safe() strips unicode outside latin-1
# FIX 3: Chart image correct size/orientation (no more sideways chart)
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
    text = str(text) if not isinstance(text, str) else text
    for ch, rep in _UNICODE_MAP.items():
        text = text.replace(ch, rep)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class InsightPDF(FPDF):

    def header(self):
        self.set_fill_color(0, 77, 128)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Arial", "B", 13)
        self.set_text_color(255, 255, 255)
        self.set_y(4)
        self.cell(0, 10, "Insight Grid AI -- Analytics Report", ln=True, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _chart_dimensions(chart_path: str):
    """
    Return (width_mm, height_mm) for the chart image.
    Detects if image was saved rotated (height > width) and corrects it.
    Falls back to (185, None) if PIL not available.
    """
    try:
        from PIL import Image as PILImage
        with PILImage.open(chart_path) as img:
            w_px, h_px = img.size

        # Plotly bar charts are always wider than tall.
        # If h > w the image got rotated — treat as landscape.
        if h_px > w_px:
            w_px, h_px = h_px, w_px   # swap to correct orientation

        # Scale to fit 185mm wide on A4
        w_mm = 185.0
        h_mm = w_mm * (h_px / max(w_px, 1))

        # Cap height so chart fits on one page without overflow
        if h_mm > 120:
            scale = 120 / h_mm
            w_mm *= scale
            h_mm *= scale

        return round(w_mm, 1), round(h_mm, 1)

    except Exception:
        return 185, None   # safe default


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
    pdf.multi_cell(0, 7, _safe(query or "-"), fill=True)
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
        kpi_w = min(185 / len(kpis), 46)
        pdf.set_font("Arial", "B", 11)
        for kpi in kpis:
            pdf.set_fill_color(0, 119, 182)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(kpi_w, 10, _safe(str(kpi.get("value", ""))), border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Arial", "", 8)
        for kpi in kpis:
            pdf.set_fill_color(220, 235, 248)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(kpi_w, 6, _safe(str(kpi.get("label", ""))), border=1, fill=True, align="C")
        pdf.ln(8)

    # ── Table ──────────────────────────────────────────────
    if parsed.get("type") == "table":
        columns = parsed.get("columns", [])
        data    = parsed.get("data",    [])
        if columns and data:
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(0, 77, 128)
            pdf.cell(0, 8, "Data Table", ln=True)
            pdf.ln(2)
            col_w = min(185 / len(columns), 55)
            # Header
            pdf.set_fill_color(0, 77, 128)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 9)
            for col in columns:
                pdf.cell(col_w, 8, _safe(str(col))[:22], border=1, fill=True, align="C")
            pdf.ln()
            # Rows
            pdf.set_font("Arial", "", 8)
            for idx, row in enumerate(data):
                if pdf.get_y() > 265:
                    pdf.add_page()
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

    # ── Chart — FIX rotation & overflow ───────────────────
    if chart_path and os.path.exists(chart_path):
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 8, "Visualization", ln=True)
        pdf.ln(2)
        if pdf.get_y() > 200:
            pdf.add_page()

        w_mm, h_mm = _chart_dimensions(chart_path)
        if h_mm:
            pdf.image(chart_path, x=10, w=w_mm, h=h_mm)
        else:
            pdf.image(chart_path, x=10, w=w_mm)

    out = "Insight_Report.pdf"
    pdf.output(out)
    return out
