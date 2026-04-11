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
    background-position: center;
}}

textarea {{
    background-color: rgba(0,0,0,0.6) !important;
    color: white !important;
}}

/* Small pill buttons */
div[data-testid="stButton"] button {{
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 13px;
    background-color: #1f2937;
    color: white;
}}

.active-btn {{
    background: linear-gradient(90deg, #2563eb, #3b82f6) !important;
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
# INPUT UI (INLINE CLEAN STYLE)
# =====================================================
st.markdown("<h2>📊 Data Engine</h2>", unsafe_allow_html=True)

if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Summarize"

selected_query = None

# ---- INLINE TABS (SIDE BY SIDE TEXT STYLE) ----
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("📊 Summarize", key="sum_tab"):
        st.session_state.active_tab = "Summarize"

with col2:
    if st.button("✨ Suggest", key="sug_tab"):
        st.session_state.active_tab = "Suggest"


# =====================================================
# SMALL FONT STYLE (IMPORTANT)
# =====================================================
st.markdown("""
<style>
.small-text {
    font-size: 14px;
    color: #d1d5db;
    margin-bottom: 10px;
}
.chip {
    display: inline-block;
    padding: 6px 12px;
    margin: 4px;
    border-radius: 20px;
    background-color: rgba(255,255,255,0.08);
    color: #facc15;
    cursor: pointer;
}
.chip:hover {
    background-color: rgba(37,99,235,0.6);
    color: white;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# SUMMARIZE OPTIONS (INLINE TEXT CHIPS)
# =====================================================
if st.session_state.active_tab == "Summarize":

    st.markdown('<div class="small-text">Summarize Options</div>', unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("Revenue", key="rev"):
            selected_query = "Summarize total revenue"

    with col2:
        if st.button("Monthly", key="mon"):
            selected_query = "Monthly sales trend"

    with col3:
        if st.button("Avg Order", key="avg"):
            selected_query = "Average order value"

    with col4:
        if st.button("Top Products", key="top"):
            selected_query = "Top products by revenue"

    with col5:
        if st.button("Region", key="reg"):
            selected_query = "Revenue by region"


# =====================================================
# SUGGEST (CLEAN DROPDOWN)
# =====================================================
elif st.session_state.active_tab == "Suggest":

    st.markdown('<div class="small-text">Suggestions</div>', unsafe_allow_html=True)

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


# ---- UPDATE INPUT ----
if selected_query:
    st.session_state.user_query = selected_query


# ---- INPUT BOX ----
user_query = st.text_area(
    "",
    value=st.session_state.user_query,
    placeholder="Ask your data question..."
)

run_clicked = st.button("Run Analysis")


# =====================================================
# SUMMARIZE OPTIONS (INLINE CHIPS)
# =====================================================
if st.session_state.active_tab == "Summarize":
    st.markdown("### 📊 Summarize Options")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if st.button("Revenue"):
            selected_query = "Summarize total revenue"

    with c2:
        if st.button("Monthly"):
            selected_query = "Monthly sales trend"

    with c3:
        if st.button("Avg Order"):
            selected_query = "Average order value"

    with c4:
        if st.button("Top Products"):
            selected_query = "Top products by revenue"

    with c5:
        if st.button("Region"):
            selected_query = "Revenue by region"


# =====================================================
# SUGGESTIONS (SMALL DROPDOWN)
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


# ---- Update input ----
if selected_query:
    st.session_state.user_query = selected_query


# ---- TEXT INPUT ----
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
    query = user_query.lower()
    if "metadata" in query or "schema" in query:
        return False
    return df.shape[1] == 2


def auto_visualize(df, user_query):
    query = user_query.lower()

    if len(df.columns) == 2:
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
        parsed = json.loads(response)

        if parsed.get("type") == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.dataframe(df)

            if should_show_visualization(user_query, df):
                with st.expander("📈 Visualization"):
                    auto_visualize(df, user_query)

        elif parsed.get("type") == "list":
            for item in parsed["items"]:
                st.markdown(f"- {item}")

        elif parsed.get("type") == "text":
            st.write(parsed["content"])

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

                messages = result.get("messages", [])
                response = ""

                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai":
                        response = msg.content
                        break

                render_response(response, user_query)

            except Exception as e:
                st.error("Error")
                st.exception(e)