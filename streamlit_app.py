# =============================================================
# streamlit_app.py  —  Insight Grid AI
#
# FIXES v3:
#   ✅ Visualization always renders after analysis (root cause fixed)
#   ✅ Follow-up click ONLY fills text box — does NOT auto-run
#   ✅ Manual query edit works properly — no false "please enter question"
#   ✅ Run Analysis button = teal/cyan (not red)
#   ✅ Memory ON: last 6 msgs sent for context; capped at 20 stored
#   ✅ Memory OFF: fresh single message each time
#   ✅ box_value / fill_box pattern — clean query box management
#   ✅ viz selectbox keys stable (viz_chart_type etc) — no wipe on rerun
#   ✅ 8 chart types: Bar, H-Bar, Line, Area, Pie, Donut, Treemap, Scatter
# =============================================================

import streamlit as st
import pandas as pd
import plotly.express as px

from langchain_core.messages import AIMessage, HumanMessage

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent   import get_followup_questions
from db.connection           import test_connection
from utils.parser            import parse_response
from utils.db_store          import load_connections, save_connection
from utils.pdf_export        import create_pdf
from utils.cache             import load_bg


# =============================================================
# PAGE CONFIG
# =============================================================
st.set_page_config(
    page_title="Insight Grid AI",
    page_icon="🤖",
    layout="wide"
)


# =============================================================
# BACKGROUND
# =============================================================
try:
    bg = load_bg("assets/backgroud6.jfif")
    bg_css = f"""
    .stApp {{
        background:
            linear-gradient(rgba(0,0,0,0.72), rgba(0,0,0,0.72)),
            url("data:image/png;base64,{bg}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    """
except Exception:
    bg_css = ".stApp { background: #0e0e1a; }"


# =============================================================
# CSS
# =============================================================
st.markdown(f"""
<style>

{bg_css}

textarea, input[type="text"], input[type="password"] {{
    background-color: rgba(255,255,255,0.07) !important;
    color: white !important;
    border-radius: 8px !important;
}}

div[data-testid="stButton"] button {{
    border-radius: 10px;
}}

/* Teal primary button (Run Analysis) */
div[data-testid="stButton"] button[kind="primary"] {{
    background: linear-gradient(135deg, #00b4d8, #0077b6) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
}}
div[data-testid="stButton"] button[kind="primary"]:hover {{
    background: linear-gradient(135deg, #48cae4, #0096c7) !important;
}}

.kpi-card {{
    background: rgba(0,100,140,0.45);
    border: 1px solid rgba(0,180,216,0.45);
    border-radius: 12px;
    padding: 16px 10px;
    text-align: center;
    min-height: 86px;
}}
.kpi-value {{
    font-size: 1.5rem;
    font-weight: 700;
    color: #48cae4;
    margin-bottom: 4px;
}}
.kpi-label {{
    font-size: 0.78rem;
    color: #90e0ef;
    letter-spacing: 0.03em;
}}

/* Follow-up buttons */
div[data-testid="stButton"] button[kind="secondary"] {{
    background: rgba(0,119,182,0.18) !important;
    border: 1px solid rgba(0,180,216,0.45) !important;
    color: #90e0ef !important;
    width: 100%;
    text-align: left;
}}
div[data-testid="stButton"] button[kind="secondary"]:hover {{
    background: rgba(0,180,216,0.28) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
    background: rgba(0,100,140,0.3) !important;
    border: 1px solid rgba(0,180,216,0.3) !important;
    color: #90e0ef !important;
    text-align: left;
    width: 100%;
}}

</style>
""", unsafe_allow_html=True)


# =============================================================
# SESSION STATE
# =============================================================
_defaults = {
    "db_connected":    False,
    "db_config":       {},
    "memory_on":       True,
    "history":         [],
    "last_response":   "",
    "last_df":         None,
    "last_parsed":     None,
    "followups":       [],
    "show_popup":      False,
    "chart_path":      None,
    "box_value":       "",       # current text area content
    "fill_box":        "",       # pending fill from click (follow-up / suggestion)
    "last_run_query":  "",       # query that was last executed
}

for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =============================================================
# APPLY PENDING FILL
# — triggered by follow-up or sidebar suggestion click
# — ONLY fills the box; does NOT run analysis
# =============================================================
if st.session_state.fill_box:
    st.session_state.box_value = st.session_state.fill_box
    st.session_state.fill_box  = ""


# =============================================================
# HEADER
# =============================================================
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# =============================================================
# TOP BAR
# =============================================================
col_mem, col_status, col_btn = st.columns([3, 3, 2])

