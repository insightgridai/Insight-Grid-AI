import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from langchain_core.messages import HumanMessage, AIMessage
import base64
import os
import re

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


# =====================================================
# ONLY REPLACE YOUR GLOBAL STYLES BLOCK WITH THIS
# KEEP FULL REMAINING CODE SAME
# =====================================================

st.markdown(
    f"""
    <style>
    /* ---- Background ---- */
    .stApp {{
        background:
            linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.65)),
            url("data:image/png;base64,{bg_img}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .block-container {{
        padding-top: 2rem;
    }}

    /* ---- Textarea ---- */
    textarea {{
        background-color: rgba(255,255,255,0.06) !important;
        color: white !important;
        border: 1px solid rgba(0,200,255,0.25) !important;
        border-radius: 8px !important;
    }}

    /* =====================================================
       ALL NORMAL BUTTONS = ROBOT IMAGE BLUE COLOR
       ===================================================== */
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {{
        background

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
    # conversation_history: list of dicts {role, content, df}
    "conversation_history": [],
    "memory_mode": "With Memory",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -------------------------------------------------
# PERFORMANCE: cache supervisor app per db_config
# -------------------------------------------------
@st.cache_resource(show_spinner=False)
def _build_supervisor(config_key: str, config: dict):
    return get_supervisor_app(config)


def get_cached_supervisor():
    cfg = st.session_state.db_config
    key = json.dumps(cfg, sort_keys=True)
    return _build_supervisor(key, cfg)


# -------------------------------------------------
# PARSE RESPONSE
# -------------------------------------------------
def parse_response(response):
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        return json.loads(response[start:end])
    except Exception:
        return None


# -------------------------------------------------
# COLUMN TYPE DETECTOR
# -------------------------------------------------
PERCENT_HINTS = re.compile(
    r"(pct|percent|rate|ratio|share|margin|growth|yield|percentage)",
    re.IGNORECASE
)
DOLLAR_HINTS = re.compile(
    r"(revenue|sales|amount|price|cost|spend|value|income|profit|loss|gmv|arr|mrr|ltv|budget)",
    re.IGNORECASE
)
QUANTITY_HINTS = re.compile(
    r"(qty|quantity|count|units|items|orders|transactions|volume_units)",
    re.IGNORECASE
)


def detect_col_type(col_name: str, series: pd.Series):
    """Return 'percent', 'dollar', or None."""
    if PERCENT_HINTS.search(col_name):
        return "percent"
    if DOLLAR_HINTS.search(col_name):
        return "dollar"
    if QUANTITY_HINTS.search(col_name):
        return None
    if pd.api.types.is_numeric_dtype(series):
        mx = series.dropna().abs().max()
        if mx is not None and 0 < mx <= 1.5:
            return "percent"
    return None


def is_already_percentage(series: pd.Series) -> bool:
    """
    True if values are already in 0–100 scale (e.g. 9.75, 10.2).
    False if values are in 0–1 decimal ratio (e.g. 0.0975).
    """
    mx = series.dropna().abs().max()
    if mx is None:
        return False
    return mx > 1.5


# -------------------------------------------------
# RESULT TABLE with correct % formatting
# -------------------------------------------------
def show_result_table(df: pd.DataFrame):
    """
    Render dataframe. For percentage columns:
      - If values are already 0-100 scale (e.g. 9.75) → show as "9.75 %"
      - If values are 0-1 decimal (e.g. 0.0975) → multiply ×100, show as "9.75 %"
    For dollar columns → show as "$ 1,234.56"
    """
    df = df.copy()
    col_config = {}

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        ct = detect_col_type(col, df[col])

        if ct == "dollar":
            col_config[col] = st.column_config.NumberColumn(
                col,
                help="💲 Dollar / Revenue metric",
                format="$ %,.2f",
            )

        elif ct == "percent":
            already_pct = is_already_percentage(df[col])
            if not already_pct:
                # Convert 0.0975 → 9.75
                df[col] = df[col] * 100
            col_config[col] = st.column_config.NumberColumn(
                col,
                help="📊 Percentage metric",
                format="%.2f %%",
            )
        # quantity / other → no special config

    st.dataframe(df, use_container_width=True, column_config=col_config)


# -------------------------------------------------
# BUILD MESSAGES WITH CONVERSATION CONTEXT
# -------------------------------------------------
def build_messages_with_context(current_query: str) -> list:
    """
    With Memory: inject last N turns as a context block so the LLM
    can resolve follow-up references like 'those customers', 'that product'.
    Without Memory: bare query only.
    """
    if st.session_state.memory_mode == "Without Memory":
        return [HumanMessage(content=current_query)]

    history = st.session_state.conversation_history
    if not history:
        return [HumanMessage(content=current_query)]

    # Take last 6 turns (3 Q&A pairs) to keep token count low
    recent = history[-6:]
    context_lines = []
    for turn in recent:
        role_label = "User" if turn["role"] == "user" else "Assistant"
        content = turn["content"]
        if turn.get("df") is not None and not turn["df"].empty:
            # Attach a small row preview so the LLM can reference actual values
            df_preview = turn["df"].head(5).to_string(index=False)
            content = f"{content}\n[Data preview:\n{df_preview}]"
        context_lines.append(f"{role_label}: {content}")

    context_block = "\n".join(context_lines)

    full_prompt = (
        "Previous conversation (use to resolve follow-up references like "
        "'those customers', 'that region', 'the same period'):\n"
        f"---\n{context_block}\n---\n\n"
        f"Current question: {current_query}"
    )

    return [HumanMessage(content=full_prompt)]


# -------------------------------------------------
# SMART SUGGESTIONS
# -------------------------------------------------
SMART_SUGGESTIONS = [
    "Top 10 customers by revenue",
    "Monthly sales trend this year",
    "Revenue by product category",
    "Compare this year vs last year",
    "Which region has highest growth?",
    "Bottom 5 performing products",
    "Customer churn rate",
    "Average order value by segment",
]


def render_smart_suggestions():
    st.markdown(
        "<span style='color:rgba(255,255,255,0.45);font-size:0.76rem;'>"
        "⚡ Quick Suggestions</span>",
        unsafe_allow_html=True
    )
    cols = st.columns(4)
    for idx, suggestion in enumerate(SMART_SUGGESTIONS):
        with cols[idx % 4]:
            st.markdown('<div class="quickchip">', unsafe_allow_html=True)
            if st.button(suggestion, key=f"smart_{idx}"):
                st.session_state.pending_query = suggestion
                st.session_state.auto_run = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


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
                    name = file.replace(".json", "")
                    saved_connections[name] = data
                except Exception:
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
                    "host": host, "port": port,
                    "database": database, "user": user, "password": pwd
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
                    "host": host, "port": port,
                    "database": database, "user": user, "password": pwd
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
# TOP BAR: Memory toggle + Connect DB
# -------------------------------------------------
col_title, col_mem, col_conn = st.columns([5, 3, 2])

with col_conn:
    if st.button("🔌 Connect DB"):
        db_popup()

with col_mem:
    memory_choice = st.radio(
        "🧠 Memory",
        ["With Memory", "Without Memory"],
        index=0 if st.session_state.memory_mode == "With Memory" else 1,
        horizontal=True,
        key="memory_radio"
    )
    if memory_choice != st.session_state.memory_mode:
        st.session_state.memory_mode = memory_choice
        if memory_choice == "Without Memory":
            # Clear history when switching to no-memory mode
            st.session_state.conversation_history = []

if st.session_state.db_connected:
    st.success("Connected ✅")
else:
    st.warning("Not Connected")


# -------------------------------------------------
# CONVERSATION HISTORY PANEL (With Memory only)
# -------------------------------------------------
if (
    st.session_state.memory_mode == "With Memory"
    and st.session_state.conversation_history
):
    with st.expander(
        f"🕐 Conversation History  ({len(st.session_state.conversation_history)} turns)",
        expanded=False
    ):
        btn_col = st.columns([7, 1])
        with btn_col[1]:
            if st.button("🗑 Clear", key="clear_history"):
                st.session_state.conversation_history = []
                st.session_state.last_df = None
                st.session_state.last_response = ""
                st.session_state.chart_df = None
                st.session_state.followups = []
                st.rerun()

        for turn in st.session_state.conversation_history:
            if turn["role"] == "user":
                st.markdown(
                    f'<div class="chat-user">'
                    f'<div class="chat-label">You</div>'
                    f'{turn["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                preview = turn["content"]
                if turn.get("df") is not None and not turn["df"].empty:
                    r, c = turn["df"].shape
                    preview = f"[Table: {r} rows × {c} cols]  {turn['content'][:80]}"
                st.markdown(
                    f'<div class="chat-ai">'
                    f'<div class="chat-label">AI</div>'
                    f'{preview}</div>',
                    unsafe_allow_html=True
                )


# -------------------------------------------------
# APPLY FOLLOWUP QUERY
# -------------------------------------------------
if st.session_state.pending_query:
    st.session_state.query_text = st.session_state.pending_query
    st.session_state.pending_query = ""


# -------------------------------------------------
# SMART SUGGESTIONS
# -------------------------------------------------
render_smart_suggestions()


# -------------------------------------------------
# QUERY BOX
# -------------------------------------------------
query = st.text_area(
    "Ask your business question",
    height=90,
    key="query_text",
    placeholder="e.g. Show top 10 customers for latest year"
)

run = st.button("🚀 Run Analysis")


# -------------------------------------------------
# VISUALS
# -------------------------------------------------
def infer_plotly_fmt(col_name: str, series: pd.Series) -> tuple:
    """Returns (format_string, suffix_label)."""
    ct = detect_col_type(col_name, series)
    if ct == "dollar":
        return "$,.2f", ""
    if ct == "percent":
        return ".2f", " %"
    return ",.0f", ""


def show_visual(df: pd.DataFrame):
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return None

    value_col = num_cols[-1]
    non_num = [c for c in df.columns if c not in num_cols]
    label_col = non_num[0] if non_num else df.columns[0]

    fmt, suffix = infer_plotly_fmt(value_col, df[value_col])

    chart = st.selectbox(
        "Choose Visual",
        ["Bar", "Line", "Pie", "Treemap"],
        key="chart_selector"
    )

    neon_colors = [
        "#00C8FF", "#0080CC", "#00FFD4", "#7B2FFF",
        "#FF6B35", "#FFD700", "#00FF88", "#FF3CAC",
        "#36D1DC", "#5B86E5"
    ]

    fig = None

    if chart == "Bar":
        fig = px.bar(
            df, x=label_col, y=value_col,
            color=label_col,
            color_discrete_sequence=neon_colors,
            template="plotly_dark",
            title=f"{value_col} by {label_col}",
        )
        fig.update_traces(
            hovertemplate=(
                f"<b>%{{x}}</b><br>{value_col}: %{{y:{fmt}}}{suffix}<extra></extra>"
            )
        )
        fig.update_layout(
            clickmode="event+select",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

    elif chart == "Line":
        fig = px.line(
            df, x=label_col, y=value_col,
            template="plotly_dark",
            title=f"{value_col} trend",
            markers=True,
            color_discrete_sequence=["#00C8FF"],
        )
        fig.update_traces(
            hovertemplate=(
                f"<b>%{{x}}</b><br>{value_col}: %{{y:{fmt}}}{suffix}<extra></extra>"
            ),
            line=dict(width=3),
            marker=dict(size=8, color="#00C8FF",
                        line=dict(width=2, color="#fff"))
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

    elif chart == "Pie":
        fig = px.pie(
            df, names=label_col, values=value_col,
            color_discrete_sequence=neon_colors,
            template="plotly_dark",
            title=f"{value_col} distribution",
            hole=0.35,
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                f"<b>%{{label}}</b><br>"
                f"{value_col}: %{{value:{fmt}}}{suffix}<br>"
                f"Share: %{{percent}}<extra></extra>"
            ),
            pull=[0.05] * len(df),
        )
        fig.update_layout(
            clickmode="event+select",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

    else:  # Treemap
        fig = px.treemap(
            df, path=[label_col], values=value_col,
            color=value_col,
            color_continuous_scale=["#003366", "#00C8FF", "#00FFD4"],
            template="plotly_dark",
            title=f"{value_col} treemap",
        )
        fig.update_traces(
            hovertemplate=(
                f"<b>%{{label}}</b><br>"
                f"{value_col}: %{{value:{fmt}}}{suffix}<extra></extra>"
            ),
            textfont=dict(size=14),
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

    # Drill-down on click
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        key="main_chart"
    )

    if event and event.get("selection") and event["selection"].get("points"):
        pts = event["selection"]["points"]
        selected_labels = [p.get("label") or p.get("x") for p in pts]
        if selected_labels:
            filtered = df[
                df[label_col].astype(str).isin([str(s) for s in selected_labels])
            ]
            if not filtered.empty:
                st.markdown(
                    f"**🔍 Drill-down: {', '.join(str(s) for s in selected_labels)}**"
                )
                show_result_table(filtered)

    return fig


# -------------------------------------------------
# RUN QUERY
# -------------------------------------------------
should_run = run or st.session_state.auto_run

if should_run:
    st.session_state.auto_run = False

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

    current_query = st.session_state.query_text.strip()
    if not current_query:
        st.warning("Please enter a question.")
        st.stop()

    with st.spinner("Running AI Agents..."):

        app = get_cached_supervisor()

        messages = build_messages_with_context(current_query)

        result = app.invoke({
            "messages": messages,
            "step": 0
        })

        final_text = ""
        for msg in reversed(result["messages"]):
            if getattr(msg, "type", "") == "ai":
                final_text = msg.content
                break

        st.session_state.last_response = final_text

        parsed = parse_response(final_text)
        result_df = None

        if parsed:
            if parsed["type"] == "table":
                result_df = pd.DataFrame(
                    parsed["data"], columns=parsed["columns"]
                )
                st.session_state.last_df = result_df
                st.session_state.chart_df = result_df
            elif parsed["type"] == "text":
                st.session_state.last_df = None
                st.session_state.chart_df = None

        # Save to conversation history (With Memory only)
        if st.session_state.memory_mode == "With Memory":
            st.session_state.conversation_history.append({
                "role": "user",
                "content": current_query,
                "df": None,
            })

            if result_df is not None:
                ai_summary = f"Returned table: {result_df.shape[0]} rows, columns: {', '.join(result_df.columns.tolist())}"
            elif parsed and parsed.get("type") == "text":
                ai_summary = parsed.get("content", "")[:150]
            else:
                ai_summary = final_text[:150]

            st.session_state.conversation_history.append({
                "role": "ai",
                "content": ai_summary,
                "df": result_df,
            })

            # Keep bounded: last 20 entries = 10 Q&A pairs
            if len(st.session_state.conversation_history) > 20:
                st.session_state.conversation_history = (
                    st.session_state.conversation_history[-20:]
                )

        # Follow-up suggestions
        st.session_state.followups = get_followup_questions(current_query)


# -------------------------------------------------
# RESULT TABLE
# -------------------------------------------------
if st.session_state.last_df is not None:
    st.subheader("📊 Result")
    show_result_table(st.session_state.last_df)


# -------------------------------------------------
# VISUAL CHART
# -------------------------------------------------
fig = None

if st.session_state.chart_df is not None:
    st.subheader("📈 Interactive Visual")
    fig = show_visual(st.session_state.chart_df)


# -------------------------------------------------
# FOLLOWUP QUESTIONS — transparent, no color
# -------------------------------------------------
if st.session_state.followups:
    st.markdown(
        "<span style='color:rgba(255,255,255,0.4);font-size:0.76rem;'>"
        "💬 Follow-up suggestions</span>",
        unsafe_allow_html=True
    )
    cols = st.columns(min(len(st.session_state.followups), 3))
    for i, q in enumerate(st.session_state.followups):
        with cols[i % len(cols)]:
            st.markdown('<div class="followup-btn">', unsafe_allow_html=True)
            if st.button(q, key=f"fq_{i}"):
                st.session_state.pending_query = q
                st.session_state.auto_run = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


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

        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, f"Query: {st.session_state.query_text}")
        pdf.ln(5)

        if parsed["type"] == "table":
            columns = parsed["columns"]
            data = parsed["data"]
            col_width = 190 / max(len(columns), 1)

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
                except Exception:
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
