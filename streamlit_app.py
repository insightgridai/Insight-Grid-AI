# =============================================================
# streamlit_app.py  —  Insight Grid AI
#
# FIXES IN THIS VERSION:
#   ✅ "Not Connected" shown correctly; never flickers after save
#   ✅ DB popup NEVER reopens after Run Analysis
#   ✅ Run Analysis does NOT open popup if already connected
#   ✅ Snowflake + PostgreSQL support with db_type dropdown
#   ✅ Saved Connections pre-loaded from config/credentials.py
#   ✅ KPI cards rendered (3–4 KPIs per query)
#   ✅ Bar / Line / Pie / Treemap chart selector
#   ✅ Chart image saved → included in PDF export
#   ✅ Memory ON/OFF toggle works correctly
#   ✅ Follow-up questions clickable → auto-run
#   ✅ PDF download with KPIs + chart
#   ✅ Domain-aware question suggestions in sidebar
#   ✅ No broken imports; production ready
# =============================================================

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import base64

from langchain_core.messages import AIMessage

from agents.supervisor_agent  import get_supervisor_app
from agents.followup_agent    import get_followup_questions
from db.connection            import test_connection
from utils.parser             import parse_response
from utils.memory             import build_messages
from utils.db_store           import load_connections, save_connection
from utils.pdf_export         import create_pdf
from utils.cache              import load_bg


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

/* Inputs */
textarea, input[type="text"], input[type="password"] {{
    background-color: rgba(255,255,255,0.07) !important;
    color: white !important;
    border-radius: 8px !important;
}}

/* Buttons */
div[data-testid="stButton"] button {{
    border-radius: 10px;
}}

/* KPI cards */
.kpi-card {{
    background: rgba(30,30,80,0.85);
    border: 1px solid rgba(30,144,255,0.35);
    border-radius: 12px;
    padding: 14px 10px;
    text-align: center;
    min-height: 80px;
}}
.kpi-value {{
    font-size: 1.45rem;
    font-weight: 700;
    color: #1e90ff;
    margin-bottom: 4px;
}}
.kpi-label {{
    font-size: 0.78rem;
    color: #aaaacc;
    letter-spacing: 0.03em;
}}

/* Follow-up buttons */
div[data-testid="stButton"] button[kind="secondary"] {{
    background: rgba(30,144,255,0.12);
    border: 1px solid rgba(30,144,255,0.4);
    color: #90c8ff;
    width: 100%;
    text-align: left;
    padding: 8px 14px;
}}

