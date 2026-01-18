import streamlit as st
from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app

st.set_page_config(page_title="Insight Grid AI", layout="wide")

# Greeting section (TOP)
col1, col2 = st.columns([0.15, 0.85])
with col1:
    st.markdown("👋")
with col2:
    st.markdown("### Hi User!")
    st.caption("Welcome to Insight Grid AI")

st.markdown("---")  # optional divider


# Create layout with spacer
db_col, spacer_col, agent_col = st.columns([1.2, 0.6, 2.8])

# =========================
# LEFT – DB CONNECTIVITY
# =========================
with db_col:
    st.subheader("🔌 Database Connectivity Test")
    st.caption("Verifies database connectivity using parameterized configuration.")

    if st.button("Test Database Connection"):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()
            st.success("Database connected successfully ✅")
        except Exception as e:
            st.error("Database connection failed ❌")
            st.exception(e)

# =========================
# SPACER – EMPTY COLUMN
# =========================
with spacer_col:
    st.write("")

# =========================
# RIGHT – AUDITOR AGENT
# =========================
with agent_col:
    st.title("📊 Auditor Agent")
    st.caption("Ask analytical questions based on the connected database")

    user_query = st.text_area(
        "Enter your analysis question",
        placeholder="e.g. Give me total number of users"
    )

    if st.button("Run Analysis"):
        if not user_query.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Running Auditor Agent..."):
                try:
                    analyst_app = get_analyst_app()
                    result = analyst_app.invoke({
                        "messages": [HumanMessage(content=user_query)]
                    })
                    st.success("Analysis completed")
                    st.write(result["messages"][-1].content)
                except Exception as e:
                    st.error("Agent failed ❌")
                    st.exception(e)

