import streamlit as st
import base64
import json
import pandas as pd
from fpdf import FPDF
import unicodedata
import matplotlib.pyplot as plt
import os

from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.supervisor_agent import get_supervisor_app


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Insight Grid AI", layout="wide")


# =====================================================
# BACKGROUND IMAGE
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
# DATA ENGINE
# =====================================================
st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)


# =====================================================
# SESSION STATE
# =====================================================
if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "mode" not in st.session_state:
    st.session_state.mode = "summarize"

selected_query = None


# =====================================================
# MODE SWITCH
# =====================================================
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("📊 Summarize"):
        st.session_state.mode = "summarize"

with col2:
    if st.button("✨ Suggest"):
        st.session_state.mode = "suggest"


# =====================================================
# SUMMARIZE (WITH VISUALIZATION)
# =====================================================
if st.session_state.mode == "summarize":

    st.markdown("### 📊 Summarize Options")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if st.button("Region Revenue"):
            selected_query = "Show total revenue by region as a pie chart"

    with c2:
        if st.button("Monthly Trend"):
            selected_query = "Show monthly sales trend as a line chart"

    with c3:
        if st.button("Top Products"):
            selected_query = "Show top 5 products by revenue as a bar chart"

    with c4:
        if st.button("Store Sales"):
            selected_query = "Show revenue distribution by store as a bar chart"

    with c5:
        if st.button("Daily Transactions"):
            selected_query = "Show daily transaction count trend as a line chart"


# =====================================================
# SUGGEST (NO VISUALIZATION)
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
            "Show total number of transactions completed today",
            "Which product category has the highest sales?"
        ]
    )

    if option != "Select...":
        selected_query = option


# =====================================================
# INPUT BOX
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
# VISUALIZATION CONTROL
# =====================================================
def should_show_visualization(user_query, df):
    if st.session_state.mode != "summarize":
        return False
    return df.shape[1] == 2


def auto_visualize(df, user_query):

    query = user_query.lower()
    col1, col2 = df.columns

    if "pie" in query:
        fig, ax = plt.subplots()
        ax.pie(df[col2], labels=df[col1], autopct='%1.1f%%')
        st.pyplot(fig)

    elif "line" in query:
        st.line_chart(df.set_index(col1))

    else:
        st.bar_chart(df.set_index(col1))


# =====================================================
# RESPONSE RENDERER
# =====================================================
def render_response(response, user_query):

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        parsed = json.loads(response[start:end])

        if parsed.get("type") == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.dataframe(df)

            if should_show_visualization(user_query, df):
                st.subheader("📈 Visualization")
                auto_visualize(df, user_query)

        elif parsed.get("type") == "list":
            st.subheader("📌 Insights")
            for item in parsed["items"]:
                st.markdown(f"- {item}")

        elif parsed.get("type") == "text":
            st.subheader("🧠 Summary")
            st.write(parsed["content"])

    except:
        st.write(response)


# =====================================================
# PDF FORMATTER (UNCHANGED FEATURE)
# =====================================================
def format_pdf_content(response):

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        parsed = json.loads(response[start:end])

        if parsed.get("type") == "table":
            columns = parsed["columns"]
            data = parsed["data"]

            lines = []
            header = " | ".join(columns)
            lines.append(header)
            lines.append("-" * len(header))

            for row in data:
                lines.append(" | ".join(str(x) for x in row))

            return "\n".join(lines)

        elif parsed.get("type") == "list":
            return "\n".join([f"- {item}" for item in parsed["items"]])

        elif parsed.get("type") == "text":
            return parsed["content"]

    except:
        pass

    return response


# =====================================================
# RUN ANALYSIS
# =====================================================
if run_clicked:

    if not user_query.strip():
        st.warning("Enter a query")

    else:
        with st.spinner("Running Multi-Agent System..."):

            try:
                supervisor_app = get_supervisor_app()

                result = supervisor_app.invoke({
                    "messages": [HumanMessage(content=user_query)],
                    "step": 0
                })

                st.success("Analysis completed ✅")

                messages = result.get("messages", [])
                response = ""

                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                render_response(response, user_query)

                # =====================================================
                # PDF DOWNLOAD (RESTORED 🔥)
                # =====================================================
                def clean_text(text):
                    text = unicodedata.normalize("NFKD", text)
                    return text.encode("latin-1", "ignore").decode("latin-1")

                formatted = format_pdf_content(response)

                pdf = FPDF()
                pdf.add_page()

                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "Database Analysis Report", ln=True)

                pdf.ln(5)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Query:", ln=True)

                pdf.set_font("Arial", size=12)
                pdf.multi_cell(0, 8, clean_text(user_query))

                pdf.ln(5)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Summary:", ln=True)

                pdf.set_font("Arial", size=12)
                pdf.multi_cell(0, 8, clean_text(formatted))

                pdf_bytes = pdf.output(dest="S").encode("latin-1")

                st.download_button(
                    label="📄 Download Report",
                    data=pdf_bytes,
                    file_name="analysis_report.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error("Agent failed ❌")
                st.exception(e)