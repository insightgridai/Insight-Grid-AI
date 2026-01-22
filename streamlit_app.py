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
        background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)),
        url("data:image/png;base64,{bg_image}");
        background-size: cover;
        background-attachment: fixed;
    }}

    .chatbar {{
        display: flex;
        align-items: center;
        background: #2b2b2b;
        border-radius: 16px;
        padding: 10px 14px;
        gap: 10px;
    }}

    .chat-input {{
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: white;
        font-size: 16px;
    }}

    .mic-btn {{
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        color: white;
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

st.markdown("---")

# =====================================================
# AUDITOR AGENT
# =====================================================
st.title("📊 Auditor Agent")

# =====================================================
# CHATGPT-STYLE INPUT BAR
# =====================================================
components.html(
    """
    <div class="chatbar">
        <input id="chatInput" class="chat-input" placeholder="Ask anything..." />
        <button class="mic-btn" onclick="startDictation()">🎤</button>
    </div>

    <script>
    function startDictation() {
        const rec = new webkitSpeechRecognition();
        rec.lang = "en-US";
        rec.interimResults = false;

        rec.onresult = function(e) {
            const text = e.results[0][0].transcript;
            document.getElementById("chatInput").value = text;
            document.getElementById("hiddenInput").value = text;
            document.getElementById("hiddenInput")
              .dispatchEvent(new Event("change", {{ bubbles: true }}));
        };
        rec.start();
    }

    document.getElementById("chatInput").addEventListener("input", function(e) {
        document.getElementById("hiddenInput").value = e.target.value;
        document.getElementById("hiddenInput")
          .dispatchEvent(new Event("change", {{ bubbles: true }}));
    });
    </script>
    """,
    height=90,
)

# =====================================================
# HIDDEN STREAMLIT INPUT (SYNC BRIDGE)
# =====================================================
hidden_value = st.text_input(
    "",
    key="hiddenInput",
    label_visibility="collapsed"
)

if hidden_value:
    st.session_state.query = hidden_value

# =====================================================
# RUN ANALYSIS
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
