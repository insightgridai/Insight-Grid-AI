# =============================================================
# streamlit_app.py  —  Insight Grid AI  v7
#
# FIXES:
# 1. "Could not format result" — now imports parse_response from
#    utils.parser which NEVER returns None. Raw text responses
#    are shown properly instead of that error message.
# 2. PDF chart sideways — fixed in pdf_export.py (_chart_dimensions)
# 3. Cost: memory OFF by default, max 4 exchanges kept
# 4. chart_df uses make_chart_df() for reliable numeric coercion
# =============================================================

import json
import streamlit as st
import pandas as pd
import plotly.express as px
from langchain_core.messages import AIMessage, HumanMessage

# ── Auth gate ───────────────────────────────────────────────
from auth.login_ui import show_login_popup, check_auth, logout

st.set_page_config(page_title="Insight Grid AI", page_icon="🤖", layout="wide")

if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "permissions" not in st.session_state: st.session_state.permissions = {}

if not check_auth():
    show_login_popup()
    st.stop()

# ── Imports after auth ──────────────────────────────────────
from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent   import get_followup_questions
from db.connection           import test_connection
from utils.db_store          import load_connections, save_connection
from utils.pdf_export        import create_pdf
from utils.cache             import load_bg
from utils.parser            import parse_response   # ← THE FIX: robust parser


# ── Background ─────────────────────────────────────────────
try:
    bg = load_bg("assets/backgroud6.jfif")
    bg_css = f"""
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.72),rgba(0,0,0,0.72)),
                    url("data:image/png;base64,{bg}");
        background-size:cover; background-position:center; background-attachment:fixed;
    }}"""
except Exception:
    bg_css = ".stApp{background:#0e0e1a;}"


