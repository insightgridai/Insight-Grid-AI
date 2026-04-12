import streamlit as st
import base64
import json
import pandas as pd
from fpdf import FPDF
import matplotlib.pyplot as plt
import re   # ✅ NEW (for JSON fix)

from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.supervisor_agent import get_supervisor_app


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Insight Grid AI", layout="wide")


# =====================================================
# BACKGROUND (SLIGHTLY ENHANCED)
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
    background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.50)),   /* 🔥 lighter */
                url("data:image/jpg;base64,{bg_image}");
    background-size: cover;
    background-position: center;
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER (UNCHANGED)
# =====================================================
col1, col2 = st.columns([6, 2])

with col1:
    st.markdown("""
    <h2>🤖 Insight Grid AI</h2>
    <p style="color:#9ca3af;">Where Data, Agents, and Decisions Connect</p>
    """, unsafe_allow_html=True)

with col2:
    if st.button("🔌 Test DB Connection"):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            st.success("Connection Successful ✅")
        except:
            st.error("Connection Failed ❌")

st.markdown("<hr>", unsafe_allow_html=True)


# =====================================================
# SESSION STATE (UNCHANGED)
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
# TABS (UNCHANGED)
# =====================================================
tab1, tab2 = st.tabs(["📊 Summarize", "✨ Suggest"])

selected_query = None


# =====================================================
# SUMMARIZE TAB (UNCHANGED)
# =====================================================
with tab1:

    st.markdown("### ⚡ Quick Insights")

    c1, c2, c3, c4, c5 = st.columns(5)

    if c1.button("📍 Region Revenue"):
        selected_query = "Show total revenue by region as a pie chart"

    if c2.button("📅 Monthly Trend"):
        selected_query = "Show monthly sales trend"

    if c3.button("🏆 Top Products"):
        selected_query = "Show top 5 products by revenue as a bar chart"

    if c4.button("🏬 Store Sales"):
        selected_query = "Show revenue by store as a bar chart"

    if c5.button("📈 Daily Txn"):
        selected_query = "Show daily transaction count"


# =====================================================
# SUGGEST TAB (UNCHANGED)
# =====================================================
with tab2:

    st.markdown("### 🤖 Smart Suggestions")

    option = st.selectbox("", [
        "Select...",
        "Show Bottom 10 Districts by Total Revenue",
        "Show top 10 Stores by Average order value",
        "Show Top 10 Manufacturing Countries By Total Quantity sold",
        "Show Top 10 Suppliers by Total revenue Contribution"
    ])

    if option != "Select...":
        selected_query = option


# =====================================================
# INPUT (UNCHANGED)
# =====================================================
if selected_query:
    st.session_state.user_query = selected_query

user_query = st.text_area("Ask your data question...", value=st.session_state.user_query)

run_clicked = st.button("🚀 Run Analysis")


# =====================================================
# KPI (UNCHANGED)
# =====================================================
def show_kpis(df):

    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        return

    col = num_cols[-1]

    k1, k2, k3 = st.columns(3)

    k1.metric("💰 Total", f"{df[col].sum():,.0f}")
    k2.metric("📊 Avg", f"{df[col].mean():,.0f}")
    k3.metric("🔥 Max", f"{df[col].max():,.0f}")


# =====================================================
# VISUALIZATION (UNCHANGED)
# =====================================================
def show_visualization(df):

    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        return

    value_col = num_cols[-1]
    label_col = [c for c in df.columns if c != value_col][0]

    df = df.groupby(label_col)[value_col].sum().reset_index()

    chart = st.selectbox("Choose Visualization", ["Bar", "Pie", "Area"])

    if chart == "Bar":
        st.bar_chart(df.set_index(label_col))

    elif chart == "Pie":
        fig, ax = plt.subplots()
        ax.pie(df[value_col], labels=df[label_col], autopct='%1.1f%%')
        st.pyplot(fig)

    else:
        st.area_chart(df.set_index(label_col))


# =====================================================
# 🔥 RESPONSE HANDLER (ONLY FIX HERE)
# =====================================================
def clean_json(json_str):
    """Fix common JSON issues safely"""
    json_str = json_str.replace("'", '"')
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)
    return json_str


def render_response(response):

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        json_str = response[start:end]

        # ✅ FIX APPLIED HERE ONLY
        json_str = clean_json(json_str)

        parsed = json.loads(json_str)

        if parsed["type"] == "table":

            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])

            st.session_state.last_df = df
            st.session_state.last_response = response

            st.markdown("### 📊 Data")
            st.dataframe(df)

            if st.session_state.mode == "summarize":
                show_kpis(df)
                show_visualization(df)

        elif parsed["type"] == "text":
            st.success(parsed["content"])

    except Exception:
        st.error("Parsing error")
        st.code(response)


# =====================================================
# RUN ANALYSIS (UNCHANGED)
# =====================================================
if run_clicked:

    st.session_state.last_df = None

    with st.spinner("🤖 Running AI Agents..."):

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
# KEEP STATE (UNCHANGED)
# =====================================================
if st.session_state.last_df is not None and not run_clicked:

    st.markdown("### 📊 Data")
    st.dataframe(st.session_state.last_df)


# =====================================================
# DOWNLOAD REPORT (UNCHANGED)
# =====================================================
if st.session_state.last_response:

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, st.session_state.last_response)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button("📄 Download Report", pdf_bytes, "report.pdf")
