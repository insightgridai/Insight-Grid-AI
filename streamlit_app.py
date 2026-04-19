import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from langchain_core.messages import HumanMessage
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

# -------------------------------------------------
# NEON BLUE THEME + GLOBAL STYLES
# Neon blue: #00C8FF  glow: rgba(0,200,255,0.55)
# -------------------------------------------------
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

    /* ---- ALL Buttons → Neon Blue ---- */
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {{
        background: linear-gradient(135deg, #00C8FF 0%, #0080CC 100%) !important;
        color: #000 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: 0 0 10px #00C8FF, 0 0 22px rgba(0,200,255,0.5) !important;
        transition: box-shadow 0.2s ease, transform 0.1s ease !important;
    }}

    div[data-testid="stButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {{
        box-shadow: 0 0 18px #00C8FF, 0 0 40px rgba(0,200,255,0.8) !important;
        transform: translateY(-1px) !important;
    }}

    div[data-testid="stButton"] button:active,
    div[data-testid="stDownloadButton"] button:active {{
        transform: translateY(0px) !important;
    }}

    /* ---- Textarea ---- */
    textarea {{
        background-color: rgba(255,255,255,0.06) !important;
        color: white !important;
    }}

    /* ---- Suggestion chips (follow-up buttons) ---- */
    .suggestion-chip button {{
        background: rgba(0,200,255,0.12) !important;
        border: 1px solid #00C8FF !important;
        color: #00C8FF !important;
        font-size: 0.82rem !important;
        padding: 4px 12px !important;
        box-shadow: 0 0 6px rgba(0,200,255,0.3) !important;
    }}

    .suggestion-chip button:hover {{
        background: rgba(0,200,255,0.25) !important;
        box-shadow: 0 0 14px rgba(0,200,255,0.6) !important;
    }}

    /* ---- Smart suggestion pill row ---- */
    .smart-suggestions {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 6px 0 14px 0;
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
    # cache the supervisor app so it isn't rebuilt every rerun
    "_supervisor_app": None,
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
# COLUMN TYPE DETECTOR  (for tooltips / formatting)
# -------------------------------------------------
PERCENT_HINTS = re.compile(
    r"(pct|percent|rate|ratio|share|margin|growth|yield)",
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
    # heuristic: if numeric and max < 1.5, likely a ratio
    if pd.api.types.is_numeric_dtype(series):
        mx = series.dropna().abs().max()
        if mx is not None and 0 < mx <= 1.5:
            return "percent"
    return None


def format_value(val, col_type):
    if col_type == "dollar":
        try:
            return f"${val:,.2f}"
        except Exception:
            return str(val)
    if col_type == "percent":
        try:
            v = float(val)
            if v <= 1.5:
                return f"{v*100:.2f}%"
            return f"{v:.2f}%"
        except Exception:
            return str(val)
    return val


# -------------------------------------------------
# SMART SUGGESTIONS (static pool — extend as needed)
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
    st.markdown("**💡 Quick Suggestions:**")
    cols = st.columns(4)
    for idx, suggestion in enumerate(SMART_SUGGESTIONS):
        with cols[idx % 4]:
            if st.button(suggestion, key=f"smart_{idx}"):
                st.session_state.pending_query = suggestion
                st.session_state.auto_run = True
                st.rerun()


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
# TOP BAR
# -------------------------------------------------
c1, c2 = st.columns([8, 2])

with c2:
    if st.button("🔌 Connect to DataBase"):
        db_popup()

if st.session_state.db_connected:
    st.success("Connected Successfully ✅")
else:
    st.warning("Not Connected")


# -------------------------------------------------
# APPLY FOLLOWUP
# -------------------------------------------------
if st.session_state.pending_query:
    st.session_state.query_text = st.session_state.pending_query
    st.session_state.pending_query = ""


# -------------------------------------------------
# SMART SUGGESTIONS ROW
# -------------------------------------------------
render_smart_suggestions()


# -------------------------------------------------
# QUERY BOX
# -------------------------------------------------
query = st.text_area(
    "Ask your business question",
    height=100,
    key="query_text",
    placeholder="Show top 10 customers for latest year"
)

run = st.button("🚀 Run Analysis")


# -------------------------------------------------
# VISUALS  (enhanced: drill-down click, tooltips)
# -------------------------------------------------
def infer_col_format(col_name: str, series: pd.Series) -> str:
    """Return plotly hovertemplate format token."""
    ct = detect_col_type(col_name, series)
    if ct == "dollar":
        return "$,.2f"
    if ct == "percent":
        # Check if values already in 0-100 range
        mx = series.dropna().abs().max()
        if mx and mx > 2:
            return ".2f%"    # e.g. 9.75 → shown as 9.75%
        return ".2%"         # e.g. 0.0975 → shown as 9.75%
    return ","


def show_visual(df):

    num_cols = df.select_dtypes(include="number").columns.tolist()

    if len(num_cols) == 0:
        return None

    value_col = num_cols[-1]
    label_col = [c for c in df.columns if c != value_col][0]

    col_type = detect_col_type(value_col, df[value_col])
    fmt = infer_col_format(value_col, df[value_col])

    chart = st.selectbox(
        "Choose Visual",
        ["Bar", "Line", "Pie", "Treemap"],
        key="chart_selector"
    )

    # ---- Neon blue color palette ----
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
            hovertemplate=f"<b>%{{x}}</b><br>{value_col}: %{{y:{fmt}}}<extra></extra>"
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
            hovertemplate=f"<b>%{{x}}</b><br>{value_col}: %{{y:{fmt}}}<extra></extra>",
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
            hole=0.35,          # donut style — more modern
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=f"<b>%{{label}}</b><br>{value_col}: %{{value:{fmt}}}<br>Share: %{{percent}}<extra></extra>",
            pull=[0.05] * len(df),   # slight pull on all slices
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
            hovertemplate=f"<b>%{{label}}</b><br>{value_col}: %{{value:{fmt}}}<extra></extra>",
            textfont=dict(size=14),
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

    # ---- Drill-down: show filtered table on click ----
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        key="main_chart"
    )

    # Handle click selection
    if event and event.get("selection") and event["selection"].get("points"):
        selected_points = event["selection"]["points"]
        selected_labels = [p.get("label") or p.get("x") for p in selected_points]
        if selected_labels:
            filtered = df[df[label_col].astype(str).isin(
                [str(s) for s in selected_labels]
            )]
            if not filtered.empty:
                st.markdown(
                    f"**🔍 Drill-down: {', '.join(str(s) for s in selected_labels)}**"
                )
                st.dataframe(filtered, use_container_width=True)

    return fig


# -------------------------------------------------
# RESULT TABLE  (with smart column tooltips)
# -------------------------------------------------
def show_result_table(df: pd.DataFrame):
    """Render the dataframe with header tooltips showing unit type."""

    # Build column config for st.dataframe
    col_config = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            ct = detect_col_type(col, df[col])
            if ct == "dollar":
                col_config[col] = st.column_config.NumberColumn(
                    col,
                    help="💲 Dollar / Revenue metric",
                    format="$ %.2f",
                )
            elif ct == "percent":
                mx = df[col].dropna().abs().max()
                if mx and mx > 2:
                    col_config[col] = st.column_config.NumberColumn(
                        col,
                        help="📊 Percentage metric",
                        format="%.2f %%",
                    )
                else:
                    col_config[col] = st.column_config.NumberColumn(
                        col,
                        help="📊 Percentage metric",
                        format="%.2%",
                    )
            # quantity → no special format

    st.dataframe(df, use_container_width=True, column_config=col_config)


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

        # Use cached supervisor app (performance boost)
        app = get_cached_supervisor()

        result = app.invoke({
            "messages": [HumanMessage(content=st.session_state.query_text)],
            "step": 0
        })

        final_text = ""
        for msg in reversed(result["messages"]):
            if getattr(msg, "type", "") == "ai":
                final_text = msg.content
                break

        st.session_state.last_response = final_text

        parsed = parse_response(final_text)

        if parsed:
            if parsed["type"] == "table":
                df = pd.DataFrame(parsed["data"], columns=parsed["columns"])
                st.session_state.last_df = df
                st.session_state.chart_df = df
            elif parsed["type"] == "text":
                st.session_state.last_df = None
                st.session_state.chart_df = None

        # Run follow-up generation in background (don't block result display)
        st.session_state.followups = get_followup_questions(
            st.session_state.query_text
        )


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
# FOLLOWUP QUESTIONS  (pill-style buttons)
# -------------------------------------------------
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")
    cols = st.columns(min(len(st.session_state.followups), 3))

    for i, q in enumerate(st.session_state.followups):
        with cols[i % len(cols)]:
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
