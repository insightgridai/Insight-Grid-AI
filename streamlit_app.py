import streamlit as st
import base64
import json
import pandas as pd
import matplotlib.pyplot as plt

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
    background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
    url("data:image/png;base64,{bg_image}");
    background-size: cover;
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
st.markdown("## 🤖 Insight Grid AI")


# =====================================================
# INPUT UI
# =====================================================
st.markdown("### 📊 Data Engine")

if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Summarize"

selected_query = None


# ---- SIDE BY SIDE ----
c1, c2 = st.columns(2)

with c1:
    if st.button("📊 Summarize"):
        st.session_state.active_tab = "Summarize"

with c2:
    if st.button("✨ Suggest"):
        st.session_state.active_tab = "Suggest"


# =====================================================
# SUMMARIZE OPTIONS
# =====================================================
if st.session_state.active_tab == "Summarize":

    st.markdown("##### Summarize Options")

    r1c1, r1c2, r1c3 = st.columns(3)

    with r1c1:
        if st.button("Revenue"):
            selected_query = "Summarize total revenue"

    with r1c2:
        if st.button("Monthly"):
            selected_query = "Monthly sales trend"

    with r1c3:
        if st.button("Avg Order"):
            selected_query = "Average order value"

    r2c1, r2c2 = st.columns(2)

    with r2c1:
        if st.button("Top Products"):
            selected_query = "Top products by revenue"

    with r2c2:
        if st.button("Region"):
            selected_query = "Revenue by region"


# =====================================================
# SUGGEST
# =====================================================
elif st.session_state.active_tab == "Suggest":

    option = st.selectbox(
        "Suggestions",
        [
            "Select...",
            "Compare metadata from sales_fact and customer_dim",
            "Top 5 customers by sales",
            "Monthly sales trend",
        ]
    )

    if option != "Select...":
        selected_query = option


# ---- UPDATE INPUT ----
if selected_query:
    st.session_state.user_query = selected_query


# ---- INPUT ----
user_query = st.text_area(
    "",
    value=st.session_state.user_query,
    placeholder="Ask your question..."
)

run_clicked = st.button("Run Analysis")


# =====================================================
# RUN
# =====================================================
if run_clicked:

    if not user_query.strip():
        st.warning("Enter query")

    else:
        with st.spinner("Running..."):
            try:
                app = get_supervisor_app()

                result = app.invoke({
                    "messages": [HumanMessage(content=user_query)],
                    "step": 0
                })

                st.success("Done")

            except Exception as e:
                st.error("Error")
                st.exception(e)