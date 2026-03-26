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
    background-position: center;
    background-attachment: fixed;
}}

textarea {{
    background-color: rgba(0,0,0,0.6) !important;
    color: white !important;
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
# INPUT
# =====================================================
st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)

user_query = st.text_area(
    "Enter your analysis question",
    placeholder="e.g. Show revenue by division as pie chart"
)

run_clicked = st.button("Run Analysis")


# =====================================================
# VISUALIZATION ENGINE
# =====================================================
def auto_visualize(df, user_query):

    st.subheader("📈 Visualization")

    cols = df.columns
    query = user_query.lower()

    if len(cols) == 2:
        col1, col2 = cols

        if "pie" in query or "share" in query:
            fig, ax = plt.subplots()
            ax.pie(df[col2], labels=df[col1], autopct='%1.1f%%')
            st.pyplot(fig)

        elif "line" in query or "trend" in query:
            st.line_chart(df.set_index(col1))

        else:
            st.bar_chart(df.set_index(col1))

    else:
        st.line_chart(df)


# =====================================================
# SMART RESPONSE RENDERER
# =====================================================
def render_response(response, user_query):

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == -1:
            raise ValueError

        parsed = json.loads(response[start:end])

        if parsed.get("type") == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.subheader("📊 Data")
            st.dataframe(df)
            auto_visualize(df, user_query)

        elif parsed.get("type") == "list":
            st.subheader("📌 Key Insights")
            for item in parsed["items"]:
                st.markdown(f"- {item}")

        elif parsed.get("type") == "text":
            st.subheader("🧠 Summary")
            st.write(parsed["content"])

        else:
            st.write(response)

    except:
        st.subheader("🧠 Summary")
        st.write(response)


# =====================================================
# 🆕 FORMAT RESPONSE FOR PDF
# =====================================================
def format_pdf_content(response):

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == -1:
            return response

        parsed = json.loads(response[start:end])

        # TABLE
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

        # LIST
        elif parsed.get("type") == "list":
            return "\n".join([f"- {item}" for item in parsed["items"]])

        # TEXT
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

                messages = result.get("messages", [])
                response = ""

                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                if not response:
                    response = "No meaningful response generated."

                # UI render
                render_response(response, user_query)

                # =================================================
                # CLEAN + FORMAT FOR PDF
                # =================================================
                def clean_text(text):
                    text = unicodedata.normalize("NFKD", text)
                    return text.encode("latin-1", "ignore").decode("latin-1")

                formatted_response = format_pdf_content(response)

                clean_query = clean_text(user_query)
                clean_response = clean_text(formatted_response)

                # =================================================
                # PDF
                # =================================================
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

                st.download_button(
                    label="📄 Download Report",
                    data=pdf_bytes,
                    file_name="analysis_report.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error("Agent or processing failed ❌")
                st.exception(e)