# ── CSS ────────────────────────────────────────────────────
st.markdown(f"""
<style>
{bg_css}
textarea, input[type="text"], input[type="password"] {{
    background-color:rgba(255,255,255,0.07)!important;
    color:white!important; border-radius:8px!important;
}}
div[data-testid="stButton"] button {{ border-radius:10px; }}
div[data-testid="stButton"] button[kind="primary"] {{
    background:linear-gradient(135deg,#00b4d8,#0077b6)!important;
    border:none!important; color:white!important; font-weight:600!important;
}}
.kpi-card {{
    background:rgba(0,100,140,0.45); border:1px solid rgba(0,180,216,0.45);
    border-radius:12px; padding:16px 10px; text-align:center; min-height:86px;
}}
.kpi-value {{ font-size:1.5rem; font-weight:700; color:#48cae4; margin-bottom:4px; }}
.kpi-label {{ font-size:0.78rem; color:#90e0ef; }}
div[data-testid="stButton"] button[kind="secondary"] {{
    background:rgba(0,119,182,0.18)!important;
    border:1px solid rgba(0,180,216,0.45)!important;
    color:#90e0ef!important; width:100%; text-align:left;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
    background:rgba(0,100,140,0.3)!important;
    border:1px solid rgba(0,180,216,0.3)!important;
    color:#90e0ef!important; text-align:left; width:100%;
}}
.role-badge {{
    display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:0.75rem; font-weight:700; letter-spacing:0.05em;
}}
.role-admin   {{ background:#0077b6; color:white; }}
.role-analyst {{ background:#00b4d8; color:white; }}
.role-viewer  {{ background:#48cae4; color:#0e0e1a; }}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────
_defaults = {
    "db_connected":   False,
    "db_config":      {},
    "memory_on":      False,
    "history":        [],
    "history_pairs":  [],
    "last_response":  "",
    "last_df":        None,
    "chart_df":       None,
    "last_parsed":    None,
    "followups":      [],
    "show_popup":     False,
    "chart_path":     None,
    "last_run_query": "",
    "pending_text":   "",
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ────────────────────────────────────────────────
def make_chart_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Coerce string numbers → float so charts always render."""
    df = raw_df.copy()
    for col in df.columns:
        cleaned = (df[col].astype(str)
                   .str.replace(",", "", regex=False)
                   .str.replace("$", "", regex=False)
                   .str.replace("%", "", regex=False)
                   .str.strip())
        coerced = pd.to_numeric(cleaned, errors="coerce")
        if coerced.notna().sum() / max(len(df), 1) >= 0.6:
            df[col] = coerced
    return df


def clean_messages_for_openai(msgs):
    """Keep only valid HumanMessage/AIMessage, max last 8."""
    clean = []
    for m in msgs:
        if isinstance(m, (HumanMessage, AIMessage)):
            content = getattr(m, "content", "")
            if isinstance(content, str) and content.strip():
                clean.append(m)
    return clean[-8:]


# ── Header ─────────────────────────────────────────────────
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# ── Top bar ────────────────────────────────────────────────
c1, c2, c3 = st.columns([3, 3, 2])
with c1:
    st.toggle("🧠 Memory Mode", key="memory_on")
with c2:
    if st.session_state.db_connected:
        name = st.session_state.db_config.get("name", "")
        dbt  = st.session_state.db_config.get("db_type", "postgresql").upper()
        st.success(f"✅ {name} ({dbt})" if name else f"✅ Connected ({dbt})")
    else:
        st.warning("⚠️ Not Connected")
with c3:
    perms = st.session_state.get("permissions", {})
    if perms.get("can_connect_db", True):
        if st.button("🔌 Connect Database", use_container_width=True):
            st.session_state.show_popup = True
    else:
        st.info("🔒 Viewer role")


# ── DB Popup ───────────────────────────────────────────────
@st.dialog("Connect to Database", width="large")
def db_popup():
    tab1, tab2 = st.tabs(["✏️ Manual Entry", "💾 Saved Connections"])

    with tab1:
        conn_name = st.text_input("Connection Name", key="p_name")
        db_type   = st.selectbox(
            "Type", ["postgresql", "snowflake"], key="p_db_type",
            format_func=lambda x: "PostgreSQL" if x == "postgresql" else "Snowflake"
        )
        if db_type == "postgresql":
            host     = st.text_input("Host", key="p_host")
            port     = st.text_input("Port", key="p_port", value="5432")
            database = st.text_input("Database", key="p_database")
            user     = st.text_input("Username", key="p_user")
            password = st.text_input("Password", key="p_password", type="password")
            cfg = {"name": conn_name, "db_type": "postgresql",
                   "host": host, "port": port, "database": database,
                   "user": user, "password": password}
        else:
            account   = st.text_input("Account", key="p_account", value="dbcitil-nc64603")
            user      = st.text_input("Username", key="p_sf_user")
            password  = st.text_input("Password", key="p_sf_pwd", type="password")
            warehouse = st.text_input("Warehouse", key="p_warehouse", value="COMPUTE_WH")
            database  = st.text_input("Database", key="p_sf_db")
            schema    = st.text_input("Schema", key="p_schema", value="PUBLIC")
            role      = st.text_input("Role", key="p_role")
            cfg = {"name": conn_name, "db_type": "snowflake",
                   "account": account, "user": user, "password": password,
                   "warehouse": warehouse, "database": database,
                   "schema": schema, "role": role}

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚡ Connect Now", use_container_width=True):
                ok, msg = test_connection(cfg)
                if ok:
                    st.session_state.db_connected = True
                    st.session_state.db_config    = cfg
                    st.session_state.show_popup   = False
                    st.rerun()
                else:
                    st.error(msg)
        with col2:
            if st.button("💾 Save", use_container_width=True):
                if conn_name.strip():
                    save_connection(cfg)
                    st.success("Saved!")
                else:
                    st.warning("Enter a connection name first.")

    with tab2:
        saved = load_connections()
        if not saved:
            st.info("No saved connections.")
        else:
            names = [x["name"] for x in saved]
            sel   = st.selectbox("Select", names, key="p_sel")
            row   = next(x for x in saved if x["name"] == sel)
            for k, v in row.items():
                if k not in ("password", "name"):
                    st.markdown(f"**{k}:** `{v}`")
            if st.button("✅ Use This Connection", use_container_width=True):
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


# ── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    role  = st.session_state.get("user_role", "viewer")
    uname = st.session_state.get("user_name", "User")
    st.markdown(
        f'👤 **{uname}** &nbsp;'
        f'<span class="role-badge role-{role}">{role.upper()}</span>',
        unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        logout(); st.rerun()
    st.divider()

    st.markdown("### 💡 Suggested Questions")
    st.caption("Click → edit → Run Analysis")
    for i, s in enumerate([
        "Show top 10 customers by total revenue",
        "Monthly revenue trend for latest year",
        "Which product category has highest sales",
        "Show bottom 5 performing products",
        "Average order value by region",
        "Compare revenue this year vs last year",
        "Customers not ordered in 90 days",
        "Total revenue by month for all years",
    ]):
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            st.session_state.pending_text = s
            st.rerun()

    st.divider()
    st.markdown("### 🗄️ Active Connection")
    if st.session_state.db_connected:
        cfg = st.session_state.db_config
        st.success(f"**{cfg.get('name','—')}**\n\n`{cfg.get('db_type','').upper()}`")
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.db_connected = False
            st.session_state.db_config    = {}
            st.rerun()
    else:
        st.warning("No database connected")

    if st.session_state.memory_on and st.session_state.history_pairs:
        st.divider()
        st.markdown("### 🧠 Conversation History")
        pairs = st.session_state.history_pairs
        st.caption(f"{len(pairs)} exchange(s)")
        for idx, pair in enumerate(reversed(pairs)):
            ri    = len(pairs) - 1 - idx
            label = pair['q'][:45] + ("…" if len(pair['q']) > 45 else "")
            with st.expander(f"#{ri+1} — {label}"):
                st.markdown(f"**You:** {pair['q']}")
                st.markdown(f"**Result:** {pair['a']}")
                if st.button("↩ Re-load", key=f"hist_{ri}", use_container_width=True):
                    st.session_state.pending_text = pair['q']
                    st.rerun()
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history       = []
            st.session_state.history_pairs = []
            st.rerun()


# ── Query box ──────────────────────────────────────────────
query = st.text_area(
    "💬 Ask your business question",
    height=110,
    value=st.session_state.pending_text,
    placeholder="e.g. Show top 10 customers by total revenue",
)
run_clicked = st.button("🚀 Run Analysis", type="primary")

if run_clicked and not st.session_state.get("permissions", {}).get("can_run_query", True):
    st.warning("🔒 Your role does not have permission to run queries.")
    run_clicked = False


# ── Run Analysis ───────────────────────────────────────────
if run_clicked:
    st.session_state.show_popup = False
    active_query = query.strip()

    if not active_query:
        st.warning("⚠️ Please enter a question.")
        st.stop()
    if not st.session_state.db_connected:
        st.error("❌ Connect to a database first.")
        st.stop()

    if st.session_state.memory_on and st.session_state.history:
        recent   = clean_messages_for_openai(st.session_state.history)
        messages = recent + [HumanMessage(content=active_query)]
    else:
        messages = [HumanMessage(content=active_query)]

    app = get_supervisor_app(st.session_state.db_config)

    try:
        with st.spinner("🤖 Running Agents… (Analyst → Expert → Reviewer)"):
            result = app.invoke({"messages": messages, "step": 0})

        final = ""
        for msg in reversed(result.get("messages", [])):
            if getattr(msg, "type", "") == "ai":
                content = getattr(msg, "content", "")
                if content and content.strip():
                    final = content
                    break

    except Exception as e:
        err = str(e).lower()
        if "rate" in err or "429" in err:
            st.error("⚠️ **OpenAI Rate Limit.** Wait 60s then try again, or add credits at platform.openai.com → Billing.")
        elif "badrequest" in err or "400" in err:
            st.error("⚠️ **Request error.** Turn off Memory Mode and try again.")
            st.session_state.history       = []
            st.session_state.history_pairs = []
        else:
            st.error(f"⚠️ Error: {str(e)[:300]}")
        st.stop()

    if not final:
        st.warning("⚠️ No response received. Please try again.")
        st.stop()

    st.session_state.last_response  = final
    st.session_state.last_run_query = active_query
    st.session_state.chart_path     = None
    st.session_state.pending_text   = active_query

    # ── parse_response from utils.parser — NEVER returns None ──
    parsed = parse_response(final)
    st.session_state.last_parsed = parsed

    if parsed.get("type") == "table":
        raw_df = pd.DataFrame(
            parsed.get("data", []),
            columns=parsed.get("columns", [])
        )
        st.session_state.last_df  = raw_df
        st.session_state.chart_df = make_chart_df(raw_df)
    else:
        st.session_state.last_df  = None
        st.session_state.chart_df = None

    try:
        st.session_state.followups = get_followup_questions(active_query)
    except Exception:
        st.session_state.followups = [
            "Show top 5 by revenue",
            "Show monthly trend",
            "Compare this year vs last year",
            "Show bottom 5 performers",
        ]

    if st.session_state.memory_on:
        st.session_state.history.append(HumanMessage(content=active_query))
        st.session_state.history.append(AIMessage(content=final))
        if len(st.session_state.history) > 8:
            st.session_state.history = st.session_state.history[-8:]
        a_text = ""
        if parsed:
            if parsed.get("type") == "text":
                a_text = parsed.get("content", final)[:150]
            else:
                cols   = parsed.get("columns", [])
                rows   = parsed.get("data",    [])
                a_text = f"{len(rows)} rows — {', '.join(cols[:3])}"
        st.session_state.history_pairs.append({"q": active_query, "a": a_text})
        if len(st.session_state.history_pairs) > 8:
            st.session_state.history_pairs = st.session_state.history_pairs[-8:]


# ── KPI Cards ──────────────────────────────────────────────
parsed = st.session_state.last_parsed
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
                    f'</div>', unsafe_allow_html=True)
        st.markdown("")

if parsed and isinstance(parsed, dict) and parsed.get("summary"):
    st.info(f"💡 {parsed['summary']}")


# ── Data table ─────────────────────────────────────────────
if st.session_state.last_df is not None:
    st.subheader("📊 Structured Result")
    st.dataframe(st.session_state.last_df, use_container_width=True)
    if st.session_state.get("permissions", {}).get("can_download", True):
        csv = st.session_state.last_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV (Power BI)",
            data=csv,
            file_name="insight_data.csv",
            mime="text/csv"
        )


