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
# STATE
# =====================================================
if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Summarize"

selected_query = None


# =====================================================
# DATA ENGINE — SUMMARIZE + SUGGEST SIDE BY SIDE ✅
# =====================================================
st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)

tab1, tab2 = st.columns([1, 1])

with tab1:
    if st.button("📊 Summarize"):
        st.session_state.active_tab = "Summarize"

with tab2:
    if st.button("✨ Suggest"):
        st.session_state.active_tab = "Suggest"


# =====================================================
# SUMMARIZE OPTIONS — REVENUE + MONTHLY SIDE BY SIDE ✅
# =====================================================
if st.session_state.active_tab == "Summarize":
    st.markdown("### 📊 Summarize Options")

    # Row 1
    r1c1, r1c2, r1c3 = st.columns([1, 1, 1])

    with r1c1:
        if st.button("Revenue"):
            selected_query = "Summarize total revenue"

    with r1c2:
        if st.button("Monthly"):
            selected_query = "Monthly sales trend"

    with r1c3:
        if st.button("Avg Order"):
            selected_query = "Average order value"

    # Row 2
    r2c1, r2c2, _ = st.columns([1, 1, 1])

    with r2c1:
        if st.button("Top Products"):
            selected_query = "Top products by revenue"

    with r2c2:
        if st.button("Region"):
            selected_query = "Revenue by region"


# =====================================================
# SUGGEST OPTIONS
# =====================================================
elif st.session_state.active_tab == "Suggest":
    st.markdown("### ✨ Suggestions")

    option = st.selectbox(
        "",
        [
            "Select...",
            "Compare metadata from sales_fact and customer_dim",
            "Show total revenue by region",
            "Top 5 customers by sales",
            "Monthly sales trend",
            "Product-wise revenue distribution",
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
# VISUALIZATION
# =====================================================
def should_show_visualization(user_query, df):
    if "metadata" in user_query.lower():
        return False
    return df.shape[1] == 2


def auto_visualize(df, user_query):
    col1, col2 = df.columns
    st.bar_chart(df.set_index(col1))


# =====================================================
# RESPONSE RENDERER
# =====================================================
def render_response(response, user_query):
    try:
        parsed = json.loads(response)

        if parsed.get("type") == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.dataframe(df)

            if should_show_visualization(user_query, df):
                with st.expander("📈 Visualization"):
                    auto_visualize(df, user_query)

        elif parsed.get("type") == "text":
            st.write(parsed["content"])

        elif parsed.get("type") == "list":
            for item in parsed["items"]:
                st.markdown(f"- {item}")

    except:
        st.write(response)


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

                response = ""
                for msg in reversed(result.get("messages", [])):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                render_response(response, user_query)

            except Exception as e:
                st.error("Error")
                st.exception(e)
