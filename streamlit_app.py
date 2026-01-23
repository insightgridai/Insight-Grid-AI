import streamlit as st
import base64
import streamlit.components.v1 as components

from db.connection import get_db_connection
from langchain_core.messages import HumanMessage
from agents.analyst_agent import get_analyst_app

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Insight Grid AI", layout="wide")

# =====================================================
# SESSION STATE
# =====================================================
if "query" not in st.session_state:
    st.session_state.query = ""

# =====================================================
# BACKGROUND IMAGE
# =====================================================
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

bg_image = get_base64_image("assets/backgroud6.jfif")

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
        background-attachment: fixed;
    }}

    /* Wrapper to position mic over textarea */
    .input-wrapper {{
        position: relative;
        width: 100%;
    }}

    .mic-overlay {{
        position: absolute;
        right: 16px;
        bottom: 14px;
        background: #0f62fe;
        color: white;
        border-radius: 50%;
        width: 42px;
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        cursor: pointer;
        z-index: 10;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# HEADER
# =====================================================
header_left, header_right = st.columns([7, 2])

with header_left:
    st.markdown(
        """
        <h3>👩‍💻 Insight Grid AI</h3>
        <p style="color:#9ca3af;">Where Data, Agents, and Decisions Connect</p>
        """,
        unsafe_allow_html=True
    )

with header_right:
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

st.markdown("<hr style='margin: 8px 0 24px 0;'>", unsafe_allow_html=True)

# =====================================================
# AUDITOR AGENT
# =====================================================
st.title("📊 Auditor Agent")
st.caption("Ask analytical questions based on the connected database")

# =====================================================
# TEXTAREA (REAL STREAMLIT INPUT)
# =====================================================
st.markdown('<div class="input-wrapper">', unsafe_allow_html=True)

user_query = st.text_area(
    "Enter your analysis question",
    key="query",
    placeholder="e.g. Give me total number of users",
    height=120
)

st.markdown(
    """
    <div class="mic-overlay" onclick="startDictation()">🎤</div>
    </div>

    <script>
    function startDictation() {
        const rec = new webkitSpeechRecognition();
        rec.lang = "en-US";
        rec.interimResults = false;

        rec.onresult = function(e) {
            const text = e.results[0][0].transcript;
            const textarea = window.parent.document.querySelector("textarea");
            if (textarea) {
                textarea.value = text;
                textarea.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }
        };
        rec.start();
    }
    </script>
    """,
    unsafe_allow_html=True
)

# =====================================================
# RUN ANALYSIS (MANUAL)
# =====================================================
if st.button("Run Analysis"):
    if not st.session_state.query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Running Auditor Agent..."):
            try:
                result = get_analyst_app().invoke(
                    {"messages": [HumanMessage(content=st.session_state.query)]}
                )
                st.success("Analysis completed")
                st.write(result["messages"][-1].content)
            except Exception as e:
                st.error("Agent failed ❌")
                st.exception(e)