with col_mem:
    st.toggle("🧠 Memory Mode", key="memory_on")

with col_status:
    if st.session_state.db_connected:
        db_name = st.session_state.db_config.get("name", "")
        db_type = st.session_state.db_config.get("db_type", "postgresql").upper()
        label   = f"{db_name} ({db_type})" if db_name else db_type
        st.success(f"✅ Connected — {label}")
    else:
        st.warning("⚠️ Not Connected")

with col_btn:
    if st.button("🔌 Connect Database", use_container_width=True):
        st.session_state.show_popup = True


# =============================================================
# DATABASE POPUP
# =============================================================
@st.dialog("Connect to Database", width="large")
def db_popup():

    tab_manual, tab_saved = st.tabs(["✏️ Manual Entry", "💾 Saved Connections"])

    with tab_manual:
        conn_name = st.text_input("Connection Name", key="p_name", placeholder="My DB")
        db_type   = st.selectbox(
            "Database Type", ["postgresql", "snowflake"], key="p_db_type",
            format_func=lambda x: "PostgreSQL" if x == "postgresql" else "Snowflake"
        )

        if db_type == "postgresql":
            host     = st.text_input("Host",     key="p_host",     placeholder="ep-xxx.neon.tech")
            port     = st.text_input("Port",     key="p_port",     value="5432")
            database = st.text_input("Database", key="p_database", placeholder="azure")
            user     = st.text_input("Username", key="p_user",     placeholder="neondb_owner")
            password = st.text_input("Password", key="p_password", type="password")
            cfg = {"name": conn_name, "db_type": "postgresql",
                   "host": host, "port": port, "database": database,
                   "user": user, "password": password}
        else:
            account   = st.text_input("Account Identifier", key="p_account",  value="dbcitil-nc64603")
            user      = st.text_input("Username",           key="p_sf_user",  placeholder="INSIGHT")
            password  = st.text_input("Password",           key="p_sf_pwd",   type="password")
            warehouse = st.text_input("Warehouse",          key="p_warehouse", value="COMPUTE_WH")
            database  = st.text_input("Database",           key="p_sf_db",    placeholder="MY_DATABASE")
            schema    = st.text_input("Schema",             key="p_schema",   value="PUBLIC")
            role      = st.text_input("Role (optional)",    key="p_role",     placeholder="SYSADMIN")
            cfg = {"name": conn_name, "db_type": "snowflake", "account": account,
                   "user": user, "password": password, "warehouse": warehouse,
                   "database": database, "schema": schema, "role": role,
                   "host": "", "port": ""}

        c1, c2 = st.columns(2)
        with c1:
            if st.button("⚡ Connect Now", use_container_width=True):
                with st.spinner("Connecting…"):
                    ok, msg = test_connection(cfg)
                if ok:
                    st.session_state.db_connected = True
                    st.session_state.db_config    = cfg
                    st.session_state.show_popup   = False
                    st.rerun()
                else:
                    st.error(msg)
        with c2:
            if st.button("💾 Save Connection", use_container_width=True):
                if not conn_name.strip():
                    st.warning("Enter a connection name first.")
                else:
                    save_connection(cfg)
                    st.success("Saved!")

    with tab_saved:
        saved = load_connections()
        if not saved:
            st.info("No saved connections yet.")
        else:
            names    = [x["name"] for x in saved]
            selected = st.selectbox("Select Connection", names, key="p_sel")
            row      = next(x for x in saved if x["name"] == selected)
            dbt      = row.get("db_type", "postgresql").upper()
            st.markdown(f"**Type:** {dbt}")
            if dbt == "SNOWFLAKE":
                st.markdown(f"**Account:** `{row.get('account','')}`")
                st.markdown(f"**Warehouse:** `{row.get('warehouse','')}`")
            else:
                st.markdown(f"**Host:** `{row.get('host','')}`")
                st.markdown(f"**Port:** `{row.get('port','5432')}`")
            st.markdown(f"**Database:** `{row.get('database','')}`")
            st.markdown(f"**Username:** `{row.get('user','')}`")

            if st.button("✅ Use This Connection", use_container_width=True):
                with st.spinner("Connecting…"):
                    ok, msg = test_connection(row)
                if ok:
                    st.session_state.db_connected = True
                    st.session_state.db_config    = row
                    st.session_state.show_popup   = False
                    st.rerun()
                else:
                    st.error(msg)


if st.session_state.show_popup:
    db_popup()


