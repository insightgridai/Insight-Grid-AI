import streamlit as st
from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app

st.set_page_config(page_title="Insight Grid AI", layout="wide")

# Create layout columns
left_col, center_col, right_col = st.columns([1, 2.5, 1])

# =========================
# LEFT COLUMN – DB TEST
# =========================
with left_col:
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
# CENTER COLUMN – AGENT
# =========================
with center_col:
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

# Right column intentionally empty (for balance / future use)
with right_col:
    pass
