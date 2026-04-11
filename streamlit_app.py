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
# SESSION STATE (FIX RESET ISSUE)
# =====================================================
if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "mode" not in st.session_state:
    st.session_state.mode = "summarize"

if "response" not in st.session_state:
    st.session_state.response = None

if "df" not in st.session_state:
    st.session_state.df = None


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
    background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
    url("data:image/png;base64,{bg_image}");
    background-size: cover;
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
# MODE SWITCH
# =====================================================
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
            selected_query = "Show monthly sales trend as a bar chart"

    with c3:
        if st.button("Top Products"):
            selected_query = "Show top 5 products by revenue as a bar chart"

    with c4:
        if st.button("Store Sales"):
            selected_query = "Show revenue by store as a bar chart"

    with c5:
        if st.button("Transactions"):
            selected_query = "Show total transactions by day as a bar chart"


# =====================================================
# SUGGEST
# =====================================================
else:

    st.markdown("### ✨ Suggestions")

    option = st.selectbox(
        "",
        [
            "Select...",
            "Top 5 customers by revenue",
            "Average order value",
            "Total transactions today",
            "Highest selling product category",
            "Customer count by region"
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
# VISUALIZATION FUNCTION
# =====================================================
def show_visualization(df):

    col1, col2 = df.columns[:2]

    st.markdown("### 📈 Visualization")

    chart = st.selectbox(
        "Choose Visualization",
        ["KPI", "Bar Chart", "Pie Chart", "Area Chart"]
    )

    if chart == "KPI":
        total = df[col2].sum()
        st.metric("Total ($)", f"${total:,.2f}")

    elif chart == "Bar Chart":
        st.bar_chart(df.set_index(col1))

    elif chart == "Pie Chart":
        fig, ax = plt.subplots()
        ax.pie(df[col2], labels=df[col1], autopct='%1.1f%%')
        st.pyplot(fig)

    elif chart == "Area Chart":
        st.area_chart(df.set_index(col1))


# =====================================================
# RUN ANALYSIS
# =====================================================
if run_clicked:

    if not user_query.strip():
        st.warning("Enter a query")

    else:
        with st.spinner("Running..."):

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

                # STORE RESPONSE
                st.session_state.response = response

            except Exception as e:
                st.error("Error")
                st.exception(e)


# =====================================================
# DISPLAY RESPONSE (🔥 FIXED JSON PARSE)
# =====================================================
if st.session_state.response:

    response = st.session_state.response

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        parsed = json.loads(response[start:end])

        if parsed.get("type") == "table":

            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.session_state.df = df

            st.subheader("📊 Data ($)")
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
# PDF DOWNLOAD
# =====================================================
if st.session_state.response:

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
    pdf.cell(0, 8, "Summary:", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, clean_text(st.session_state.response))

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.download_button(
        label="📄 Download Report",
        data=pdf_bytes,
        file_name="analysis_report.pdf",
        mime="application/pdf"
    )