# =============================================================
# SIDEBAR
# =============================================================
with st.sidebar:
    st.markdown("### 💡 Suggested Questions")
    st.caption("Click to fill the box → then press **Run Analysis**")

    suggestions = [
        "Show top 10 customers by total revenue",
        "What is monthly revenue trend for the latest year?",
        "Which product category has highest sales?",
        "Show bottom 5 performing products",
        "What is average order value by region?",
        "Compare revenue this year vs last year",
        "Which customers haven't ordered in 90 days?",
        "Show total revenue by month for all years",
    ]

    for i, s in enumerate(suggestions):
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            st.session_state.fill_box = s
            st.rerun()

    st.divider()
    st.markdown("### 🗄️ Active Connection")
    if st.session_state.db_connected:
        cfg  = st.session_state.db_config
        name = cfg.get("name", "—")
        dbt  = cfg.get("db_type", "postgresql").upper()
        st.success(f"**{name}**\n\n`{dbt}`")
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.db_connected = False
            st.session_state.db_config    = {}
            st.rerun()
    else:
        st.warning("No database connected")

    if st.session_state.memory_on and st.session_state.history:
        st.divider()
        st.markdown("### 🧠 Conversation History")
        count = len(st.session_state.history)
        st.caption(f"{count // 2} exchange(s) stored")
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history = []
            st.rerun()


# =============================================================
# QUERY BOX
# — value = box_value (updated by fill_box or user typing)
# — user can freely type / edit at any time
# =============================================================
query = st.text_area(
    "💬 Ask your business question",
    height=110,
    value=st.session_state.box_value,
    placeholder="e.g. Show top 10 customers by total revenue for latest year",
    key="query_widget"
)

# Sync typed value back so it survives reruns from other widgets
st.session_state.box_value = query

run_clicked = st.button("🚀 Run Analysis", type="primary")


# =============================================================
# RUN ANALYSIS  — fires ONLY on explicit button click
# =============================================================
if run_clicked:

    st.session_state.show_popup = False

    active_query = query.strip()

    if not active_query:
        st.warning("⚠️ Please type a question before running analysis.")
        st.stop()

    if not st.session_state.db_connected:
        st.error("❌ Please connect to a database first.")
        st.stop()

    # Build message list
    if st.session_state.memory_on and st.session_state.history:
        # Keep last 6 msgs (3 exchanges) to limit tokens
        recent = st.session_state.history[-6:]
        messages = recent + [HumanMessage(content=active_query)]
    else:
        messages = [HumanMessage(content=active_query)]

    app = get_supervisor_app(st.session_state.db_config)

    with st.spinner("🤖 Running AI Agents… (Analyst → Expert → Reviewer)"):
        result = app.invoke({"messages": messages, "step": 0})

    # Get final AI response
    final = ""
    for msg in reversed(result["messages"]):
        if getattr(msg, "type", "") == "ai":
            final = msg.content
            break

    st.session_state.last_response  = final
    st.session_state.last_run_query = active_query
    st.session_state.chart_path     = None   # reset chart for new result

    parsed = parse_response(final)
    st.session_state.last_parsed = parsed

    if parsed and isinstance(parsed, dict) and parsed.get("type") == "table":
        st.session_state.last_df = pd.DataFrame(
            parsed.get("data", []),
            columns=parsed.get("columns", [])
        )
    else:
        st.session_state.last_df = None

    # Follow-up questions
    st.session_state.followups = get_followup_questions(active_query)

    # Store in memory (cap at 20 messages = 10 exchanges)
    if st.session_state.memory_on:
        st.session_state.history.append(HumanMessage(content=active_query))
        st.session_state.history.append(AIMessage(content=final))
        if len(st.session_state.history) > 20:
            st.session_state.history = st.session_state.history[-20:]


# =============================================================
# ── RESULTS  (always read from session state) ──
# =============================================================
parsed = st.session_state.last_parsed


