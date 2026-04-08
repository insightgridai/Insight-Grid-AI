import streamlit as st 
import base64 
import json 
import pandas as pd 
from fpdf import FPDF 
import unicodedata 
import matplotlib.pyplot as plt 
import os

from db.connection import get_db_connection from langchain_core.messages 
import HumanMessage from agents.supervisor_agent import get_supervisor_app

=====================================================

PAGE CONFIG

=====================================================

st.set_page_config(page_title="Insight Grid AI", layout="wide")

=====================================================

BACKGROUND IMAGE

=====================================================

def get_base64_image(image_path): with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()

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
</style>""", unsafe_allow_html=True)

=====================================================

HEADER

=====================================================

col1, col2 = st.columns([6, 2])

with col1: st.markdown(""" <h2>🤖 Insight Grid AI</h2> <p style="color:#9ca3af;">Where Data, Agents, and Decisions Connect</p> """, unsafe_allow_html=True)

with col2: if st.button("🔌 Test DB Connection"): try: conn = get_db_connection() cur = conn.cursor() cur.execute("SELECT 1") cur.fetchone() cur.close() conn.close() st.success("Connection Successful ✅") except Exception as e: st.error("Connection Failed ❌") st.exception(e)

st.markdown("<hr>", unsafe_allow_html=True)

=====================================================

INPUT

=====================================================

st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)

user_query = st.text_area( "Enter your analysis question", placeholder="e.g. Show revenue by division as pie chart" )

run_clicked = st.button("Run Analysis")

=====================================================

VISUALIZATION ENGINE

=====================================================

def should_show_visualization(user_query, df): query = user_query.lower()

# Skip visualization for metadata/schema queries
if "metadata" in query or "schema" in query:
    return False

# Only show if numeric comparison or aggregation
if df.shape[1] == 2:
    return True

return False

def auto_visualize(df, user_query): query = user_query.lower()

if len(df.columns) == 2:
    col1, col2 = df.columns

    if "pie" in query:
        fig, ax = plt.subplots()
        ax.pie(df[col2], labels=df[col1], autopct='%1.1f%%')
        st.pyplot(fig)

    elif "line" in query or "trend" in query:
        st.line_chart(df.set_index(col1))

    else:
        st.bar_chart(df.set_index(col1))

else:
    st.line_chart(df)

=====================================================

SMART RESPONSE RENDERER

=====================================================

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

        # ✅ Show visualization only on demand
        if should_show_visualization(user_query, df):
            with st.expander("📈 View Visualization (Optional)"):
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

=====================================================

FORMAT RESPONSE FOR PDF
=====================================================

RUN ANALYSIS
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
