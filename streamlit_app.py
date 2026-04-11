import streamlit as st
import base64
import json
import pandas as pd
import matplotlib.pyplot as plt

from langchain_core.messages import HumanMessage
from agents.supervisor_agent import get_supervisor_app


# =====================================================
# CONFIG
# =====================================================
st.set_page_config(page_title="Insight Grid AI", layout="wide")


# =====================================================
# BACKGROUND
# =====================================================
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

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
# STATE
# =====================================================
if "user_query" not in st.session_state:
    st.session_state.user_query = ""

if "mode" not in st.session_state:
    st.session_state.mode = "summarize"

selected_query = None


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
# SUMMARIZE QUESTIONS (WITH VISUALIZATION)
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
# VISUALIZATION CONTROL (KEY LOGIC 🔥)
# =====================================================
def should_show_visualization(user_query, df):

    # Only allow visualization in summarize mode
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
# RESPONSE RENDER
# =====================================================
def render_response(response, user_query):

    try:
        parsed = json.loads(response)

        if parsed.get("type") == "table":
            df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
            st.dataframe(df)

            if should_show_visualization(user_query, df):
                st.subheader("📈 Visualization")
                auto_visualize(df, user_query)

        elif parsed.get("type") == "list":
            for item in parsed["items"]:
                st.markdown(f"- {item}")

        elif parsed.get("type") == "text":
            st.write(parsed["content"])

    except:
        st.write(response)


# =====================================================
# RUN
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