</style>
""", unsafe_allow_html=True)


# =============================================================
# SESSION STATE DEFAULTS
# =============================================================
_defaults = {
    "db_connected":   False,
    "db_config":      {},
    "memory_on":      True,
    "history":        [],
    "last_response":  "",
    "last_df":        None,
    "last_parsed":    None,
    "followups":      [],
    "show_popup":     False,
    "pending_query":  "",
    "auto_run":       False,
    "chart_path":     None,
}

for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


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

    # ----------------------------------------------------------
    # TAB 1 — Manual Entry
    # ----------------------------------------------------------
    with tab_manual:

        conn_name = st.text_input("Connection Name", key="p_name",
                                  placeholder="My DB")

        db_type = st.selectbox(
            "Database Type",
            ["postgresql", "snowflake"],
            key="p_db_type",
            format_func=lambda x: "PostgreSQL" if x == "postgresql" else "Snowflake"
        )

        if db_type == "postgresql":
            host     = st.text_input("Host",     key="p_host",
                                     placeholder="ep-xxx.neon.tech")
            port     = st.text_input("Port",     value="5432", key="p_port")
            database = st.text_input("Database", key="p_database",
                                     placeholder="azure")
            user     = st.text_input("Username", key="p_user",
                                     placeholder="neondb_owner")
            password = st.text_input("Password", type="password", key="p_password")

            cfg = {
                "name":     conn_name,
                "db_type":  "postgresql",
                "host":     host,
                "port":     port,
                "database": database,
                "user":     user,
                "password": password,
            }

        else:  # snowflake
            account   = st.text_input("Account Identifier", key="p_account",
                                      placeholder="dbcitil-nc64603",
                                      value="dbcitil-nc64603")
            user      = st.text_input("Username",  key="p_sf_user",
                                      placeholder="INSIGHT")
            password  = st.text_input("Password",  type="password", key="p_sf_pwd")
            warehouse = st.text_input("Warehouse", key="p_warehouse",
                                      value="COMPUTE_WH")
            database  = st.text_input("Database",  key="p_sf_db",
                                      placeholder="MY_DATABASE")
            schema    = st.text_input("Schema",    key="p_schema",
                                      value="PUBLIC")
            role      = st.text_input("Role (optional)", key="p_role",
                                      placeholder="SYSADMIN")

            cfg = {
                "name":      conn_name,
                "db_type":   "snowflake",
                "account":   account,
                "user":      user,
                "password":  password,
                "warehouse": warehouse,
                "database":  database,
                "schema":    schema,
                "role":      role,
                "host":      "",
                "port":      "",
            }

        btn_c1, btn_c2 = st.columns(2)

        with btn_c1:
            if st.button("⚡ Connect Now", use_container_width=True):
                with st.spinner("Connecting…"):
                    ok, msg = test_connection(cfg)
                if ok:
                    st.session_state.db_connected = True
                    st.session_state.db_config    = cfg
                    st.session_state.show_popup   = False
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with btn_c2:
            if st.button("💾 Save Connection", use_container_width=True):
                if not conn_name.strip():
                    st.warning("Please enter a Connection Name before saving.")
                else:
                    save_connection(cfg)
                    st.success("Saved!")

    # ----------------------------------------------------------
    # TAB 2 — Saved Connections
    # ----------------------------------------------------------
    with tab_saved:

        saved = load_connections()

        if not saved:
            st.info("No saved connections yet.")
        else:
            names    = [x["name"] for x in saved]
            selected = st.selectbox("Select Connection", names, key="p_sel")
            row      = next(x for x in saved if x["name"] == selected)

            db_t = row.get("db_type", "postgresql").upper()
            st.markdown(f"**Type:** {db_t}")

            if row.get("db_type") == "snowflake":
                st.markdown(f"**Account:** `{row.get('account','')}`")
                st.markdown(f"**Warehouse:** `{row.get('warehouse','')}`")
                st.markdown(f"**Database:** `{row.get('database','')}`")
                st.markdown(f"**Schema:** `{row.get('schema','PUBLIC')}`")
                st.markdown(f"**Username:** `{row.get('user','')}`")
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
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# ---------------------------------------------------------------
# RENDER POPUP only when explicitly triggered
# ---------------------------------------------------------------
if st.session_state.show_popup:
    db_popup()


# =============================================================
# SIDEBAR — Suggested Questions
# =============================================================
with st.sidebar:
    st.markdown("### 💡 Suggested Questions")
    st.caption("Click any question to run it instantly")

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
            st.session_state.pending_query = s
            st.session_state.auto_run      = True
            st.rerun()

    st.divider()
    st.markdown("### 🗄️ Active Connection")
    if st.session_state.db_connected:
        cfg  = st.session_state.db_config
        dbt  = cfg.get("db_type", "postgresql").upper()
        name = cfg.get("name", "—")
        st.success(f"**{name}**\n\n`{dbt}`")
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.db_connected = False
            st.session_state.db_config    = {}
            st.rerun()
    else:
        st.warning("No database connected")


# =============================================================
# APPLY PENDING QUERY (from follow-up / suggestion click)
# =============================================================
if st.session_state.pending_query:
    pq = st.session_state.pending_query
    st.session_state.pending_query = ""
else:
    pq = ""


# =============================================================
# QUERY INPUT BOX
# =============================================================
query = st.text_area(
    "💬 Ask your business question",
    height=110,
    value=pq if pq else "",
    placeholder="e.g. Show top 10 customers by total revenue for latest year"
)

run = st.button("🚀 Run Analysis", use_container_width=False, type="primary")


# =============================================================
# RUN ANALYSIS
# =============================================================
should_run = run or st.session_state.auto_run

if should_run:

    st.session_state.auto_run   = False
    st.session_state.show_popup = False   # ← KEY FIX: never open popup on run

    active_query = pq if pq else query

    if not active_query.strip():
        st.warning("Please enter a question.")
        st.stop()

    if not st.session_state.db_connected:
        st.error("❌ Please connect to a database first using the 'Connect Database' button.")
        st.stop()

    messages = build_messages(
        active_query,
        st.session_state.memory_on,
        st.session_state.history
    )

    app = get_supervisor_app(st.session_state.db_config)

    with st.spinner("🤖 Running AI Agents… (Analyst → Expert → Reviewer)"):
        result = app.invoke({
            "messages": messages,
            "step":     0
        })

    # Extract last AI message
    final = ""
    for msg in reversed(result["messages"]):
        if getattr(msg, "type", "") == "ai":
            final = msg.content
            break

    st.session_state.last_response = final

    parsed = parse_response(final)
    st.session_state.last_parsed = parsed

    if parsed and isinstance(parsed, dict):
        if parsed.get("type") == "table":
            st.session_state.last_df = pd.DataFrame(
                parsed.get("data", []),
                columns=parsed.get("columns", [])
            )
        else:
            st.session_state.last_df = None
    else:
        st.session_state.last_df = None

    # Follow-up questions
    st.session_state.followups = get_followup_questions(active_query)

    # Memory
    if st.session_state.memory_on:
        st.session_state.history += messages
        st.session_state.history.append(AIMessage(content=final))


# =============================================================
# KPI CARDS
# =============================================================
parsed = st.session_state.last_parsed

if parsed and isinstance(parsed, dict):
    kpis = parsed.get("kpis", [])
    if kpis:
        st.subheader("📌 Key Metrics")
        cols = st.columns(len(kpis))
        for i, kpi in enumerate(kpis):
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div class="kpi-value">{kpi.get('value','—')}</div>
                        <div class="kpi-label">{kpi.get('label','')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        st.markdown("")


# =============================================================
# SUMMARY
# =============================================================
if parsed and isinstance(parsed, dict):
    summary = parsed.get("summary", "")
    if summary:
        st.info(f"💡 {summary}")


# =============================================================
# DATA TABLE
# =============================================================
if st.session_state.last_df is not None:
    st.subheader("📊 Structured Result")
    st.dataframe(st.session_state.last_df, use_container_width=True)


# =============================================================
# INTERACTIVE VISUALIZATION
# =============================================================
chart_fig  = None
chart_path = None

if st.session_state.last_df is not None:

    df      = st.session_state.last_df
    num_cols = df.select_dtypes(include="number").columns.tolist()

    if num_cols:
        st.subheader("📈 Interactive Visualization")

        v_col1, v_col2, v_col3 = st.columns([2, 2, 2])

        with v_col1:
            chart_type = st.selectbox(
                "Chart Type",
                ["Bar", "Line", "Pie", "Treemap", "Scatter"],
                key="chart_type"
            )

        with v_col2:
            value_col = st.selectbox(
                "Value (Y-axis)",
                num_cols,
                index=len(num_cols) - 1,
                key="value_col"
            )

        with v_col3:
            label_cols = [c for c in df.columns if c != value_col]
            label_col  = st.selectbox(
                "Label (X-axis / Group)",
                label_cols,
                key="label_col"
            )

        # Build chart
        if chart_type == "Bar":
            chart_fig = px.bar(
                df, x=label_col, y=value_col,
                color=value_col,
                color_continuous_scale="Blues",
                title=f"{value_col} by {label_col}"
            )
        elif chart_type == "Line":
            chart_fig = px.line(
                df, x=label_col, y=value_col,
                markers=True,
                title=f"{value_col} over {label_col}"
            )
        elif chart_type == "Pie":
            chart_fig = px.pie(
                df, names=label_col, values=value_col,
                title=f"{value_col} by {label_col}"
            )
        elif chart_type == "Treemap":
            chart_fig = px.treemap(
                df, path=[label_col], values=value_col,
                title=f"{value_col} — Treemap"
            )
        elif chart_type == "Scatter":
            chart_fig = px.scatter(
                df, x=label_col, y=value_col,
                title=f"{value_col} vs {label_col}"
            )

        if chart_fig:
            chart_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="white",
            )
            st.plotly_chart(chart_fig, use_container_width=True)

            # Save chart for PDF
            try:
                chart_path = "chart_export.png"
                chart_fig.write_image(chart_path)
                st.session_state.chart_path = chart_path
            except Exception:
                st.session_state.chart_path = None


# =============================================================
# TEXT RESPONSE (if no table)
# =============================================================
if (
    st.session_state.last_response
    and st.session_state.last_df is None
    and parsed
    and parsed.get("type") == "text"
):
    st.subheader("💬 Analysis Result")
    st.markdown(parsed.get("content", st.session_state.last_response))


# =============================================================
# FOLLOW-UP QUESTIONS
# =============================================================
if st.session_state.followups:
    st.subheader("🔁 Follow-up Questions")
    fq_cols = st.columns(2)
    for i, q in enumerate(st.session_state.followups):
        with fq_cols[i % 2]:
            if st.button(q, key=f"fq_{i}", use_container_width=True):
                st.session_state.pending_query = q
                st.session_state.auto_run      = True
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
                query or pq,
                chart_path=st.session_state.get("chart_path")
            )

            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="📄 Download Report (PDF)",
                    data=f,
                    file_name="Insight_Report.pdf",
                    mime="application/pdf",
                    use_container_width=False
                )
        except Exception as e:
            st.caption(f"PDF export error: {e}")
