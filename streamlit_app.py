import streamlit as st
import base64
import json
import pandas as pd
from fpdf import FPDF
import matplotlib.pyplot as plt

from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.supervisor_agent import get_supervisor_app


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Insight Grid AI", layout="wide")


# =====================================================
# BACKGROUND + BUTTON STYLE
# =====================================================
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return ""

bg_image = get_base64_image("assets/backgroud6.jfif")

st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)),
                url("data:image/jpg;base64,{bg_image}");
    background-size: cover;
    background-position: center;
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
# =====================================================
st.title("🤖 Insight Grid AI")


# =====================================================
# SESSION STATE
# =====================================================
if "mode" not in st.session_state:
    st.session_state.mode = "summarize"

if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "last_df" not in st.session_state:
    st.session_state.last_df = None

if "last_response" not in st.session_state:
    st.session_state.last_response = ""


# =====================================================
# INPUT
# =====================================================
user_query = st.text_area("Enter Query")
run_clicked = st.button("Run Analysis")


# =====================================================
# RESPONSE HANDLER
# =====================================================
def render_response(response):
    try:
        parsed = json.loads(response)

        if parsed["type"] == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.session_state.last_df = df
            st.session_state.last_response = response
            st.dataframe(df)

        elif parsed["type"] == "text":
            st.success(parsed["content"])

    except:
        st.error("Parsing error")
        st.code(response)


# =====================================================
# RUN ANALYSIS
# =====================================================
if run_clicked:

    with st.spinner("Running..."):

        app = get_supervisor_app()

        result = app.invoke({
            "messages": [HumanMessage(content=user_query)],
            "step": 0
        })

        messages = result.get("messages", [])

        for msg in reversed(messages):
            if getattr(msg, "type", "") == "ai":
                render_response(msg.content)
                break


# =====================================================
# DOWNLOAD REPORT (✅ FIXED HERE)
# =====================================================
if st.session_state.last_response:

    try:
        start = st.session_state.last_response.find("{")
        end = st.session_state.last_response.rfind("}") + 1
        parsed = json.loads(st.session_state.last_response[start:end])

        # ===== AUTO PAGE SIZE =====
        columns = parsed.get("columns", [])
        num_cols = len(columns)

        if num_cols <= 6:
            pdf = FPDF(orientation='P')
        elif num_cols <= 10:
            pdf = FPDF(orientation='L')
        else:
            pdf = FPDF(orientation='L', format=(300, 210))

        pdf.add_page()

        # ===== TITLE =====
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)

        pdf.ln(5)

        # ===== QUERY =====
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Query:", ln=True)

        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, st.session_state.user_query)

        pdf.ln(5)

        # ===== TABLE =====
        if parsed["type"] == "table":

            data = parsed["data"]

            # ===== DYNAMIC WIDTH =====
            page_width = pdf.w - 20
            col_width = page_width / len(columns)

            # ===== HEADER =====
            pdf.set_font("Arial", "B", 9)
            for col in columns:
                pdf.cell(col_width, 8, str(col), border=1)
            pdf.ln()

            # ===== DATA =====
            pdf.set_font("Arial", size=8)
            for row in data:
                for item in row:
                    text = str(item)
                    if len(text) > 20:
                        text = text[:17] + "..."
                    pdf.cell(col_width, 8, text, border=1)
                pdf.ln()

        elif parsed["type"] == "text":

            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 8, parsed["content"])

    except:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, st.session_state.last_response)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button(
        "📄 Download Report",
        pdf_bytes,
        "report.pdf"
    )
