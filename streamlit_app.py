import streamlit as st
import base64
import json
import pandas as pd
from fpdf import FPDF
import unicodedata

from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.supervisor_agent import get_supervisor_app


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)


# =====================================================
# BACKGROUND IMAGE
# =====================================================
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


bg_image = get_base64_image("assets/backgroud6.jfif")

st.markdown(
    f"""
    <style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
        url("data:image/png;base64,{bg_image}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    div.stButton > button {{
        white-space: nowrap;
    }}

    textarea {{
        background-color: rgba(0,0,0,0.6) !important;
        color: white !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# =====================================================
# HEADER
# =====================================================
col1, col2 = st.columns([6, 2])

with col1:
    st.markdown(
        """
        <h2 style="margin-bottom:5px;">🤖 Insight Grid AI</h2>
        <p style="color:#9ca3af; font-size:14px;">
            Where Data, Agents, and Decisions Connect
        </p>
        """,
        unsafe_allow_html=True
    )

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
st.markdown(
    """
    <h2 style="margin-bottom:5px;">📊 Data Engine</h2>
    <p style="color:#9ca3af;">
        Ask analytical questions based on your database
    </p>
    """,
    unsafe_allow_html=True
)

user_query = st.text_area(
    "Enter your analysis question",
    placeholder="e.g. Compare sales Jan vs Feb 2025"
)

run_clicked = st.button("Run Analysis")


# =====================================================
# AUTO VISUALIZATION
# =====================================================
def auto_visualize(df):

    st.subheader("📊 Data Preview")
    st.dataframe(df)

    st.subheader("📈 Visualization")

    cols = df.columns

    if len(cols) == 1:
        st.metric(cols[0], df.iloc[0, 0])

    elif len(cols) == 2:
        col1, col2 = cols

        if "date" in col1.lower():
            st.line_chart(df.set_index(col1))
        else:
            st.bar_chart(df.set_index(col1))

    else:
        st.line_chart(df)


# =====================================================
# RUN ANALYSIS
# =====================================================
if run_clicked:

    if not user_query.strip():
        st.warning("Please enter a question.")

    else:
        with st.spinner("Running Multi-Agent System..."):

            try:
                supervisor_app = get_supervisor_app()

                result = supervisor_app.invoke({
                    "messages": [HumanMessage(content=user_query)],
                    "step": 0
                })

                st.success("Analysis completed")

                # -------------------------------------------------
                # Extract response safely
                # -------------------------------------------------
                messages = result.get("messages", [])
                response = ""

                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                if not response:
                    response = "No meaningful response generated."

                # -------------------------------------------------
                # SAFE JSON PARSING (robust)
                # -------------------------------------------------
                data = None
                try:
                    start = response.find("{")
                    end = response.rfind("}") + 1

                    if start != -1 and end != -1:
                        json_str = response[start:end]
                        data = json.loads(json_str)
                except Exception:
                    data = None

                # -------------------------------------------------
                # VISUALIZATION
                # -------------------------------------------------
                if data and isinstance(data, dict) and "columns" in data and "data" in data:
                    df = pd.DataFrame(data["data"], columns=data["columns"])
                    auto_visualize(df)

                # -------------------------------------------------
                # SUMMARY
                # -------------------------------------------------
                st.subheader("🧠 Summary")
                st.write(response)

                # -------------------------------------------------
                # CLEAN TEXT (FIX UNICODE ERROR)
                # -------------------------------------------------
                def clean_text(text):
                    text = unicodedata.normalize("NFKD", text)
                    return text.encode("latin-1", "ignore").decode("latin-1")

                clean_query = clean_text(user_query)
                clean_response = clean_text(response)

                # -------------------------------------------------
                # PDF GENERATION
                # -------------------------------------------------
                pdf = FPDF()
                pdf.add_page()

                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "Database Analysis Report", ln=True)

                pdf.ln(5)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Query:", ln=True)

                pdf.set_font("Arial", size=12)
                pdf.multi_cell(0, 8, clean_query)

                pdf.ln(5)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Summary:", ln=True)

                pdf.set_font("Arial", size=12)
                pdf.multi_cell(0, 8, clean_response)

                pdf_bytes = pdf.output(dest="S").encode("latin-1")

                # -------------------------------------------------
                # DOWNLOAD BUTTON
                # -------------------------------------------------
                st.download_button(
                    label="📄 Download Report",
                    data=pdf_bytes,
                    file_name="analysis_report.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error("Agent or processing failed ❌")
                st.exception(e)
