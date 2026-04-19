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
    layout="wide"
)


# -------------------------------------------------
# BACKGROUND IMAGE
# -------------------------------------------------
def get_base64_image(image_path):
    with open(image_path, "rb") as img:
        return base64.b64encode(img.read()).decode()


bg_img = get_base64_image("assets/backgroud6.jfif")

st.markdown(
    f"""
    <style>
    .stApp {{
        background:
            linear-gradient(
                rgba(0,0,0,0.65),
                rgba(0,0,0,0.65)
            ),
            url("data:image/png;base64,{bg_img}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .block-container {{
        padding-top: 2rem;
    }}

    div[data-testid="stButton"] button {{
        border-radius: 10px;
    }}

    textarea {{
        background-color: rgba(255,255,255,0.06) !important;
        color: white !important;
    }}

    /* Memory toggle pill styling */
    .memory-toggle-container {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        background: rgba(255,255,255,0.07);
        border-radius: 30px;
        border: 1px solid rgba(255,255,255,0.15);
        width: fit-content;
        margin-bottom: 1rem;
    }}

    .memory-badge {{
        font-size: 12px;
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: 600;
    }}

    .memory-on {{
        background: #1db954;
        color: white;
    }}

    .memory-off {{
        background: #888;
        color: white;
    }}

    /* Chat history styling */
    .chat-bubble-user {{
        background: rgba(100, 149, 237, 0.2);
        border-left: 3px solid #6495ED;
        padding: 10px 14px;
        border-radius: 8px;
        margin: 6px 0;
        font-size: 14px;
        color: #dce8ff;
    }}

    .chat-bubble-ai {{
        background: rgba(255,255,255,0.06);
        border-left: 3px solid #aaa;
        padding: 10px 14px;
        border-radius: 8px;
        margin: 6px 0;
        font-size: 14px;
        color: #eee;
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------------------------------------
# HEADER
# -------------------------------------------------
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


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
    # Memory feature
    "memory_enabled": True,
    "conversation_history": [],   # list of {"role": "user"|"ai", "content": str}
    "memory_messages": [],        # LangChain message objects for agent
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -------------------------------------------------
# PARSE RESPONSE
# -------------------------------------------------
def parse_response(response):
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        return json.loads(response[start:end])
    except:
        return None


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
                    with open(
                        os.path.join(credential_folder, file), "r"
                    ) as f:
                        data = json.load(f)
                    name = file.replace(".json", "")
                    saved_connections[name] = data
                except:
                    pass

    options = ["Manual Entry"] + list(saved_connections.keys())
    selected = st.selectbox("Saved Connections", options)

    host = ""
    port = "5432"
    database = ""
    user = ""
    pwd = ""

    if selected != "Manual Entry":
        cfg = saved_connections[selected]
        host = cfg.get("host", "")
        port = str(cfg.get("port", "5432"))
        database = cfg.get("database", "")
        user = cfg.get("user", "")
        pwd = cfg.get("password", "")

    st.markdown("### Edit Connection")
    host = st.text_input("Host", value=host)
    port = st.text_input("Port", value=port)
    database = st.text_input("Database", value=database)
    user = st.text_input("Username", value=user)
    pwd = st.text_input("Password", value=pwd, type="password")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("🔌 Connect Now", use_container_width=True):
            try:
                config = {
                    "host": host,
                    "port": port,
                    "database": database,
                    "user": user,
                    "password": pwd
                }
                conn = get_db_connection_dynamic(config)
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                st.session_state.db_connected = True
                st.session_state.db_config = config
                st.success("Connected Successfully ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    with c2:
        if st.button("💾 Save / Update", use_container_width=True):
            try:
                if not os.path.exists(credential_folder):
                    os.makedirs(credential_folder)
                filename = database if database else "new_connection"
                save_data = {
                    "host": host,
                    "port": port,
                    "database": database,
                    "user": user,
                    "password": pwd
                }
                with open(
                    os.path.join(credential_folder, f"{filename}.json"), "w"
                ) as f:
                    json.dump(save_data, f, indent=4)
                st.success("Saved Successfully ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))


# -------------------------------------------------
# TOP BAR  (DB connect + Memory Toggle)
# -------------------------------------------------
col_left, col_mid, col_right = st.columns([5, 3, 2])

with col_right:
    if st.button("🔌 Connect DB"):
        db_popup()

with col_mid:
    # Memory toggle using a radio styled as a pill switcher
    memory_choice = st.radio(
        "💬 Follow-up Mode",
        options=["🧠 With Memory", "🔄 Without Memory"],
        index=0 if st.session_state.memory_enabled else 1,
        horizontal=True,
        help=(
            "With Memory: follow-up questions build on previous answers (like ChatGPT).\n"
            "Without Memory: each question is treated as a fresh, independent query."
        )
    )
    st.session_state.memory_enabled = (memory_choice == "🧠 With Memory")

with col_left:
    if st.session_state.db_connected:
        st.success("Connected ✅")
    else:
        st.warning("Not Connected")

# Show memory status badge
if st.session_state.memory_enabled:
    st.markdown(
        '<div class="memory-toggle-container">'
        '<span>Conversation Mode:</span>'
        '<span class="memory-badge memory-on">🧠 Memory ON — follow-ups carry context</span>'
        '</div>',
        unsafe_allow_html=True
    )
    # Clear memory button shown only when memory is on
    if st.session_state.conversation_history:
        if st.button("🗑️ Clear Conversation Memory"):
            st.session_state.conversation_history = []
            st.session_state.memory_messages = []
            st.success("Memory cleared.")
            st.rerun()
else:
    st.markdown(
        '<div class="memory-toggle-container">'
        '<span>Conversation Mode:</span>'
        '<span class="memory-badge memory-off">🔄 Memory OFF — each query is independent</span>'
        '</div>',
        unsafe_allow_html=True
    )


# -------------------------------------------------
# CONVERSATION HISTORY DISPLAY (Memory mode only)
# -------------------------------------------------
if st.session_state.memory_enabled and st.session_state.conversation_history:
    with st.expander("📜 Conversation History", expanded=False):
        for turn in st.session_state.conversation_history:
            if turn["role"] == "user":
                st.markdown(
                    f'<div class="chat-bubble-user">🧑 <b>You:</b> {turn["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                # Show a short summary for AI turns (avoid dumping raw JSON)
                parsed = parse_response(turn["content"])
                if parsed and parsed.get("type") == "table":
                    preview = f"[Table: {len(parsed.get('data', []))} rows, columns: {', '.join(parsed.get('columns', []))}]"
                elif parsed and parsed.get("type") == "text":
                    preview = parsed.get("content", turn["content"])[:200]
                else:
                    preview = turn["content"][:200]
                st.markdown(
                    f'<div class="chat-bubble-ai">🤖 <b>AI:</b> {preview}</div>',
                    unsafe_allow_html=True
                )


# -------------------------------------------------
# APPLY FOLLOWUP (pending query from button click)
# -------------------------------------------------
if st.session_state.pending_query:
    st.session_state.query_text = st.session_state.pending_query
    st.session_state.pending_query = ""


# -------------------------------------------------
# QUERY BOX
# -------------------------------------------------
query = st.text_area(
    "Ask your business question",
    height=120,
    key="query_text",
    placeholder="Show top 10 customers for latest year"
)

run = st.button("🚀 Run Analysis")


# -------------------------------------------------
# VISUALS
# -------------------------------------------------
def show_visual(df):
    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        return None

    value_col = num_cols[-1]
    label_col = [c for c in df.columns if c != value_col][0]

    chart = st.selectbox(
        "Choose Visual",
        ["Bar", "Line", "Pie", "Treemap"],
        key="chart_selector"
    )

    if chart == "Bar":
        fig = px.bar(df, x=label_col, y=value_col)
    elif chart == "Line":
        fig = px.line(df, x=label_col, y=value_col)
    elif chart == "Pie":
        fig = px.pie(df, names=label_col, values=value_col)
    else:
        fig = px.treemap(df, path=[label_col], values=value_col)

    st.plotly_chart(fig, use_container_width=True)
    return fig


# -------------------------------------------------
# BUILD MESSAGES FOR AGENT
# -------------------------------------------------
def build_agent_messages(current_query: str):
    """
    With Memory ON  → prepend full conversation history as LangChain messages.
    With Memory OFF → only the current query, no history.
    """
    if st.session_state.memory_enabled and st.session_state.memory_messages:
        # Replay prior messages so the agent has full context
        messages = list(st.session_state.memory_messages)
        messages.append(HumanMessage(content=current_query))
    else:
        messages = [HumanMessage(content=current_query)]
    return messages


# -------------------------------------------------
# RUN QUERY
# -------------------------------------------------
should_run = run or st.session_state.auto_run

if should_run:
    st.session_state.auto_run = False

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

    with st.spinner("Running AI Agents..."):

        app = get_supervisor_app(st.session_state.db_config)

        # Build message list depending on memory mode
        agent_messages = build_agent_messages(st.session_state.query_text)

        result = app.invoke({
            "messages": agent_messages,
            "step": 0
        })

        final_text = ""
        for msg in reversed(result["messages"]):
            if getattr(msg, "type", "") == "ai":
                final_text = msg.content
                break

        st.session_state.last_response = final_text

        # ------------------------------------------
        # UPDATE MEMORY
        # ------------------------------------------
        if st.session_state.memory_enabled:
            # Append to human-readable history for display
            st.session_state.conversation_history.append({
                "role": "user",
                "content": st.session_state.query_text
            })
            st.session_state.conversation_history.append({
                "role": "ai",
                "content": final_text
            })
            # Append LangChain message objects for agent replay
            st.session_state.memory_messages.append(
                HumanMessage(content=st.session_state.query_text)
            )
            st.session_state.memory_messages.append(
                AIMessage(content=final_text)
            )
        else:
            # Memory OFF — discard any history
            st.session_state.conversation_history = []
            st.session_state.memory_messages = []

        # ------------------------------------------
        # PARSE RESULT
        # ------------------------------------------
        parsed = parse_response(final_text)

        if parsed:
            if parsed["type"] == "table":
                df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
                st.session_state.last_df = df
                st.session_state.chart_df = df
            elif parsed["type"] == "text":
                st.session_state.last_df = None
                st.session_state.chart_df = None

        # ------------------------------------------
        # FOLLOW-UP QUESTIONS
        # Include conversation context when memory is on
        # ------------------------------------------
        if st.session_state.memory_enabled and st.session_state.conversation_history:
            # Pass last few exchanges as context so follow-ups are relevant
            context_summary = " | ".join([
                t["content"][:120]
                for t in st.session_state.conversation_history[-4:]
            ])
            followup_input = f"{context_summary} | {st.session_state.query_text}"
        else:
            followup_input = st.session_state.query_text

        st.session_state.followups = get_followup_questions(followup_input)


# -------------------------------------------------
# RESULT TABLE
# -------------------------------------------------
if st.session_state.last_df is not None:
    st.subheader("📊 Result")
    st.dataframe(st.session_state.last_df, use_container_width=True)


# -------------------------------------------------
# VISUAL CHART
# -------------------------------------------------
fig = None

if st.session_state.chart_df is not None:
    st.subheader("📈 Interactive Visual")
    fig = show_visual(st.session_state.chart_df)


# -------------------------------------------------
# FOLLOWUP QUESTIONS
# -------------------------------------------------
if st.session_state.followups:
    mem_label = "🧠 Memory ON" if st.session_state.memory_enabled else "🔄 Memory OFF"
    st.subheader(f"💡 Follow-up Questions  ({mem_label})")

    if st.session_state.memory_enabled:
        st.caption(
            "These follow-ups will remember your previous answers. "
            "Click any to continue the conversation."
        )
    else:
        st.caption(
            "These follow-ups will run as fresh, independent queries with no prior context."
        )

    for i, q in enumerate(st.session_state.followups):
        if st.button(q, key=f"fq_{i}"):
            st.session_state.pending_query = q
            st.session_state.auto_run = True
            st.rerun()


# -------------------------------------------------
# PDF EXPORT
# -------------------------------------------------
if st.session_state.last_response:

    parsed = parse_response(st.session_state.last_response)

    if parsed:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)
        pdf.ln(5)

        # Show memory mode in report
        pdf.set_font("Arial", "I", 10)
        mode_label = "With Memory (contextual)" if st.session_state.memory_enabled else "Without Memory (independent)"
        pdf.cell(0, 8, f"Follow-up Mode: {mode_label}", ln=True)
        pdf.ln(3)

        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, f"Query: {st.session_state.query_text}")
        pdf.ln(5)

        if parsed["type"] == "table":
            columns = parsed["columns"]
            data = parsed["data"]
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