# ── Visualization ──────────────────────────────────────────
if st.session_state.chart_df is not None:
    cdf      = st.session_state.chart_df
    num_cols = cdf.select_dtypes(include="number").columns.tolist()
    all_cols = cdf.columns.tolist()

    # Last-resort: force-coerce the last column if still no numerics
    if not num_cols and all_cols:
        last_col = all_cols[-1]
        cdf[last_col] = pd.to_numeric(
            cdf[last_col].astype(str)
                .str.replace(",", "", regex=False).str.strip(),
            errors="coerce"
        )
        st.session_state.chart_df = cdf
        num_cols = cdf.select_dtypes(include="number").columns.tolist()

    if num_cols:
        st.subheader("📈 Interactive Visualization")
        vc1, vc2, vc3 = st.columns(3)
        with vc1:
            chart_type = st.selectbox(
                "Chart Type",
                ["Bar","Horizontal Bar","Line","Area","Pie","Donut","Treemap","Scatter"],
                key="viz_chart_type"
            )
        with vc2:
            val_col = st.selectbox(
                "Value (metric)", num_cols,
                index=len(num_cols)-1, key="viz_value_col"
            )
        with vc3:
            lbl_options = [c for c in all_cols if c != val_col] or all_cols
            lbl_col     = st.selectbox("Label / Group", lbl_options, key="viz_label_col")

        title = f"{val_col} by {lbl_col}"
        fig   = None

        if   chart_type == "Bar":
            fig = px.bar(cdf, x=lbl_col, y=val_col, color=val_col,
                         color_continuous_scale="Blues", title=title, text_auto=True)
        elif chart_type == "Horizontal Bar":
            fig = px.bar(cdf, x=val_col, y=lbl_col, orientation="h", color=val_col,
                         color_continuous_scale="Teal", title=title, text_auto=True)
        elif chart_type == "Line":
            fig = px.line(cdf, x=lbl_col, y=val_col, markers=True, title=title)
        elif chart_type == "Area":
            fig = px.area(cdf, x=lbl_col, y=val_col, title=title)
        elif chart_type == "Pie":
            fig = px.pie(cdf, names=lbl_col, values=val_col, title=title)
        elif chart_type == "Donut":
            fig = px.pie(cdf, names=lbl_col, values=val_col, hole=0.45, title=title)
        elif chart_type == "Treemap":
            fig = px.treemap(cdf, path=[lbl_col], values=val_col, title=title)
        elif chart_type == "Scatter":
            fig = px.scatter(cdf, x=lbl_col, y=val_col, color=val_col,
                             color_continuous_scale="Blues", title=title)

        if fig:
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(10,10,30,0.6)",
                font_color="white",
                title_font_color="#48cae4",
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=20, r=20, t=50, b=20)
            )
            fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)")
            fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
            st.plotly_chart(fig, use_container_width=True)

            # Save PNG for PDF — explicit 900×500 forces landscape, no rotation
            try:
                fig.write_image(
                    "chart_export.png",
                    width=900, height=500, scale=2
                )
                st.session_state.chart_path = "chart_export.png"
            except Exception:
                pass
    else:
        st.caption("ℹ️ No numeric columns found for visualization.")


