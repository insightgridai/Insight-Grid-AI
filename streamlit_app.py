import streamlit as st
import base64
import streamlit.components.v1 as components

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
# SESSION STATE (IMPORTANT)
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
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    div.stButton > button {{
        white-space: nowrap;
        padding: 0.6rem 1.1rem;
    }}

    .mic-btn {{
        background: #0f62fe;
        color: white;
        border: none;
        border-radius: 50%;
        width: 48px;
        height: 48px;
        font-size: 20px;
        cursor: pointer;
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
        <h3 style="margin-bottom:4px;">👩‍💻 Insight Grid AI</h3>
        <p style="margin-top:0; color:#9ca3af; font-size:14px;">
            Where Data, Agents, and Decisions Connect
        </p>
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
# 🎙️ CHATGPT-STYLE VOICE BUTTON
# =====================================================
components.html(
    """
    <button class="mic-btn" onclick="startDictation()">🎤</button>

    <script>
    function startDictation() {
        const recognition = new webkitSpeechRecognition();
        recognition.lang = "en-US";
        recognition.interimResults = false;

        recognition.onresult = function(event) {
            const text = event.results[0][0].transcript;
            window.parent.postMessage(
                { type: "VOICE_TEXT", text: text },
                "*"
            );
        };
        recognition.start();
    }
    </script>
    """,
    height=70,
)

# =====================================================
# CAPTURE VOICE → STREAMLIT (CRITICAL FIX)
# =====================================================
components.html(
    """
    <script>
    window.addEventListener("message", (event) => {
        if (event.data.type === "VOICE_TEXT") {
            const textarea = window.parent.document.querySelector("textarea");
            if (textarea) {
                textarea.value = event.data.text;
                textarea.dispatchEvent(new Event("input", { bubbles: true }));
            }
        }
    });
    </script>
    """,
    height=0,
)

# =====================================================
# TEXT INPUT (BOUND TO SESSION STATE)
# =====================================================
user_query = st.text_area(
    "Enter your analysis question",
    key="query",
    placeholder="e.g. Give me total number of users"
)

# =====================================================
# RUN ANALYSIS
# =====================================================
if st.button("Run Analysis"):
    if not st.session_state.query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Running Auditor Agent..."):
            try:
                analyst_app = get_analyst_app()
                result = analyst_app.invoke({
                    "messages": [HumanMessage(content=st.session_state.query)]
                })
                st.success("Analysis completed")
                st.write(result["messages"][-1].content)
            except Exception as e:
                st.error("Agent failed ❌")
                st.exception(e)
