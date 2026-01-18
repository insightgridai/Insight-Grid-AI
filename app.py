import streamlit as st
from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app

# =====================================================
# PAGE CONFIG (MUST BE FIRST STREAMLIT COMMAND)
# =====================================================
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)

# =====================================================
# TOP HEADER (LEFT-ALIGNED, WEBSITE STYLE)
# =====================================================
st.markdown(
    """
    <div style="
        display: flex;
        align-items: center;
        padding: 12px 24px;
    ">
        <div>
            <h3 style="margin: -110;">👩‍💻 Hi User!</h3>
            <p style="margin: -150; color: #9ca3af; font-size: 14px;">
                Welcome to Insight Grid AI
            </p>
        </div>
    </div>
    <hr style="margin-top: -8px; margin-bottom: 14px;">
    """,
    unsafe_allow_html=True
)


# =====================================================
# MAIN LAYOUT (LEFT = DB | GAP | RIGHT = AUDITOR)
# =====================================================
db_col, spacer_col, agent_col = st.columns([1.2, 0.8, 3.0])

# -----------------------------------------------------
# LEFT COLUMN – DATABASE CONNECTIVITY
# -----------------------------------------------------
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

# -----------------------------------------------------
# MIDDLE COLUMN – SPACER (INTENTIONALLY EMPTY)
# -----------------------------------------------------
with spacer_col:
    st.write("")

# -----------------------------------------------------
# RIGHT COLUMN – AUDITOR AGENT
# -----------------------------------------------------
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














