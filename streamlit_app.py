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
# BACKGROUND
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
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
# =====================================================
col1, col2 = st.columns([6, 2])

with col1:
    st.markdown("<h2>🤖 Insight Grid AI</h2>", unsafe_allow_html=True)

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
# MODE SWITCH
# =====================================================
col1, col2 = st.columns(2)

if col1.button("📊 Summarize"):
    st.session_state.mode = "summarize"

if col2.button("✨ Suggest"):
    st.session_state.mode = "suggest"

selected_query = None


# =====================================================
# SUMMARIZE
# =====================================================
if st.session_state.mode == "summarize":

    c1, c2, c3, c4, c5 = st.columns(5)

    if c1.button("Region Revenue"):
        selected_query = "Show total revenue by region"

    if c2.button("Monthly Trend"):
        selected_query = "Show monthly sales trend"

    if c3.button("Top Products"):
        selected_query = "Show top 5 products by revenue"

    if c4.button("Store Sales"):
        selected_query = "Show revenue by store"

    if c5.button("Daily Transactions"):
        selected_query = "Show daily transaction count for latest year"


# =====================================================
# SUGGEST
# =====================================================
else:

    option = st.selectbox("", [
        "Select...",
        "Show Bottom 10 Districts by Total Revenue",
        "Show top 10 Stores by Average order value",
        "Show Top 10 Manufacturing Countries By Total Quantity sold",
        "Show Top 10 Suppliers by Total revenue Contribution",
        "Match columns and data types between Store_Dim and Item_Dim (exact or similar)"
    ])

    if option != "Select...":
        selected_query = option


# =====================================================
# INPUT
# =====================================================
if selected_query:
    st.session_state.user_query = selected_query

user_query = st.text_area("", value=st.session_state.user_query)

run_clicked = st.button("Run Analysis")


# =====================================================
# KPI
# =====================================================
def show_kpis(df):
    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        return

    col = num_cols[-1]
    st.metric("Total", f"{df[col].sum():,.0f}")
    st.metric("Avg", f"{df[col].mean():,.0f}")
    st.metric("Max", f"{df[col].max():,.0f}")


# =====================================================
# VISUALIZATION
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
# RESPONSE HANDLER (🔥 FIXED)
# =====================================================
def render_response(response):

    st.session_state.last_response = response

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        parsed = json.loads(response[start:end])

        if parsed.get("type") == "table":

            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.session_state.last_df = df

            st.markdown("### 📊 Data")
            st.dataframe(df)

            # ONLY SUMMARIZE
            if st.session_state.mode == "summarize":
                show_kpis(df)
                show_visualization(df)

        elif parsed.get("type") == "text":
            st.success(parsed.get("content", ""))

    except:
        # 🔥 METADATA SAFE FALLBACK
        st.markdown("### 📄 Result")

        if "no metadata" in response.lower():
            st.warning("No metadata similarities found")
        else:
            st.info("Showing raw response (non-structured output)")

        st.code(response)


# =====================================================
# RUN
# =====================================================
if run_clicked:

    st.session_state.last_df = None

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
# KEEP STATE
# =====================================================
if st.session_state.last_df is not None and not run_clicked:

    st.markdown("### 📊 Data")
    st.dataframe(st.session_state.last_df)

    if st.session_state.mode == "summarize":
        show_kpis(st.session_state.last_df)
        show_visualization(st.session_state.last_df)


# =====================================================
# PDF (🔥 FIXED)
# =====================================================
if st.session_state.last_response:

    pdf = FPDF()
    pdf.add_page()

    try:
        response = st.session_state.last_response

        start = response.find("{")
        end = response.rfind("}") + 1
        parsed = json.loads(response[start:end])

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)

        pdf.ln(5)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Query:", ln=True)

        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, st.session_state.user_query)

        pdf.ln(5)

        if parsed.get("type") == "table":

            columns = parsed["columns"]
            data = parsed["data"]

            col_width = 180 / len(columns)

            pdf.set_font("Arial", "B", 10)
            for col in columns:
                pdf.cell(col_width, 8, str(col), border=1)
            pdf.ln()

            pdf.set_font("Arial", size=9)
            for row in data:
                for item in row:
                    pdf.cell(col_width, 8, str(item)[:25], border=1)
                pdf.ln()

            pdf.ln(5)

            # ONLY SUMMARIZE
            if st.session_state.mode == "summarize":
                try:
                    df = pd.DataFrame(data, columns=columns)
                    num_cols = df.select_dtypes(include="number").columns

                    if len(num_cols) > 0:
                        value_col = num_cols[-1]
                        label_col = [c for c in df.columns if c != value_col][0]

                        chart_df = df.groupby(label_col)[value_col].sum().reset_index()

                        fig, ax = plt.subplots()
                        ax.bar(chart_df[label_col], chart_df[value_col])

                        plt.xticks(rotation=45)
                        plt.tight_layout()

                        img_path = "temp_chart.png"
                        fig.savefig(img_path)
                        plt.close(fig)

                        pdf.image(img_path, x=10, w=180)

                except:
                    pass

        elif parsed.get("type") == "text":

            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 8, parsed.get("content", ""))

    except:
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, st.session_state.last_response)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button("📄 Download Report", pdf_bytes, "report.pdf")
