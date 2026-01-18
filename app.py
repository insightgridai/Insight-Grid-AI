import streamlit as st
import base64
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
# BACKGROUND IMAGE (LOCAL FILE – SAFE METHOD)
# =====================================================
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

bg_image = get_base64_image("assets/background.png")

st.markdown(
    f"""
    <style>
        .stApp {{
            background:
                linear-gradient(
                    rgba(0,0,0,0.95),
                    rgba(0,0,0,0.95)
                ),
                url("data:image/png;base64,{bg_image}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# TOP HEADER (LEFT-ALIGNED, CLEAN)
# =====================================================
st.markdown(
    """
    <div style="padding: 16px 24px;">
        <h3 style="margin: 0;">👩‍💻 Hi User!</h3>
        <p style="margin: 4px 0 0 0; color: #9ca3af; font-size: 14px;">
            Welcome to Insight Grid AI
        </p>
    </div>
    <hr style="margin: 12px 0 24px 0;">
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
# MIDDLE COLUMN – SPACER
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