# ── KPI CARDS ──────────────────────────────────────────────
if parsed and isinstance(parsed, dict):
    kpis = parsed.get("kpis", [])
    if kpis:
        st.subheader("📌 Key Metrics")
        kpi_cols = st.columns(len(kpis))
        for i, kpi in enumerate(kpis):
            with kpi_cols[i]:
                st.markdown(
                    f'<div class="kpi-card">'
                    f'<div class="kpi-value">{kpi.get("value","—")}</div>'
                    f'<div class="kpi-label">{kpi.get("label","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        st.markdown("")


# ── SUMMARY ────────────────────────────────────────────────
if parsed and isinstance(parsed, dict):
    summary = parsed.get("summary", "")
    if summary:
        st.info(f"💡 {summary}")


# ── DATA TABLE ─────────────────────────────────────────────
if st.session_state.last_df is not None:
    st.subheader("📊 Structured Result")
    st.dataframe(st.session_state.last_df, use_container_width=True)


# ── INTERACTIVE VISUALIZATION ──────────────────────────────
# FIX: Read df from session state, use stable widget keys (viz_*)
# so selectbox values survive rerun without being wiped.
if st.session_state.last_df is not None:

    df       = st.session_state.last_df
    all_cols = df.columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()

    if num_cols:
        st.subheader("📈 Interactive Visualization")

        vc1, vc2, vc3 = st.columns([2, 2, 2])

        with vc1:
            chart_type = st.selectbox(
                "Chart Type",
                ["Bar", "Horizontal Bar", "Line", "Area",
                 "Pie", "Donut", "Treemap", "Scatter"],
                key="viz_chart_type"
            )
        with vc2:
            value_col = st.selectbox(
                "Value (metric)",
                num_cols,
                index=len(num_cols) - 1,
                key="viz_value_col"
            )
        with vc3:
            cat_cols  = [c for c in all_cols if c != value_col] or all_cols
            label_col = st.selectbox(
                "Label / Group",
                cat_cols,
                key="viz_label_col"
            )

        chart_fig = None
        title_str = f"{value_col} by {label_col}"

        if chart_type == "Bar":
            chart_fig = px.bar(
                df, x=label_col, y=value_col,
                color=value_col, color_continuous_scale="Blues",
                title=title_str, text_auto=True
            )
        elif chart_type == "Horizontal Bar":
            chart_fig = px.bar(
                df, x=value_col, y=label_col,
                orientation="h",
                color=value_col, color_continuous_scale="Teal",
                title=title_str, text_auto=True
            )
        elif chart_type == "Line":
            chart_fig = px.line(
                df, x=label_col, y=value_col,
                markers=True, title=title_str
            )
        elif chart_type == "Area":
            chart_fig = px.area(
                df, x=label_col, y=value_col,
                title=title_str
            )
        elif chart_type == "Pie":
            chart_fig = px.pie(
                df, names=label_col, values=value_col,
                title=title_str
            )
        elif chart_type == "Donut":
            chart_fig = px.pie(
                df, names=label_col, values=value_col,
                hole=0.45, title=title_str
            )
        elif chart_type == "Treemap":
            chart_fig = px.treemap(
                df, path=[label_col], values=value_col,
                title=title_str
            )
        elif chart_type == "Scatter":
            chart_fig = px.scatter(
                df, x=label_col, y=value_col,
                size=value_col, color=value_col,
                color_continuous_scale="Blues",
                title=title_str
            )

        if chart_fig is not None:
            chart_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(10,10,30,0.6)",
                font_color="white",
                title_font_color="#48cae4",
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=20, r=20, t=50, b=20),
            )
            chart_fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)")
            chart_fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")

            st.plotly_chart(chart_fig, use_container_width=True)

            # Save for PDF
            try:
                cp = "chart_export.png"
                chart_fig.write_image(cp)
                st.session_state.chart_path = cp
            except Exception:
                pass


# ── TEXT RESULT (no table) ────────────────────────────────
if (
    st.session_state.last_response
    and st.session_state.last_df is None
    and parsed
    and isinstance(parsed, dict)
    and parsed.get("type") == "text"
):
    st.subheader("💬 Analysis Result")
    st.markdown(parsed.get("content", st.session_state.last_response))


# =============================================================
# FOLLOW-UP QUESTIONS
# — click fills box only; user presses Run Analysis to execute
# =============================================================
if st.session_state.followups:
    st.subheader("🔁 Follow-up Questions")
    st.caption("Click any question to load it → then press **Run Analysis**")
    fq_cols = st.columns(2)
    for i, q in enumerate(st.session_state.followups):
        with fq_cols[i % 2]:
            if st.button(q, key=f"fq_{i}", use_container_width=True):
                st.session_state.fill_box  = q
                st.session_state.box_value = q
                st.rerun()


# =============================================================
# PDF DOWNLOAD
# =============================================================
if st.session_state.last_response and st.session_state.last_parsed:
    p = st.session_state.last_parsed
    if p.get("type") in ("table", "text"):
        try:
            pdf_file = create_pdf(
                p,
                st.session_state.last_run_query or query,
                chart_path=st.session_state.get("chart_path")
            )
            with open(pdf_file, "rb") as f:
                st.download_button(
                    "📄 Download Report (PDF)",
                    data=f,
                    file_name="Insight_Report.pdf",
                    mime="application/pdf",
                )
        except Exception as e:
            st.caption(f"PDF note: {e}")