# ── Text result ────────────────────────────────────────────
if (st.session_state.last_response
        and st.session_state.last_df is None
        and parsed
        and isinstance(parsed, dict)
        and parsed.get("type") == "text"):
    st.subheader("💬 Analysis Result")
    st.markdown(parsed.get("content", st.session_state.last_response))


# ── Follow-up questions ────────────────────────────────────
if st.session_state.followups:
    st.subheader("🔁 Follow-up Questions")
    st.caption("Click to load → edit → **Run Analysis**")
    fcols = st.columns(2)
    for i, q in enumerate(st.session_state.followups):
        with fcols[i % 2]:
            if st.button(q, key=f"fq_{i}", use_container_width=True):
                st.session_state.pending_text = q
                st.rerun()


# ── PDF download ───────────────────────────────────────────
if st.session_state.last_response and st.session_state.last_parsed:
    p = st.session_state.last_parsed
    if (p.get("type") in ("table", "text")
            and st.session_state.get("permissions", {}).get("can_download", True)):
        try:
            pdf_file = create_pdf(
                p,
                st.session_state.last_run_query or "",
                chart_path=st.session_state.get("chart_path")
            )
            with open(pdf_file, "rb") as f:
                st.download_button(
                    "📄 Download Report (PDF)",
                    data=f,
                    file_name="Insight_Report.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.caption(f"PDF note: {e}")
