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

[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.05);
    padding: 15px;
    border-radius: 12px;
}}
</style>
""", unsafe_allow_html=True)


# =====================================================
# SESSION STATE
# =====================================================
if "mode" not in st.session_state:
    st.session_state.mode = "summarize"

if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "df" not in st.session_state:
    st.session_state.df = None

if "response" not in st.session_state:
    st.session_state.response = ""

if "chart_type" not in st.session_state:
    st.session_state.chart_type = "Bar Chart"

if "drill_value" not in st.session_state:
    st.session_state.drill_value = None


# =====================================================
# HEADER
# =====================================================
col1, col2 = st.columns([6,2])

with col1:
    st.markdown("## 🤖 Insight Grid AI")
    st.caption("Enterprise Analytics Dashboard")

with col2:
    if st.button("🔌 Test DB"):
        try:
            conn = get_db_connection()
            st.success("Connected ✅")
        except:
            st.error("Failed ❌")


# =====================================================
# MODE SWITCH
# =====================================================
c1, c2 = st.columns(2)

with c1:
    if st.button("📊 Summarize"):
        st.session_state.mode = "summarize"

with c2:
    if st.button("✨ Suggest"):
        st.session_state.mode = "suggest"


# =====================================================
# SUMMARIZE BUTTONS
# =====================================================
selected_query = None

if st.session_state.mode == "summarize":

    st.subheader("📊 Quick Insights")

    c1,c2,c3,c4,c5 = st.columns(5)

    with c1:
        if st.button("Revenue by Region"):
            selected_query = "Show total revenue by region"

    with c2:
        if st.button("Top Products"):
            selected_query = "Show top 5 products by revenue"

    with c3:
        if st.button("Monthly Sales"):
            selected_query = "Show monthly sales trend"

    with c4:
        if st.button("Store Sales"):
            selected_query = "Show revenue by store"

    with c5:
        if st.button("Transactions"):
            selected_query = "Show daily transactions"


# =====================================================
# SUGGEST MODE
# =====================================================
else:
    selected_query = st.selectbox("Suggestions", [
        "Select...",
        "Top customers by revenue",
        "Average order value",
        "Total transactions today",
        "Product category performance"
    ])


if selected_query and selected_query != "Select...":
    st.session_state.user_query = selected_query


# =====================================================
# INPUT
# =====================================================
query = st.text_area("", value=st.session_state.user_query)
run = st.button("Run Analysis")


# =====================================================
# RUN AGENTS
# =====================================================
if run:
    app = get_supervisor_app()

    result = app.invoke({
        "messages": [HumanMessage(content=query)],
        "step": 0
    })

    for msg in reversed(result["messages"]):
        if getattr(msg, "type", "") == "ai":
            st.session_state.response = msg.content
            break


# =====================================================
# PARSE RESPONSE (FIXED)
# =====================================================
def parse_response(resp):
    try:
        start = resp.find("{")
        end = resp.rfind("}") + 1
        clean = resp[start:end].replace("'", '"')
        return json.loads(clean)
    except:
        return None


parsed = parse_response(st.session_state.response)


# =====================================================
# DISPLAY DATA
# =====================================================
if parsed and parsed.get("type") == "table":

    df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
    st.session_state.df = df

    st.subheader("📊 Data ($)")
    st.dataframe(df)


    # =====================================================
    # FILTERS (POWER BI STYLE)
    # =====================================================
    st.subheader("🎛️ Filters")

    filter_cols = st.multiselect("Select columns to filter", df.columns)

    for col in filter_cols:
        values = df[col].unique()
        selected = st.multiselect(f"{col}", values, default=values)
        df = df[df[col].isin(selected)]


    # =====================================================
    # KPI CARDS
    # =====================================================
    try:
        val_col = df.columns[-1]
        df[val_col] = pd.to_numeric(df[val_col], errors='coerce')

        c1,c2,c3 = st.columns(3)
        c1.metric("Total", f"${df[val_col].sum():,.0f}")
        c2.metric("Average", f"${df[val_col].mean():,.0f}")
        c3.metric("Max", f"${df[val_col].max():,.0f}")
    except:
        pass


    # =====================================================
    # DRILL DOWN
    # =====================================================
    st.subheader("🔍 Drill Down")

    group_col = st.selectbox("Select dimension", df.columns[:-1])

    if group_col:
        grouped = df.groupby(group_col)[val_col].sum().reset_index()
        st.dataframe(grouped)

        drill_value = st.selectbox("Select value to drill", grouped[group_col])

        if drill_value:
            detail = df[df[group_col] == drill_value]
            st.write("Detailed View")
            st.dataframe(detail)


    # =====================================================
    # VISUALIZATION
    # =====================================================
    st.subheader("📈 Visualization")

    chart = st.selectbox(
        "Chart Type",
        ["Bar Chart", "Pie Chart", "Area Chart"],
        key="chart_select"
    )

    label = df.columns[1]
    value = df.columns[-1]

    df[value] = pd.to_numeric(df[value], errors='coerce')

    chart_df = df[[label, value]].sort_values(by=value, ascending=False)

    if chart == "Bar Chart":
        st.bar_chart(chart_df.set_index(label))

    elif chart == "Pie Chart":
        fig, ax = plt.subplots()
        ax.pie(chart_df[value], labels=chart_df[label], autopct='%1.1f%%')
        st.pyplot(fig)

    elif chart == "Area Chart":
        st.area_chart(chart_df.set_index(label))


# =====================================================
# PDF DOWNLOAD
# =====================================================
if st.session_state.response:

    def clean_text(text):
        text = unicodedata.normalize("NFKD", text)
        return text.encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Insight Grid Report", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, clean_text(st.session_state.response))

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button(
        "📄 Download Report",
        data=pdf_bytes,
        file_name="report.pdf"
    )