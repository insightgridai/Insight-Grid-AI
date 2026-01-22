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

if "voice_trigger" not in st.session_state:
    st.session_state.voice_trigger = 0

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
        background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)),
        url("data:image/png;base64,{bg_image}");
        background-size: cover;
        background-attachment: fixed;
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
st.markdown("## 👩‍💻 Insight Grid AI")
st.caption("Where Data, Agents, and Decisions Connect")
st.markdown("---")

# =====================================================
# 🎙️ VOICE BUTTON (CHATGPT STYLE)
# =====================================================
components.html(
    """
    <button class="mic-btn" onclick="startDictation()">🎤</button>

    <script>
    function startDictation() {
        const rec = new webkitSpeechRecognition();
        rec.lang = "en-US";
        rec.interimResults = false;

        rec.onresult = function(e) {
            const text = e.results[0][0].transcript;
            window.parent.postMessage(
                { type: "VOICE_TEXT", value: text },
                "*"
            );
        };
        rec.start();
    }
    </script>
    """,
    height=70,
)

# =====================================================
# JS → STREAMLIT SYNC (CRITICAL)
# =====================================================
components.html(
    """
    <script>
    window.addEventListener("message", (event) => {
        if (event.data.type === "VOICE_TEXT") {
            const input = document.getElementById("voice_input");
            input.value = event.data.value;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });
    </script>
    """,
    height=0,
)

# =====================================================
# HIDDEN INPUT (FORCE STREAMLIT RERUN)
# =====================================================
voice_value = st.text_input(
    "",
    key="voice_input",
    label_visibility="collapsed"
)

if voice_value:
    st.session_state.query = voice_value

# =====================================================
# TEXT AREA (VISIBLE, EDITABLE)
# =====================================================
user_query = st.text_area(
    "Enter your analysis question",
    value=st.session_state.query,
    placeholder="e.g. Give me total number of users"
)

# =====================================================
# RUN ANALYSIS
# =====================================================
if st.button("Run Analysis"):
    if not user_query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Running Auditor Agent..."):
            try:
                result = get_analyst_app().invoke(
                    {"messages": [HumanMessage(content=user_query)]}
                )
                st.success("Analysis completed")
                st.write(result["messages"][-1].content)
            except Exception as e:
                st.error("Agent failed ❌")
                st.exception(e)
