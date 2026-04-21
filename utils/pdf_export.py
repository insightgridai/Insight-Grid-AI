# =============================================================
# utils/pdf_export.py
# FIXED:
# 1. All body text is BLACK / DARK (no white text on white page)
# 2. White text kept ONLY on blue headers
# 3. Downloaded PDF readable on white background
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
   "\u00d7": "x", "\u00f7": "/",
}
def _safe(text) -> str:
   text = str(text) if not isinstance(text, str) else text
   for ch, rep in _UNICODE_MAP.items():
       text = text.replace(ch, rep)
   return text.encode("latin-1", errors="replace").decode("latin-1")

# ── PDF Class ───────────────────────────────────────────────
class InsightPDF(FPDF):
   def header(self):
       # Blue Header Bar
       self.set_fill_color(0, 77, 128)
       self.rect(0, 0, 210, 18, "F")
       # White text ONLY in top bar
       self.set_font("Arial", "B", 13)
       self.set_text_color(255, 255, 255)
       self.set_y(4)
       self.cell(0, 10, "Insight Grid AI - Analytics Report", ln=True, align="C")
       # Reset body text to BLACK
       self.set_text_color(0, 0, 0)
       self.ln(4)
   def footer(self):
       self.set_y(-14)
       self.set_font("Arial", "I", 8)
       self.set_text_color(100, 100, 100)
       self.cell(0, 10, f"Page {self.page_no()}", align="C")

# ── Main Function ───────────────────────────────────────────
def create_pdf(parsed: dict, query: str, chart_path: str = None) -> str:
   pdf = InsightPDF()
   pdf.set_auto_page_break(True, 20)
   pdf.add_page()
   # ---------------------------------------------------------
   # QUERY
   # ---------------------------------------------------------
   pdf.set_font("Arial", "B", 11)
   pdf.set_text_color(0, 77, 128)
   pdf.cell(0, 8, "Query", ln=True)
   pdf.set_font("Arial", "", 10)
   pdf.set_fill_color(240, 248, 255)
   pdf.set_text_color(0, 0, 0)
   pdf.multi_cell(0, 7, _safe(query or "-"), fill=True)
   pdf.ln(4)
   # ---------------------------------------------------------
   # SUMMARY
   # ---------------------------------------------------------
   summary = _safe(parsed.get("summary", ""))
   if summary:
       pdf.set_font("Arial", "B", 11)
       pdf.set_text_color(0, 77, 128)
       pdf.cell(0, 8, "Summary", ln=True)
       pdf.set_font("Arial", "", 10)
       pdf.set_text_color(0, 0, 0)
       pdf.multi_cell(0, 7, summary)
       pdf.ln(4)
   # ---------------------------------------------------------
   # KPI SECTION
   # ---------------------------------------------------------
   kpis = parsed.get("kpis", [])
   if kpis:
       pdf.set_font("Arial", "B", 11)
       pdf.set_text_color(0, 77, 128)
       pdf.cell(0, 8, "Key Performance Indicators", ln=True)
       pdf.ln(2)
       kpi_w = min(185 / len(kpis), 46)
       # KPI VALUE BOXES
       pdf.set_font("Arial", "B", 11)
       for kpi in kpis:
           pdf.set_fill_color(0, 119, 182)
           pdf.set_text_color(255, 255, 255)   # White on blue box only
           pdf.cell(
               kpi_w, 10,
               _safe(str(kpi.get("value", ""))),
               border=1,
               fill=True,
               align="C"
           )
       pdf.ln()
       # KPI LABELS
       pdf.set_font("Arial", "", 8)
       for kpi in kpis:
           pdf.set_fill_color(220, 235, 248)
           pdf.set_text_color(0, 0, 0)
           pdf.cell(
               kpi_w, 6,
               _safe(str(kpi.get("label", ""))),
               border=1,
               fill=True,
               align="C"
           )
       pdf.ln(8)
   # ---------------------------------------------------------
   # TABLE OUTPUT
   # ---------------------------------------------------------
   if parsed.get("type") == "table":
       columns = parsed.get("columns", [])
       data = parsed.get("data", [])
       if columns and data:
           pdf.set_font("Arial", "B", 11)
           pdf.set_text_color(0, 77, 128)
           pdf.cell(0, 8, "Data Table", ln=True)
           pdf.ln(2)
           col_w = min(185 / len(columns), 55)
           # Table Header
           pdf.set_fill_color(0, 77, 128)
           pdf.set_text_color(255, 255, 255)
           pdf.set_font("Arial", "B", 9)
           for col in columns:
               pdf.cell(
                   col_w, 8,
                   _safe(str(col))[:20],
                   border=1,
                   fill=True,
                   align="C"
               )
           pdf.ln()
           # Table Rows
           pdf.set_font("Arial", "", 8)
           for i, row in enumerate(data):
               if i % 2 == 0:
                   pdf.set_fill_color(245, 250, 255)
               else:
                   pdf.set_fill_color(255, 255, 255)
               pdf.set_text_color(0, 0, 0)
               for item in row:
                   pdf.cell(
                       col_w, 7,
                       _safe(str(item))[:22],
                       border=1,
                       fill=True
                   )
               pdf.ln()
           pdf.ln(8)
   # ---------------------------------------------------------
   # TEXT RESULT
   # ---------------------------------------------------------
   elif parsed.get("type") == "text":
       pdf.set_font("Arial", "B", 11)
       pdf.set_text_color(0, 77, 128)
       pdf.cell(0, 8, "Analysis Result", ln=True)
       pdf.set_font("Arial", "", 10)
       pdf.set_text_color(0, 0, 0)
       pdf.multi_cell(0, 7, _safe(parsed.get("content", "")))
       pdf.ln(4)
   # ---------------------------------------------------------
   # CHART
   # ---------------------------------------------------------
   if chart_path and os.path.exists(chart_path):
       pdf.set_font("Arial", "B", 11)
       pdf.set_text_color(0, 77, 128)
       pdf.cell(0, 8, "Visualization", ln=True)
       pdf.ln(2)
       if pdf.get_y() > 220:
           pdf.add_page()
       pdf.image(chart_path, x=10, w=185)
   # ---------------------------------------------------------
   # SAVE
   # ---------------------------------------------------------
   out = "Insight_Report.pdf"
   pdf.output(out)
   return out
