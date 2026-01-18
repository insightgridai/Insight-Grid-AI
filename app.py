import streamlit as st
from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app


# ---------------- Page config ----------------
st.set_page_config(page_title="GenAI Analyst Prototype", layout="centered")


# ---------------- DB Connectivity Test ----------------
st.title("🔌 Database Connectivity Test")
st.write("This verifies whether the app can connect to the database using parameterized config.")

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


# ---------------- Analyst Agent ----------------
st.divider()
st.title("📊 Auditor Agent")

user_query = st.text_area(
    "Enter your analysis question",
    placeholder="Analyze the data and summarize key insights"
)

if st.button("Run Analysis"):
    if not user_query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Running Analyst Agent..."):
            try:
                analyst_app = get_analyst_app()

                result = analyst_app.invoke({
                    "messages": [HumanMessage(content=user_query)]
                })

                st.success("Analysis completed ✅")
                st.write("### Insights")
                st.write(result["messages"][-1].content)

            except Exception as e:
                st.error("Agent failed ❌")
                st.exception(e)

