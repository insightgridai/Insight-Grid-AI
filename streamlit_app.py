import streamlit as st
import base64
from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)

# =====================================================
# BACKGROUND IMAGE
# =====================================================
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

bg_image = get_base64_image("assets/background.png")

st.markdown(
    f"""
    <style>
    .stApp {{
        background: linear-gradient(
            rgba(0,0,0,0.55),
            rgba(0,0,0,0.55)
        ),
        url("data:image/png;base64,{bg_image}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    /* Remove Streamlit column padding */
    section[data-testid="stHorizontalBlock"] {{
        padding-left: 0 !important;
        padding-right: 0 !important;
    }}

    /* Keep buttons single line */
    div.stButton > button {{
        white-space: nowrap;
        padding: 0.6rem 1.2rem;
    }}

    /* DB success badge */
    .db-success {{
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        padding: 8px 14px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 500;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-top: 8px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# HEADER (TRUE LEFT + TRUE RIGHT)
# =====================================================
header_container = st.container()

with header_container:
    col_left, col_right = st.columns([6, 6])

    with col_left:
        st.markdown(
            """
            <h3 style="margin-bottom:4px;">Insight Grid AI</h3>
            <p style="margin-top:0; color:#9ca3af; font-size:14px;">
                Where Data, Agents, and Decisions Connect.
            </p>
            """,
            unsafe_allow_html=True
        )

    with col_right:
        st.markdown(
            "<div style='display:flex; flex-direction:column; align-items:flex-end; margin-left:auto;'>",
            unsafe_allow_html=True
        )

        if st.button("🔌 Test DB Connection"):
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
                conn.close()

                st.markdown(
                    "<div class='db-success'>✅ Database connected successfully</div>",
                    unsafe_allow_html=True
                )

            except Exception as e:
                st.error("Database connection failed ❌")
                st.exception(e)

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin: 10px 0 24px 0;'>", unsafe_allow_html=True)

# =====================================================
# AUDITOR AGENT
# =====================================================
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
