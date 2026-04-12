import streamlit as st
import base64
import json
import pandas as pd
from fpdf import FPDF
import unicodedata
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
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


bg_image = get_base64_image("assets/backgroud6.jfif")

st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)),
    background-image: url("data:image/png;base64,{bg_image}");
    background-size: cover;
}}

textarea {{
    background-color: rgba(0,0,0,0.6) !important;
    color: white !important;
}}

div[data-testid="stButton"] button {{
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 13px;
    background-color: #1f2937;
    color: white;
}}

[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.05);
    padding: 15px;
    border-radius: 12px;
    text-align: center;
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
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
            cur.fetchone()
            cur.close()
            conn.close()
            st.success("Connection Successful ✅")
        except Exception as e:
            st.error("Connection Failed ❌")
            st.exception(e)

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
# DATA ENGINE
# =====================================================
st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    if st.button("📊 Summarize"):
        st.session_state.mode = "summarize"

with col2:
    if st.button("✨ Suggest"):
        st.session_state.mode = "suggest"


selected_query = None


# =====================================================
# SUMMARIZE OPTIONS
# =====================================================
if st.session_state.mode == "summarize":

    st.markdown("### 📊 Summarize Options")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if st.button("Region Revenue"):
            selected_query = "Show total revenue by region as a pie chart"

    with c2:
        if st.button("Monthly Trend"):
            selected_query = "Show monthly sales trend"

    with c3:
        if st.button("Top Products"):
            selected_query = "Show top 5 products by revenue as a bar chart"

    with c4:
        if st.button("Store Sales"):
            selected_query = "Show revenue by store as a bar chart"

    with c5:
        if st.button("Daily Transactions"):
            selected_query = "Show daily transaction count"


# =====================================================
# SUGGEST
# =====================================================
else:

    st.markdown("### ✨ Suggestions")

    option = st.selectbox(
        "",
        [
            "Select...",
            "Compare metadata from sales_fact and customer_dim",
            "List top 5 customers by total purchase value",
            "What is the average order value overall?",
            "Show total number of transactions today",
            "Which product category has highest sales?"
        ]
    )

    if option != "Select...":
        selected_query = option


# =====================================================
# INPUT
# =====================================================
if selected_query:
    st.session_state.user_query = selected_query

user_query = st.text_area(
    "",
    value=st.session_state.user_query,
    placeholder="Ask your data question..."
)

run_clicked = st.button("Run Analysis")


# =====================================================
# KPI CARDS
# =====================================================
def show_kpis(df):

    try:
        value_col = df.columns[-1]
        df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

        total = df[value_col].sum()
        avg = df[value_col].mean()
        max_val = df[value_col].max()

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Total Revenue", f"${total:,.0f}")
        col2.metric("📊 Avg Value", f"${avg:,.0f}")
        col3.metric("🔥 Max Value", f"${max_val:,.0f}")

    except:
        st.warning("KPI not available")


# =====================================================
# VISUALIZATION
# =====================================================
def show_visualization(df):

    if len(df.columns) < 2:
        st.warning("Not enough data")
        return

    label_col = df.columns[1]
    value_col = df.columns[-1]

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    show_kpis(df)

    st.markdown("### 📈 Visualization")

    chart = st.selectbox(
        "Choose Visualization",
        ["Bar Chart", "Pie Chart", "Area Chart"],
        key="chart_selector"
    )

    chart_df = df[[label_col, value_col]].copy()
    chart_df = chart_df.sort_values(by=value_col, ascending=False)

    if chart == "Bar Chart":
        st.bar_chart(chart_df.set_index(label_col))

    elif chart == "Pie Chart":
        fig, ax = plt.subplots()
        ax.pie(chart_df[value_col], labels=chart_df[label_col], autopct='%1.1f%%')
        st.pyplot(fig)

    elif chart == "Area Chart":
        st.area_chart(chart_df.set_index(label_col))


# =====================================================
# RESPONSE HANDLER
# =====================================================
def render_response(response):

    try:
        cleaned = response.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1

        json_str = cleaned[start:end]

        # FIX JSON
        json_str = json_str.replace("'", '"')

        parsed = json.loads(json_str)

        if parsed.get("type") == "table":

            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])

            st.session_state.last_df = df
            st.session_state.last_response = response

            st.markdown("### 📊 Data ($)")
            st.dataframe(df)

            if st.session_state.mode == "summarize":
                show_visualization(df)

        elif parsed.get("type") == "list":
            for item in parsed["items"]:
                st.markdown(f"- {item}")

        elif parsed.get("type") == "text":
            st.write(parsed["content"])

    except:
        st.error("Parsing error")
        st.write(response)


# =====================================================
# RUN ANALYSIS
# =====================================================
if run_clicked:

    if not user_query.strip():
        st.warning("Enter a query")

    else:
        with st.spinner("Running Multi-Agent System..."):

            try:
                app = get_supervisor_app()

                result = app.invoke({
                    "messages": [HumanMessage(content=user_query)],
                    "step": 0
                })

                messages = result.get("messages", [])
                response = ""

                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                render_response(response)

            except Exception as e:
                st.error("Error")
                st.exception(e)


# =====================================================
# KEEP RESULT
# =====================================================
if st.session_state.last_df is not None and not run_clicked:

    st.markdown("### 📊 Data ($)")
    st.dataframe(st.session_state.last_df)

    if st.session_state.mode == "summarize":
        show_visualization(st.session_state.last_df)


# =====================================================
# PDF DOWNLOAD
# =====================================================
if st.session_state.last_response:

    def clean_text(text):
        text = unicodedata.normalize("NFKD", text)
        return text.encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Database Analysis Report", ln=True)

    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Query:", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, clean_text(st.session_state.user_query))

    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Result:", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, clean_text(st.session_state.last_response))

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button(
        label="📄 Download Report",
        data=pdf_bytes,
        file_name="analysis_report.pdf",
        mime="application/pdf"
    )