import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import io
from fpdf import FPDF
from langchain_core.messages import AIMessage, HumanMessage

# ── Auth — runs before anything else ───────────────────────
from auth.login_ui import show_login_popup, check_auth, logout

st.set_page_config(page_title="Insight Grid AI", page_icon="🤖", layout="wide")

if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "permissions" not in st.session_state: st.session_state.permissions = {}

if not check_auth():
    show_login_popup()
    st.stop()

# ── Imports (only after auth) ───────────────────────────────
from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent   import get_followup_questions
from db.connection           import test_connection
from utils.db_store          import load_connections, save_connection
from utils.pdf_export        import create_pdf
from utils.cache             import load_bg
from utils.parser            import parse_response


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
.anomaly-high {{ color:#ff6b6b; font-weight:700; }}
.anomaly-low  {{ color:#ffd93d; font-weight:700; }}
.confidence-bar {{
    background:rgba(0,180,216,0.2); border-radius:8px;
    padding:8px 14px; margin-bottom:8px;
    border-left:4px solid #48cae4;
}}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────
_defaults = {
    "db_connected":       False,
    "db_config":          {},
    "memory_on":          False,
    "history":            [],
    "history_pairs":      [],
    "last_response":      "",
    "last_df":            None,
    "chart_df":           None,
    "last_parsed":        None,
    "followups":          [],
    "show_popup":         False,
    "chart_path":         None,
    "last_run_query":     "",
    "pending_text":       "",
    # NEW: for compare mode
    "compare_mode":       False,
    "compare_query1":     "",
    "compare_query2":     "",
    "compare_df1":        None,
    "compare_df2":        None,
    "compare_parsed1":    None,
    "compare_parsed2":    None,
    # NEW: session query log for history export
    "query_log":          [],
    # NEW: chart theme
    "chart_theme":        "Dark",
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Suggestions per DB type ─────────────────────────────────
POSTGRESQL_SUGGESTIONS = [
    "Show top 10 customers by total revenue",
    "Which product category has highest total sales",
    "Show monthly revenue trend for 2021",
    "Show bottom 5 performing products by revenue",
    "Show total sales by payment type cash vs card",
    "Which stores have highest sales in 2021",
    "Show top 10 items by quantity sold",
    "What is total revenue by month for all years",
    "Show customer count by division",
    "Which bank is used most for card payments",
    "Show daily sales trend for January 2021",
    "What are top 5 suppliers by total sales",
    "Show revenue comparison by store district",
    "Show average order value by store division",
    "Which customers have made more than 5 orders",
]
SNOWFLAKE_SUGGESTIONS = [
    "Show total oil production by field for all time",
    "What is total gas production by location type",
    "Show top 10 wells by oil production BBL",
    "Show monthly oil production trend for 2025",
    "Compare onshore vs offshore vs deepwater production",
    "Show total water production by field name",
    "Which wells have status Producing right now",
    "Show average API gravity by location",
    "What is total oil production for year 2025",
    "Show wells with highest water cut percentage",
    "Compare oil production by field for 2025",
    "Show count of wells by current status",
    "What is average oil production per well",
    "Show total production by month for Krishna Basin",
    "Which wells had highest gas production in 2025",
]

def get_suggestions() -> list:
    if st.session_state.db_connected:
        if st.session_state.db_config.get("db_type","postgresql").lower() == "snowflake":
            return SNOWFLAKE_SUGGESTIONS
    return POSTGRESQL_SUGGESTIONS


# ── Helpers ────────────────────────────────────────────────
def make_chart_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    for col in df.columns:
        cleaned = (df[col].astype(str)
                   .str.replace(",", "", regex=False)
                   .str.replace("$", "", regex=False)
                   .str.replace("%", "", regex=False)
                   .str.strip())
        coerced = pd.to_numeric(cleaned, errors="coerce")
        if coerced.notna().any():
            df[col] = coerced
    return df


def clean_history(msgs):
    clean = []
    for m in msgs:
        if isinstance(m, (HumanMessage, AIMessage)):
            c = getattr(m, "content", "")
            if isinstance(c, str) and c.strip():
                clean.append(m)
    return clean[-4:]


# ── NEW FEATURE 1: Chart theme colours ────────────────────
CHART_THEMES = {
    "Dark":       {"paper": "rgba(0,0,0,0)",     "plot": "rgba(10,10,30,0.6)",  "font": "white",   "title": "#48cae4", "scale": "Blues"},
    "Light":      {"paper": "rgba(255,255,255,1)","plot": "rgba(240,245,255,1)", "font": "#1a1a2e", "title": "#0077b6","scale": "Blues"},
    "Corporate":  {"paper": "rgba(0,20,40,0.95)", "plot": "rgba(0,30,60,0.8)",  "font": "#e0e0e0", "title": "#00b4d8","scale": "Teal"},
    "Warm":       {"paper": "rgba(30,10,0,0.9)",  "plot": "rgba(50,20,0,0.7)",  "font": "#fff3e0", "title": "#ffa726","scale": "Oranges"},
}

def apply_theme(fig, theme_name: str):
    t = CHART_THEMES.get(theme_name, CHART_THEMES["Dark"])
    fig.update_layout(
        paper_bgcolor=t["paper"], plot_bgcolor=t["plot"],
        font_color=t["font"], title_font_color=t["title"],
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=20,r=20,t=50,b=20))
    fig.update_xaxes(gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    return fig


# ── NEW FEATURE 2: Anomaly detection ──────────────────────
def detect_anomalies(df: pd.DataFrame) -> list:
    """
    Zero tokens — pure maths.
    Returns list of anomaly strings to display.
    """
    alerts = []
    num_cols = df.select_dtypes(include="number").columns.tolist()
    for col in num_cols:
        series = df[col].dropna()
        if len(series) < 3:
            continue
        mean = series.mean()
        std  = series.std()
        if std == 0:
            continue
        high = series[series > mean + 2 * std]
        low  = series[series < mean - 2 * std]
        for idx in high.index:
            alerts.append(("high", col, df.iloc[idx, 0] if len(df.columns) > 1 else f"Row {idx}", series[idx]))
        for idx in low.index:
            alerts.append(("low",  col, df.iloc[idx, 0] if len(df.columns) > 1 else f"Row {idx}", series[idx]))
    return alerts[:5]  # max 5 alerts


# ── NEW FEATURE 3: Confidence score ───────────────────────
def calc_confidence(parsed: dict, df) -> int:
    """
    Zero tokens — heuristic scoring.
    Returns 0-100 score based on result quality.
    """
    if parsed is None:
        return 0
    score = 40
    if parsed.get("type") == "table":
        score += 20
        rows = parsed.get("data", [])
        if len(rows) > 0:   score += 15
        if len(rows) > 3:   score += 10
        if parsed.get("summary"): score += 10
        if parsed.get("kpis"):    score += 5
    elif parsed.get("type") == "text":
        content = parsed.get("content", "")
        if len(content) > 50:  score += 20
        if len(content) > 200: score += 15
    return min(score, 98)


# ── NEW FEATURE 4: Query history PDF export ───────────────
def export_query_history_pdf(query_log: list) -> bytes:
    """Export full session query history as PDF. Zero tokens."""
    pdf = FPDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    # Header
    pdf.set_fill_color(0, 77, 128)
    pdf.rect(0, 0, 210, 18, "F")
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(4)
    pdf.cell(0, 10, "Insight Grid AI -- Session Query History", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    for i, entry in enumerate(query_log):
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(0, 77, 128)
        pdf.cell(0, 7, f"Query {i+1}: {entry.get('q','')[:80]}", ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(40, 40, 40)
        result_text = entry.get("a", "No result")[:300]
        pdf.multi_cell(0, 6, result_text)
        pdf.ln(3)
        pdf.set_draw_color(200, 220, 240)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    # Return as bytes
    pdf_str = pdf.output(dest="S")
    if isinstance(pdf_str, str):
        return pdf_str.encode("latin-1")
    return bytes(pdf_str)


# ── NEW FEATURE 5: Table relationship map ─────────────────
def show_relationship_map(db_config: dict):
    """
    Zero tokens — draws a visual relationship map
    based on common key column names across tables.
    """
    try:
        from db.connection import get_db_connection_dynamic
        conn = get_db_connection_dynamic(db_config)
        cur  = conn.cursor()
        db_type = db_config.get("db_type", "postgresql").lower()

        if db_type == "snowflake":
            db_name = db_config.get("database", "").upper()
            schema  = db_config.get("schema", "PUBLIC").upper()
            cur.execute(f"""
                SELECT TABLE_NAME, COLUMN_NAME
                FROM {db_name}.INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema}'
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """)
        else:
            cur.execute("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

        rows = cur.fetchall()
        cur.close(); conn.close()

        # Build table→columns map
        table_cols: dict = {}
        for tname, cname in rows:
            table_cols.setdefault(tname, []).append(cname)

        tables = list(table_cols.keys())
        if not tables:
            st.info("No tables found.")
            return

        # Find relationships — columns ending in _key or _id shared between tables
        relationships = []
        for i, t1 in enumerate(tables):
            for t2 in tables[i+1:]:
                common = set(table_cols[t1]) & set(table_cols[t2])
                key_cols = [c for c in common if c.endswith(("_key","_id","key","id"))]
                if key_cols:
                    relationships.append((t1, t2, ", ".join(key_cols[:3])))

        # Draw with plotly
        n = len(tables)
        import math
        angle_step = 2 * math.pi / max(n, 1)
        radius = 2
        pos = {t: (radius * math.cos(i * angle_step),
                   radius * math.sin(i * angle_step))
               for i, t in enumerate(tables)}

        edge_x, edge_y, edge_labels = [], [], []
        for t1, t2, label in relationships:
            x0,y0 = pos[t1]; x1,y1 = pos[t2]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
            edge_labels.append(dict(
                x=(x0+x1)/2, y=(y0+y1)/2,
                text=label, showarrow=False,
                font=dict(size=8, color="#90e0ef"),
                bgcolor="rgba(0,50,80,0.7)"
            ))

        node_x = [pos[t][0] for t in tables]
        node_y = [pos[t][1] for t in tables]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(width=2, color="#0077b6"), hoverinfo="none"
        ))
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode="markers+text",
            marker=dict(size=28, color="#00b4d8",
                        line=dict(width=2, color="#48cae4")),
            text=tables, textposition="top center",
            textfont=dict(color="white", size=11),
            hoverinfo="text"
        ))
        fig.update_layout(
            annotations=edge_labels,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(10,10,30,0.6)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            margin=dict(l=20,r=20,t=20,b=20),
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)
        if relationships:
            st.caption(f"🔗 Found {len(relationships)} relationships via shared key columns")
        else:
            st.caption("ℹ️ No shared key columns detected between tables")

    except Exception as e:
        st.error(f"Could not load relationship map: {e}")


# ── NEW FEATURE 6: Run single query helper ────────────────
def run_single_query(q: str, db_config: dict, messages: list) -> tuple:
    """Run one query and return (parsed, df, chart_df)."""
    app = get_supervisor_app(db_config)
    result = app.invoke({"messages": messages + [HumanMessage(content=q)], "step": 0})
    final = ""
    for msg in reversed(result.get("messages", [])):
        if getattr(msg, "type", "") == "ai":
            c = getattr(msg, "content", "")
            if c and str(c).strip():
                final = str(c).strip()
                break
    parsed = parse_response(final)
    df = None
    cdf = None
    if parsed.get("type") == "table":
        df  = pd.DataFrame(parsed.get("data",[]), columns=parsed.get("columns",[]))
        cdf = make_chart_df(df)
    return parsed, df, cdf


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
        db_type   = st.selectbox("Type", ["postgresql","snowflake"], key="p_db_type",
                      format_func=lambda x: "PostgreSQL" if x=="postgresql" else "Snowflake")
        if db_type == "postgresql":
            host=st.text_input("Host",key="p_host"); port=st.text_input("Port",key="p_port",value="5432")
            database=st.text_input("Database",key="p_database"); user=st.text_input("Username",key="p_user")
            password=st.text_input("Password",key="p_password",type="password")
            cfg={"name":conn_name,"db_type":"postgresql","host":host,"port":port,
                 "database":database,"user":user,"password":password}
        else:
            account=st.text_input("Account",key="p_account",value="dbcitil-nc64603")
            user=st.text_input("Username",key="p_sf_user"); password=st.text_input("Password",key="p_sf_pwd",type="password")
            warehouse=st.text_input("Warehouse",key="p_warehouse",value="COMPUTE_WH")
            database=st.text_input("Database",key="p_sf_db"); schema=st.text_input("Schema",key="p_schema",value="PUBLIC")
            role=st.text_input("Role",key="p_role")
            cfg={"name":conn_name,"db_type":"snowflake","account":account,"user":user,
                 "password":password,"warehouse":warehouse,"database":database,"schema":schema,"role":role}
        col1,col2=st.columns(2)
        with col1:
            if st.button("⚡ Connect Now",use_container_width=True):
                ok,msg=test_connection(cfg)
                if ok:
                    st.session_state.db_connected=True; st.session_state.db_config=cfg
                    st.session_state.show_popup=False; st.rerun()
                else: st.error(msg)
        with col2:
            if st.button("💾 Save",use_container_width=True):
                if conn_name.strip(): save_connection(cfg); st.success("Saved!")
                else: st.warning("Enter name first.")
    with tab2:
        saved=load_connections()
        if not saved: st.info("No saved connections.")
        else:
            names=[x["name"] for x in saved]; sel=st.selectbox("Select",names,key="p_sel")
            row=next(x for x in saved if x["name"]==sel)
            for k,v in row.items():
                if k not in ("password","name"): st.markdown(f"**{k}:** `{v}`")
            if st.button("✅ Use This Connection",use_container_width=True):
                ok,msg=test_connection(row)
                if ok:
                    st.session_state.db_connected=True; st.session_state.db_config=row
                    st.session_state.show_popup=False; st.rerun()
                else: st.error(msg)

if st.session_state.show_popup:
    db_popup()


# ── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    role  = st.session_state.get("user_role","viewer")
    uname = st.session_state.get("user_name","User")
    st.markdown(
        f'👤 **{uname}** &nbsp;'
        f'<span class="role-badge role-{role}">{role.upper()}</span>',
        unsafe_allow_html=True)
    if st.button("🚪 Logout",use_container_width=True):
        logout(); st.rerun()
    st.divider()

    db_type_now = st.session_state.db_config.get("db_type","postgresql").lower() \
                  if st.session_state.db_connected else "postgresql"
    if db_type_now == "snowflake":
        st.markdown("### 💡 Oil & Gas Questions")
    else:
        st.markdown("### 💡 E-Commerce Questions")
    st.caption("Click → edit → Run Analysis")
    for i, s in enumerate(get_suggestions()):
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            st.session_state.pending_text = s
            st.rerun()

    st.divider()
    st.markdown("### 🗄️ Active Connection")
    if st.session_state.db_connected:
        cfg=st.session_state.db_config
        st.success(f"**{cfg.get('name','—')}**\n\n`{cfg.get('db_type','').upper()}`")
        if st.button("🔌 Disconnect",use_container_width=True):
            st.session_state.db_connected=False; st.session_state.db_config={}; st.rerun()
    else:
        st.warning("No database connected")

    # ── NEW: Chart Theme ───────────────────────────────────
    st.divider()
    st.markdown("### 🎨 Chart Theme")
    st.session_state.chart_theme = st.selectbox(
        "Select Theme", list(CHART_THEMES.keys()),
        index=list(CHART_THEMES.keys()).index(st.session_state.chart_theme),
        key="theme_select", label_visibility="collapsed"
    )

    # ── NEW: Table Relationship Map ────────────────────────
    if st.session_state.db_connected:
        st.divider()
        st.markdown("### 🗺️ Table Relationships")
        if st.button("Show Relationship Map", use_container_width=True):
            st.session_state["show_rel_map"] = True

    # ── NEW: Query History Export ──────────────────────────
    if st.session_state.query_log:
        st.divider()
        st.markdown("### 📋 Session History")
        st.caption(f"{len(st.session_state.query_log)} queries this session")
        try:
            hist_pdf = export_query_history_pdf(st.session_state.query_log)
            st.download_button(
                "📥 Export History PDF",
                data=hist_pdf,
                file_name="query_history.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            pass

    if st.session_state.memory_on and st.session_state.history_pairs:
        st.divider()
        st.markdown("### 🧠 Conversation History")
        pairs=st.session_state.history_pairs
        st.caption(f"{len(pairs)} exchange(s)")
        for idx,pair in enumerate(reversed(pairs)):
            ri=len(pairs)-1-idx
            label=pair['q'][:45]+("…" if len(pair['q'])>45 else "")
            with st.expander(f"#{ri+1} — {label}"):
                st.markdown(f"**You:** {pair['q']}")
                st.markdown(f"**Result:** {pair['a']}")
                if st.button("↩ Re-load",key=f"hist_{ri}",use_container_width=True):
                    st.session_state.pending_text=pair['q']; st.rerun()
        if st.button("🗑️ Clear History",use_container_width=True):
            st.session_state.history=[]; st.session_state.history_pairs=[]; st.rerun()


# ── NEW: Relationship Map Display ─────────────────────────
if st.session_state.get("show_rel_map") and st.session_state.db_connected:
    st.subheader("🗺️ Table Relationship Map")
    show_relationship_map(st.session_state.db_config)
    if st.button("✖ Close Map"):
        st.session_state["show_rel_map"] = False
        st.rerun()
    st.divider()


# ── NEW: Compare Two Queries Mode ─────────────────────────
st.session_state.compare_mode = st.toggle(
    "⚖️ Compare Two Queries Mode", value=st.session_state.compare_mode,
    key="compare_toggle"
)

if st.session_state.compare_mode:
    st.info("💡 Enter two different questions to compare results side by side.")
    cq1, cq2 = st.columns(2)
    with cq1:
        q1 = st.text_area("Question 1", height=80, key="cmp_q1",
                           placeholder="e.g. Show top 5 customers by revenue")
    with cq2:
        q2 = st.text_area("Question 2", height=80, key="cmp_q2",
                           placeholder="e.g. Show top 5 products by revenue")

    if st.button("⚖️ Run Comparison", type="primary", use_container_width=True):
        if not st.session_state.db_connected:
            st.error("❌ Connect to a database first.")
        elif not q1.strip() or not q2.strip():
            st.warning("⚠️ Please enter both questions.")
        else:
            with st.spinner("Running both queries…"):
                try:
                    p1, df1, cdf1 = run_single_query(q1.strip(), st.session_state.db_config, [])
                    p2, df2, cdf2 = run_single_query(q2.strip(), st.session_state.db_config, [])
                    st.session_state.compare_parsed1 = p1
                    st.session_state.compare_parsed2 = p2
                    st.session_state.compare_df1 = df1
                    st.session_state.compare_df2 = df2
                except Exception as e:
                    st.error(f"Comparison error: {e}")

    # Show comparison results
    if st.session_state.compare_df1 is not None or st.session_state.compare_parsed1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Result 1:** {st.session_state.get('cmp_q1','')[:50]}")
            p1 = st.session_state.compare_parsed1
            df1 = st.session_state.compare_df1
            if p1 and p1.get("summary"):
                st.info(f"💡 {p1['summary']}")
            if df1 is not None:
                st.dataframe(df1, use_container_width=True)
            elif p1 and p1.get("type") == "text":
                st.markdown(p1.get("content",""))
        with col2:
            st.markdown(f"**Result 2:** {st.session_state.get('cmp_q2','')[:50]}")
            p2 = st.session_state.compare_parsed2
            df2 = st.session_state.compare_df2
            if p2 and p2.get("summary"):
                st.info(f"💡 {p2['summary']}")
            if df2 is not None:
                st.dataframe(df2, use_container_width=True)
            elif p2 and p2.get("type") == "text":
                st.markdown(p2.get("content",""))
    st.divider()


# ── Query box ──────────────────────────────────────────────
query = st.text_area(
    "💬 Ask your business question",
    height=110,
    value=st.session_state.pending_text,
    placeholder="e.g. Show top 10 customers by total revenue",
)
run_clicked = st.button("🚀 Run Analysis", type="primary")

if run_clicked and not st.session_state.get("permissions",{}).get("can_run_query",True):
    st.warning("🔒 Your role cannot run queries.")
    run_clicked = False


# ── Run Analysis ───────────────────────────────────────────
if run_clicked:
    st.session_state.show_popup = False
    active_query = query.strip()

    if not active_query:
        st.warning("⚠️ Please enter a question."); st.stop()
    if not st.session_state.db_connected:
        st.error("❌ Connect to a database first."); st.stop()

    if st.session_state.memory_on and st.session_state.history:
        messages = clean_history(st.session_state.history) + [HumanMessage(content=active_query)]
    else:
        messages = [HumanMessage(content=active_query)]

    app = get_supervisor_app(st.session_state.db_config)

    try:
        with st.spinner("🤖 Running Agents… (Analyst → Expert → Reviewer)"):
            result = app.invoke({"messages": messages, "step": 0})

        final = ""
        for msg in reversed(result.get("messages", [])):
            if getattr(msg, "type", "") == "ai":
                c = getattr(msg, "content", "")
                if c and str(c).strip():
                    final = str(c).strip()
                    break

    except Exception as e:
        err = str(e).lower()
        if "rate" in err or "429" in err:
            st.error("⚠️ **Rate limit hit.** Wait 60 seconds then try again.")
        elif "badrequest" in err or "400" in err:
            st.session_state.history = []
            st.session_state.history_pairs = []
            st.error("⚠️ **Request error.** History cleared — please try again.")
        else:
            st.error(f"⚠️ Error: {str(e)[:300]}")
        st.stop()

    if not final:
        st.warning("⚠️ No response received. Please try again."); st.stop()

    st.session_state.last_response  = final
    st.session_state.last_run_query = active_query
    st.session_state.chart_path     = None
    st.session_state.pending_text   = active_query

    parsed = parse_response(final)
    st.session_state.last_parsed = parsed

    if parsed.get("type") == "table":
        raw_df = pd.DataFrame(parsed.get("data",[]), columns=parsed.get("columns",[]))
        st.session_state.last_df  = raw_df
        st.session_state.chart_df = make_chart_df(raw_df)
    else:
        st.session_state.last_df  = None
        st.session_state.chart_df = None

    try:
        current_db_type = st.session_state.db_config.get("db_type", "postgresql").lower()
        st.session_state.followups = get_followup_questions(active_query, db_type=current_db_type)
    except Exception:
        st.session_state.followups = [
            "Show top 5 by revenue", "Show monthly trend",
            "Compare this year vs last year", "Show bottom 5 performers",
            "Show total count of records",
        ]

    # Log query for history export
    a_text = ""
    if parsed:
        if parsed.get("type") == "text":
            a_text = parsed.get("content", final)[:200]
        else:
            cols=parsed.get("columns",[]); rows=parsed.get("data",[])
            a_text=f"Table: {len(rows)} rows — {', '.join(cols[:3])}"
    st.session_state.query_log.append({"q": active_query, "a": a_text})
    if len(st.session_state.query_log) > 50:
        st.session_state.query_log = st.session_state.query_log[-50:]

    if st.session_state.memory_on:
        st.session_state.history.append(HumanMessage(content=active_query))
        st.session_state.history.append(AIMessage(content=final))
        if len(st.session_state.history) > 8:
            st.session_state.history = st.session_state.history[-8:]
        st.session_state.history_pairs.append({"q":active_query,"a":a_text})
        if len(st.session_state.history_pairs)>8:
            st.session_state.history_pairs=st.session_state.history_pairs[-8:]


# ── NEW: Confidence Score ──────────────────────────────────
parsed = st.session_state.last_parsed
if parsed and st.session_state.last_response:
    score = calc_confidence(parsed, st.session_state.last_df)
    color = "#48cae4" if score >= 80 else "#ffd93d" if score >= 60 else "#ff6b6b"
    st.markdown(
        f'<div class="confidence-bar">🎯 <b>AI Confidence:</b> '
        f'<span style="color:{color};font-weight:700">{score}%</span> — '
        f'{"High confidence result" if score>=80 else "Moderate confidence" if score>=60 else "Low confidence — verify result"}'
        f'</div>',
        unsafe_allow_html=True
    )


# ── KPI Cards ──────────────────────────────────────────────
if parsed and isinstance(parsed, dict):
    kpis = parsed.get("kpis", [])
    if kpis:
        st.subheader("📌 Key Metrics")
        kpi_cols = st.columns(len(kpis))
        for i,kpi in enumerate(kpis):
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

    # ── NEW: Anomaly Detection ─────────────────────────────
    anomalies = detect_anomalies(st.session_state.last_df)
    if anomalies:
        st.subheader("⚠️ Data Anomalies Detected")
        for atype, col, label, val in anomalies:
            css = "anomaly-high" if atype == "high" else "anomaly-low"
            icon = "🔺" if atype == "high" else "🔻"
            st.markdown(
                f'<span class="{css}">{icon} Unusual {atype} value in <b>{col}</b>: '
                f'<b>{label}</b> = {val:,.0f}</span>',
                unsafe_allow_html=True
            )
        st.markdown("")

    if st.session_state.get("permissions",{}).get("can_download",True):
        csv = st.session_state.last_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV (Power BI)", data=csv,
                           file_name="insight_data.csv", mime="text/csv")


# ── Visualization ──────────────────────────────────────────
if st.session_state.chart_df is not None:
    cdf      = st.session_state.chart_df
    num_cols = cdf.select_dtypes(include="number").columns.tolist()
    all_cols = cdf.columns.tolist()

    if not num_cols and all_cols:
        lc = all_cols[-1]
        cdf[lc] = pd.to_numeric(
            cdf[lc].astype(str).str.replace(",","",regex=False).str.strip(),
            errors="coerce")
        st.session_state.chart_df = cdf
        num_cols = cdf.select_dtypes(include="number").columns.tolist()

    if num_cols:
        st.subheader("📈 Interactive Visualization")
        vc1,vc2,vc3 = st.columns(3)
        with vc1:
            chart_type = st.selectbox("Chart Type",
                ["Bar","Horizontal Bar","Line","Area","Pie","Donut","Treemap","Scatter"],
                key="viz_chart_type")
        with vc2:
            val_col = st.selectbox("Value",num_cols,index=len(num_cols)-1,key="viz_value_col")
        with vc3:
            lbl_options=[c for c in all_cols if c!=val_col] or all_cols
            lbl_col=st.selectbox("Label/Group",lbl_options,key="viz_label_col")

        theme = st.session_state.chart_theme
        scale = CHART_THEMES[theme]["scale"]
        title=f"{val_col} by {lbl_col}"; fig=None

        if   chart_type=="Bar":
            fig=px.bar(cdf,x=lbl_col,y=val_col,color=val_col,color_continuous_scale=scale,title=title,text_auto=True)
        elif chart_type=="Horizontal Bar":
            fig=px.bar(cdf,x=val_col,y=lbl_col,orientation="h",color=val_col,color_continuous_scale=scale,title=title,text_auto=True)
        elif chart_type=="Line":
            fig=px.line(cdf,x=lbl_col,y=val_col,markers=True,title=title)
        elif chart_type=="Area":
            fig=px.area(cdf,x=lbl_col,y=val_col,title=title)
        elif chart_type=="Pie":
            fig=px.pie(cdf,names=lbl_col,values=val_col,title=title)
        elif chart_type=="Donut":
            fig=px.pie(cdf,names=lbl_col,values=val_col,hole=0.45,title=title)
        elif chart_type=="Treemap":
            fig=px.treemap(cdf,path=[lbl_col],values=val_col,title=title)
        elif chart_type=="Scatter":
            fig=px.scatter(cdf,x=lbl_col,y=val_col,color=val_col,color_continuous_scale=scale,title=title)

        if fig:
            fig = apply_theme(fig, theme)
            st.plotly_chart(fig,use_container_width=True)
            try:
                fig.write_image("chart_export.png",width=900,height=500,scale=2)
                st.session_state.chart_path="chart_export.png"
            except Exception:
                pass


# ── Text result ────────────────────────────────────────────
if (st.session_state.last_response and st.session_state.last_df is None
        and parsed and isinstance(parsed,dict) and parsed.get("type")=="text"):
    st.subheader("💬 Analysis Result")
    st.markdown(parsed.get("content",st.session_state.last_response))


# ── Follow-up questions ────────────────────────────────────
if st.session_state.followups:
    st.subheader("🔁 Follow-up Questions")
    st.caption("Click to load → edit → **Run Analysis**")
    fcols=st.columns(2)
    for i,q in enumerate(st.session_state.followups):
        with fcols[i%2]:
            if st.button(q,key=f"fq_{i}",use_container_width=True):
                st.session_state.pending_text=q; st.rerun()


# ── PDF download ───────────────────────────────────────────
if st.session_state.last_response and st.session_state.last_parsed:
    p=st.session_state.last_parsed
    if (p.get("type") in ("table","text")
            and st.session_state.get("permissions",{}).get("can_download",True)):
        try:
            pdf_file=create_pdf(p,st.session_state.last_run_query or "",
                                chart_path=st.session_state.get("chart_path"))
            with open(pdf_file,"rb") as f:
                st.download_button("📄 Download Report (PDF)",data=f,
                                   file_name="Insight_Report.pdf",mime="application/pdf")
        except Exception as e:
            st.caption(f"PDF note: {e}")
