import streamlit as st
import pandas as pd
import json
import plotly.express as px
from fpdf import FPDF
from langchain_core.messages import HumanMessage, AIMessage
import base64
import os

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent import get_followup_questions
from db.connection import get_db_connection_dynamic


# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# -------------------------------------------------
# BACKGROUND IMAGE
# -------------------------------------------------
def get_base64_image(image_path):
    with open(image_path, "rb") as img:
        return base64.b64encode(img.read()).decode()


bg_img = get_base64_image("assets/backgroud6.jfif")


# -------------------------------------------------
# GLOBAL CSS
# -------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp {{
        background:
            linear-gradient(rgba(0,0,0,0.70), rgba(0,0,0,0.70)),
            url("data:image/png;base64,{bg_img}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        font-family: 'Sora', sans-serif;
    }}

    .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

    /* ── Welcome ── */
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(28px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    .welcome-eyebrow {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        letter-spacing: 4px;
        text-transform: uppercase;
        color: #c8a96e;
        margin-bottom: 10px;
        opacity: 0.8;
        text-align: center;
    }}

    .welcome-title {{
        font-size: clamp(2rem, 5vw, 3.2rem);
        font-weight: 700;
        color: #f0d9a8;
        text-align: center;
        line-height: 1.15;
        margin-bottom: 6px;
        letter-spacing: -0.5px;
        animation: fadeInUp 0.7s ease both;
    }}

    .welcome-subtitle {{
        font-size: 15px;
        color: rgba(255,255,255,0.42);
        text-align: center;
        margin-bottom: 36px;
        font-weight: 300;
        animation: fadeInUp 0.8s ease 0.1s both;
    }}

    /* ── Main header ── */
    .main-title {{ font-size: 1.5rem; font-weight: 700; color: #f0d9a8; }}
    .main-caption {{
        font-size: 11px;
        color: rgba(255,255,255,0.38);
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1px;
    }}

    /* ── Memory badge ── */
    .memory-badge {{
        font-size: 11px; padding: 3px 10px;
        border-radius: 20px; font-weight: 600;
    }}
    .memory-on  {{ background: #1db954; color: white; }}
    .memory-off {{ background: #666;    color: white; }}
    .memory-toggle-container {{
        display: flex; align-items: center; gap: 8px;
        padding: 6px 14px;
        background: rgba(255,255,255,0.06);
        border-radius: 30px;
        border: 1px solid rgba(255,255,255,0.12);
        width: fit-content; margin-bottom: 1rem;
        font-size: 13px; color: rgba(255,255,255,0.6);
    }}

    /* ── Chat bubbles ── */
    .chat-bubble-user {{
        background: rgba(100,149,237,0.18);
        border-left: 3px solid #6495ED;
        padding: 10px 14px; border-radius: 8px;
        margin: 6px 0; font-size: 14px; color: #dce8ff;
    }}
    .chat-bubble-ai {{
        background: rgba(255,255,255,0.06);
        border-left: 3px solid #c8a96e;
        padding: 10px 14px; border-radius: 8px;
        margin: 6px 0; font-size: 14px; color: #eee;
    }}

    /* ── Streamlit overrides ── */
    div[data-testid="stButton"] button {{
        border-radius: 10px;
        font-family: 'Sora', sans-serif;
    }}
    textarea {{
        background-color: rgba(255,255,255,0.05) !important;
        color: white !important;
        font-family: 'Sora', sans-serif !important;
        border: none !important;
    }}
    div[data-testid="stTextArea"] label {{
        color: rgba(255,255,255,0.5) !important;
        font-size: 13px !important;
    }}
    #MainMenu, footer {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
defaults = {
    "db_connected": False,
    "db_config": {},
    "last_df": None,
    "last_response": "",
    "followups": [],
    "chart_df": None,
    "query_text": "",
    "pending_query": "",
    "auto_run": False,
    "memory_enabled": True,
    "conversation_history": [],
    "memory_messages": [],
    "screen": "welcome",
    "active_category": "All",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -------------------------------------------------
# SUGGESTION DATA
# -------------------------------------------------
CATEGORIES = ["All", "Analyze", "Find", "Summarize", "Suggest"]

SUGGESTIONS = {
    "All": [
        ("📊", "Top 10 customers by revenue this year"),
        ("📈", "Monthly sales trend for last 12 months"),
        ("🏆", "Best performing products by profit margin"),
        ("🌍", "Revenue breakdown by region"),
        ("⚠️",  "Show orders with delivery delays > 7 days"),
        ("💰", "Compare Q1 vs Q2 revenue this year"),
        ("👥", "New vs returning customers last quarter"),
        ("📦", "Low stock products below reorder level"),
    ],
    "Analyze": [
        ("📊", "Top 10 customers by revenue this year"),
        ("💰", "Compare Q1 vs Q2 revenue this year"),
        ("📈", "Monthly sales trend for last 12 months"),
        ("🏆", "Best performing products by profit margin"),
    ],
    "Find": [
        ("⚠️",  "Show orders with delivery delays > 7 days"),
        ("📦", "Low stock products below reorder level"),
        ("🔍", "Find duplicate customer records"),
        ("🛑", "Find cancelled orders this month"),
    ],
    "Summarize": [
        ("🗂️", "Summarize overall business performance"),
        ("🌍", "Revenue breakdown by region"),
        ("👥", "New vs returning customers last quarter"),
        ("📋", "Weekly sales summary for last 4 weeks"),
    ],
    "Suggest": [
        ("💡", "Suggest ways to improve customer retention"),
        ("🚀", "Suggest upsell opportunities based on data"),
        ("📉", "Suggest cost-saving areas from expense data"),
        ("🎯", "Suggest target customers for new campaign"),
    ],
}


# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def parse_response(response):
    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        return json.loads(response[start:end])
    except:
        return None


def build_agent_messages(current_query: str):
    if st.session_state.memory_enabled and st.session_state.memory_messages:
        msgs = list(st.session_state.memory_messages)
        msgs.append(HumanMessage(content=current_query))
        return msgs
    return [HumanMessage(content=current_query)]


def run_query(query_str: str):
    if not st.session_state.db_connected:
        st.error("Please connect to a database first.")
        return

    st.session_state.screen     = "main"
    st.session_state.query_text = query_str

    with st.spinner("Running AI Agents…"):
        app    = get_supervisor_app(st.session_state.db_config)
        result = app.invoke({
            "messages": build_agent_messages(query_str),
            "step": 0
        })

        final_text = ""
        for msg in reversed(result["messages"]):
            if getattr(msg, "type", "") == "ai":
                final_text = msg.content
                break

        st.session_state.last_response = final_text

        if st.session_state.memory_enabled:
            st.session_state.conversation_history += [
                {"role": "user", "content": query_str},
                {"role": "ai",   "content": final_text},
            ]
            st.session_state.memory_messages += [
                HumanMessage(content=query_str),
                AIMessage(content=final_text),
            ]
        else:
            st.session_state.conversation_history = []
            st.session_state.memory_messages      = []

        parsed = parse_response(final_text)
        if parsed:
            if parsed["type"] == "table":
                df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
                st.session_state.last_df  = df
                st.session_state.chart_df = df
            elif parsed["type"] == "text":
                st.session_state.last_df  = None
                st.session_state.chart_df = None

        if st.session_state.memory_enabled and st.session_state.conversation_history:
            ctx = " | ".join(
                t["content"][:120]
                for t in st.session_state.conversation_history[-4:]
            )
            followup_input = f"{ctx} | {query_str}"
        else:
            followup_input = query_str

        st.session_state.followups = get_followup_questions(followup_input)


def show_visual(df):
    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        return None
    value_col = num_cols[-1]
    label_col = [c for c in df.columns if c != value_col][0]

    chart = st.selectbox("Choose Visual", ["Bar", "Line", "Pie", "Treemap"],
                         key="chart_selector")
    if chart == "Bar":
        fig = px.bar(df, x=label_col, y=value_col,
                     color_discrete_sequence=["#c8a96e"])
    elif chart == "Line":
        fig = px.line(df, x=label_col, y=value_col)
    elif chart == "Pie":
        fig = px.pie(df, names=label_col, values=value_col)
    else:
        fig = px.treemap(df, path=[label_col], values=value_col)

    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig, use_container_width=True)
    return fig


# -------------------------------------------------
# DB POPUP
# -------------------------------------------------
@st.dialog("Connect to Database")
def db_popup():
    credential_folder = "credentials"
    saved_connections = {}

    if os.path.exists(credential_folder):
        for file in os.listdir(credential_folder):
            if file.endswith(".json"):
                try:
                    with open(os.path.join(credential_folder, file), "r") as f:
                        data = json.load(f)
                    saved_connections[file.replace(".json", "")] = data
                except:
                    pass

    options  = ["Manual Entry"] + list(saved_connections.keys())
    selected = st.selectbox("Saved Connections", options)

    host = ""; port = "5432"; database = ""; user = ""; pwd = ""
    if selected != "Manual Entry":
        cfg      = saved_connections[selected]
        host     = cfg.get("host", "")
        port     = str(cfg.get("port", "5432"))
        database = cfg.get("database", "")
        user     = cfg.get("user", "")
        pwd      = cfg.get("password", "")

    st.markdown("### Edit Connection")
    host     = st.text_input("Host",     value=host)
    port     = st.text_input("Port",     value=port)
    database = st.text_input("Database", value=database)
    user     = st.text_input("Username", value=user)
    pwd      = st.text_input("Password", value=pwd, type="password")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔌 Connect Now", use_container_width=True):
            try:
                config = {"host": host, "port": port,
                          "database": database, "user": user, "password": pwd}
                conn = get_db_connection_dynamic(config)
                cur  = conn.cursor(); cur.execute("SELECT 1")
                cur.close(); conn.close()
                st.session_state.db_connected = True
                st.session_state.db_config    = config
                st.success("Connected Successfully ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    with c2:
        if st.button("💾 Save / Update", use_container_width=True):
            try:
                os.makedirs(credential_folder, exist_ok=True)
                fname = database if database else "new_connection"
                with open(os.path.join(credential_folder, f"{fname}.json"), "w") as f:
                    json.dump({"host": host, "port": port, "database": database,
                               "user": user, "password": pwd}, f, indent=4)
                st.success("Saved Successfully ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))


# =================================================================
#  SCREEN: WELCOME  (Copilot-style)
# =================================================================
if st.session_state.screen == "welcome":

    # Top bar
    t1, t2 = st.columns([8, 2])
    with t2:
        if st.button("🔌 Connect DB"):
            db_popup()
    with t1:
        if st.session_state.db_connected:
            st.success("Connected ✅")
        else:
            st.warning("Not Connected")

    st.markdown("<br>", unsafe_allow_html=True)

    # Hero text
    st.markdown(
        '<div class="welcome-eyebrow">INSIGHT GRID AI</div>'
        '<div class="welcome-title">Welcome, how can I help?</div>'
        '<div class="welcome-subtitle">Ask anything about your data — powered by AI agents</div>',
        unsafe_allow_html=True
    )

    # Centered content column
    _, mid, _ = st.columns([1, 4, 1])
    with mid:

        # ── Category chips ──
        active_cat = st.radio(
            "",
            CATEGORIES,
            horizontal=True,
            index=CATEGORIES.index(st.session_state.active_category),
            key="cat_radio",
            label_visibility="collapsed"
        )
        st.session_state.active_category = active_cat

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Text input box ──
        welcome_query = st.text_area(
            "question",
            height=85,
            placeholder="e.g.  Show top 10 customers by revenue this year…",
            label_visibility="collapsed",
            key="welcome_input"
        )

        r1, r2 = st.columns([5, 1])
        with r1:
            run_btn = st.button("🚀  Run Analysis", use_container_width=True, type="primary")
        with r2:
            if st.button("✕", use_container_width=True, help="Clear"):
                st.session_state["welcome_input"] = ""
                st.rerun()

        if run_btn and welcome_query.strip():
            run_query(welcome_query.strip())
            st.rerun()
        elif run_btn:
            st.warning("Please type a question first.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Suggestion chips (2 per row) ──
        chips = SUGGESTIONS.get(active_cat, SUGGESTIONS["All"])
        pairs = [chips[i:i+2] for i in range(0, len(chips), 2)]
        for pair in pairs:
            cols = st.columns(len(pair))
            for idx, (icon, label) in enumerate(pair):
                with cols[idx]:
                    btn_label = f"{icon}  {label}"
                    if st.button(btn_label, key=f"chip_{label[:30]}", use_container_width=True):
                        run_query(label)
                        st.rerun()

    st.stop()


# =================================================================
#  SCREEN: MAIN
# =================================================================

# Handle pending follow-up
if st.session_state.pending_query:
    st.session_state.query_text    = st.session_state.pending_query
    st.session_state.pending_query = ""

if st.session_state.auto_run:
    st.session_state.auto_run = False
    run_query(st.session_state.query_text)
    st.rerun()

# ── Top bar ──
col_logo, col_mem, col_db = st.columns([4, 4, 2])

with col_logo:
    st.markdown(
        '<div class="main-title">🤖 Insight Grid AI</div>'
        '<div class="main-caption">WHERE DATA, AGENTS AND DECISIONS CONNECT</div>',
        unsafe_allow_html=True
    )

with col_mem:
    mem_choice = st.radio(
        "💬 Follow-up Mode",
        ["🧠 With Memory", "🔄 Without Memory"],
        index=0 if st.session_state.memory_enabled else 1,
        horizontal=True,
        help="With Memory: follow-ups build on prior answers.\nWithout Memory: each query is independent."
    )
    st.session_state.memory_enabled = (mem_choice == "🧠 With Memory")

with col_db:
    if st.button("🔌 Connect DB"):
        db_popup()
    if st.session_state.db_connected:
        st.success("Connected ✅")
    else:
        st.warning("Not Connected")

# Back to home
if st.button("⬅️ Back to Home"):
    st.session_state.screen = "welcome"
    st.rerun()

st.divider()

# ── Memory status ──
if st.session_state.memory_enabled:
    st.markdown(
        '<div class="memory-toggle-container"><span>Mode:</span>'
        '<span class="memory-badge memory-on">🧠 Memory ON</span></div>',
        unsafe_allow_html=True
    )
    if st.session_state.conversation_history:
        if st.button("🗑️ Clear Conversation Memory"):
            st.session_state.conversation_history = []
            st.session_state.memory_messages      = []
            st.rerun()
else:
    st.markdown(
        '<div class="memory-toggle-container"><span>Mode:</span>'
        '<span class="memory-badge memory-off">🔄 Memory OFF</span></div>',
        unsafe_allow_html=True
    )

# ── Conversation history expander ──
if st.session_state.memory_enabled and st.session_state.conversation_history:
    with st.expander("📜 Conversation History", expanded=False):
        for turn in st.session_state.conversation_history:
            if turn["role"] == "user":
                st.markdown(
                    f'<div class="chat-bubble-user">🧑 <b>You:</b> {turn["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                ph = parse_response(turn["content"])
                if ph and ph.get("type") == "table":
                    preview = (
                        f"[Table: {len(ph.get('data',[]))} rows, "
                        f"cols: {', '.join(ph.get('columns',[]))}]"
                    )
                elif ph and ph.get("type") == "text":
                    preview = ph.get("content", "")[:200]
                else:
                    preview = turn["content"][:200]
                st.markdown(
                    f'<div class="chat-bubble-ai">🤖 <b>AI:</b> {preview}</div>',
                    unsafe_allow_html=True
                )

# ── Query input ──
query = st.text_area(
    "Ask your business question",
    height=110,
    key="query_text",
    placeholder="Show top 10 customers for latest year…"
)
run = st.button("🚀 Run Analysis", type="primary")

if run:
    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()
    run_query(st.session_state.query_text)
    st.rerun()

# ── Result table ──
if st.session_state.last_df is not None:
    st.subheader("📊 Result")
    st.dataframe(st.session_state.last_df, use_container_width=True)

# ── Chart ──
fig = None
if st.session_state.chart_df is not None:
    st.subheader("📈 Interactive Visual")
    fig = show_visual(st.session_state.chart_df)

# ── Follow-up questions ──
if st.session_state.followups:
    mem_label = "🧠 Memory ON" if st.session_state.memory_enabled else "🔄 Memory OFF"
    st.subheader(f"💡 Follow-up Questions  ({mem_label})")
    if st.session_state.memory_enabled:
        st.caption("These follow-ups carry context from your previous answers.")
    else:
        st.caption("These follow-ups run as fresh, independent queries.")

    for i, q in enumerate(st.session_state.followups):
        if st.button(q, key=f"fq_{i}"):
            st.session_state.pending_query = q
            st.session_state.auto_run      = True
            st.rerun()

# ── PDF Export ──
if st.session_state.last_response:
    parsed = parse_response(st.session_state.last_response)
    if parsed:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "I", 10)
        mode_label = (
            "With Memory (contextual)"
            if st.session_state.memory_enabled
            else "Without Memory (independent)"
        )
        pdf.cell(0, 8, f"Follow-up Mode: {mode_label}", ln=True)
        pdf.ln(3)

        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, f"Query: {st.session_state.query_text}")
        pdf.ln(5)

        if parsed["type"] == "table":
            columns   = parsed["columns"]
            data      = parsed["data"]
            col_width = 190 / len(columns)

            pdf.set_font("Arial", "B", 10)
            for col in columns:
                pdf.cell(col_width, 8, str(col), border=1)
            pdf.ln()

            pdf.set_font("Arial", "", 9)
            for row in data:
                for item in row:
                    pdf.cell(col_width, 8, str(item)[:22], border=1)
                pdf.ln()

            if fig:
                try:
                    fig.write_image("chart.png")
                    pdf.ln(8)
                    pdf.image("chart.png", x=10, w=190)
                except:
                    pass

        elif parsed["type"] == "text":
            pdf.multi_cell(0, 8, parsed["content"])

        pdf.output("report.pdf")
        with open("report.pdf", "rb") as f:
            st.download_button(
                "📄 Download Report",
                data=f,
                file_name="Insight_Report.pdf",
                mime="application/pdf"
            )
