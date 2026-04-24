import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json, time, io
from fpdf import FPDF
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage

from auth.login_ui import show_login_popup, check_auth, logout

st.set_page_config(page_title="Insight Grid AI", page_icon="🤖", layout="wide")

if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "permissions" not in st.session_state: st.session_state.permissions = {}

if not check_auth():
    show_login_popup()
    st.stop()

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent   import get_followup_questions
from db.connection           import test_connection
from utils.db_store          import load_connections, save_connection
from utils.pdf_export        import create_pdf
from utils.cache             import load_bg
from utils.parser            import parse_response

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
.stat-card {{
    background:rgba(0,80,120,0.35); border:1px solid rgba(0,180,216,0.3);
    border-radius:10px; padding:10px 8px; text-align:center;
}}
.stat-val {{ font-size:1.1rem; font-weight:700; color:#48cae4; }}
.stat-lbl {{ font-size:0.7rem; color:#90e0ef; }}
.pinned-banner {{
    background:rgba(0,100,60,0.4); border:1px solid rgba(0,200,120,0.5);
    border-radius:10px; padding:12px 16px; margin-bottom:12px;
}}
.meta-bar {{
    background:rgba(0,50,80,0.4); border-radius:8px;
    padding:6px 14px; margin-bottom:6px; font-size:0.82rem;
    color:#90e0ef; display:flex; gap:18px; flex-wrap:wrap;
}}
.tag-badge {{
    display:inline-block; padding:2px 10px; border-radius:12px;
    font-size:0.75rem; font-weight:700; margin-right:4px;
}}
.tag-Revenue    {{ background:#0077b6; color:white; }}
.tag-Trend      {{ background:#00b4d8; color:white; }}
.tag-Metadata   {{ background:#7b2d8b; color:white; }}
.tag-Count      {{ background:#2d8b5a; color:white; }}
.tag-Comparison {{ background:#8b5a2d; color:white; }}
.tag-Top        {{ background:#1a6b3a; color:white; }}
.tag-Other      {{ background:#555;    color:white; }}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────
_defaults = {
    "db_connected":    False,
    "db_config":       {},
    "memory_on":       False,
    "history":         [],
    "history_pairs":   [],
    "last_response":   "",
    "last_df":         None,
    "chart_df":        None,
    "last_parsed":     None,
    "followups":       [],
    "show_popup":      False,
    "chart_path":      None,
    "last_run_query":  "",
    "pending_text":    "",
    "compare_mode":    False,
    "compare_df1":     None,
    "compare_df2":     None,
    "compare_parsed1": None,
    "compare_parsed2": None,
    "query_log":       [],
    "chart_theme":     "Dark",
    "pinned_result":   None,
    # NEW
    "query_count":     0,       # feature 4
    "last_resp_time":  None,    # feature 5
    "last_fetch_time": None,    # feature 6
    "last_query_tag":  None,    # feature 9
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Suggestions ────────────────────────────────────────────
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

def get_suggestions():
    if st.session_state.db_connected:
        if st.session_state.db_config.get("db_type","postgresql").lower()=="snowflake":
            return SNOWFLAKE_SUGGESTIONS
    return POSTGRESQL_SUGGESTIONS

# ── Helpers ────────────────────────────────────────────────
def make_chart_df(raw_df):
    df = raw_df.copy()
    for col in df.columns:
        cleaned = (df[col].astype(str)
                   .str.replace(",","",regex=False)
                   .str.replace("$","",regex=False)
                   .str.replace("%","",regex=False)
                   .str.strip())
        coerced = pd.to_numeric(cleaned, errors="coerce")
        if coerced.notna().any():
            df[col] = coerced
    return df

def clean_history(msgs):
    clean = []
    for m in msgs:
        if isinstance(m,(HumanMessage,AIMessage)):
            c = getattr(m,"content","")
            if isinstance(c,str) and c.strip():
                clean.append(m)
    return clean[-4:]

# ── Chart themes ───────────────────────────────────────────
CHART_THEMES = {
    "Dark":      {"paper":"rgba(0,0,0,0)",      "plot":"rgba(10,10,30,0.6)",  "font":"white",   "title":"#48cae4","scale":"Blues"},
    "Light":     {"paper":"rgba(255,255,255,1)", "plot":"rgba(240,245,255,1)","font":"#1a1a2e", "title":"#0077b6","scale":"Blues"},
    "Corporate": {"paper":"rgba(0,20,40,0.95)",  "plot":"rgba(0,30,60,0.8)",  "font":"#e0e0e0", "title":"#00b4d8","scale":"Teal"},
    "Warm":      {"paper":"rgba(30,10,0,0.9)",   "plot":"rgba(50,20,0,0.7)",  "font":"#fff3e0", "title":"#ffa726","scale":"Oranges"},
}

def apply_theme(fig, theme_name):
    t = CHART_THEMES.get(theme_name, CHART_THEMES["Dark"])
    fig.update_layout(
        paper_bgcolor=t["paper"], plot_bgcolor=t["plot"],
        font_color=t["font"], title_font_color=t["title"],
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=20,r=20,t=50,b=20))
    fig.update_xaxes(gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    return fig

# ── Anomaly detection ──────────────────────────────────────
def detect_anomalies(df):
    alerts = []
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) < 3: continue
        mean, std = s.mean(), s.std()
        if std == 0: continue
        for idx in s[s > mean+2*std].index:
            alerts.append(("high",col,str(df.iloc[idx,0])[:20],s[idx]))
        for idx in s[s < mean-2*std].index:
            alerts.append(("low", col,str(df.iloc[idx,0])[:20],s[idx]))
    return alerts[:5]

# ── Confidence score ───────────────────────────────────────
def calc_confidence(parsed, df) -> int:
    if not parsed: return 0
    score = 40
    if parsed.get("type") == "table":
        score += 20
        rows = parsed.get("data",[])
        if len(rows) > 0:  score += 15
        if len(rows) > 3:  score += 10
        if parsed.get("summary"): score += 10
        if parsed.get("kpis"):    score += 5
    elif parsed.get("type") == "text":
        c = parsed.get("content","")
        if len(c) > 50:  score += 20
        if len(c) > 200: score += 15
    return min(score, 98)

# ── Query history PDF ──────────────────────────────────────
def export_query_history_pdf(query_log):
    pdf = FPDF()
    pdf.set_auto_page_break(True,20); pdf.add_page()
    pdf.set_fill_color(0,77,128); pdf.rect(0,0,210,18,"F")
    pdf.set_font("Arial","B",13); pdf.set_text_color(255,255,255)
    pdf.set_y(4); pdf.cell(0,10,"Insight Grid AI -- Session Query History",ln=True,align="C")
    pdf.set_text_color(0,0,0); pdf.ln(6)
    for i,entry in enumerate(query_log):
        pdf.set_font("Arial","B",10); pdf.set_text_color(0,77,128)
        pdf.cell(0,7,f"Query {i+1}: {entry.get('q','')[:80]}",ln=True)
        pdf.set_font("Arial","",9); pdf.set_text_color(40,40,40)
        pdf.multi_cell(0,6,str(entry.get("a","No result"))[:300])
        pdf.ln(3); pdf.set_draw_color(200,220,240)
        pdf.line(10,pdf.get_y(),200,pdf.get_y()); pdf.ln(4)
    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out,str) else bytes(out)

# ── Relationship map ───────────────────────────────────────
def show_relationship_map(db_config):
    import math
    try:
        from db.connection import get_db_connection_dynamic
        conn = get_db_connection_dynamic(db_config)
        cur  = conn.cursor()
        db_type = db_config.get("db_type","postgresql").lower()
        if db_type == "snowflake":
            db_name = db_config.get("database","").upper()
            schema  = db_config.get("schema","PUBLIC").upper()
            cur.execute(f"SELECT TABLE_NAME,COLUMN_NAME FROM {db_name}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='{schema}' ORDER BY TABLE_NAME,ORDINAL_POSITION")
        else:
            cur.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")
        rows = cur.fetchall(); cur.close(); conn.close()
        table_cols: dict = {}
        for tname,cname in rows:
            table_cols.setdefault(tname,[]).append(cname)
        tables = list(table_cols.keys())
        if not tables: st.info("No tables found."); return
        relationships = []
        for i,t1 in enumerate(tables):
            for t2 in tables[i+1:]:
                common = set(table_cols[t1]) & set(table_cols[t2])
                keys = [c for c in common if c.endswith(("_key","_id","key","id"))]
                if keys: relationships.append((t1,t2,", ".join(keys[:3])))
        n = len(tables)
        angle_step = 2*math.pi/max(n,1); radius=2
        pos = {t:(radius*math.cos(i*angle_step),radius*math.sin(i*angle_step)) for i,t in enumerate(tables)}
        edge_x,edge_y,annots=[],[],[]
        for t1,t2,label in relationships:
            x0,y0=pos[t1]; x1,y1=pos[t2]
            edge_x+=[x0,x1,None]; edge_y+=[y0,y1,None]
            annots.append(dict(x=(x0+x1)/2,y=(y0+y1)/2,text=label,showarrow=False,font=dict(size=8,color="#90e0ef"),bgcolor="rgba(0,50,80,0.7)"))
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=edge_x,y=edge_y,mode="lines",line=dict(width=2,color="#0077b6"),hoverinfo="none"))
        fig.add_trace(go.Scatter(x=[pos[t][0] for t in tables],y=[pos[t][1] for t in tables],mode="markers+text",marker=dict(size=28,color="#00b4d8",line=dict(width=2,color="#48cae4")),text=tables,textposition="top center",textfont=dict(color="white",size=11),hoverinfo="text"))
        fig.update_layout(annotations=annots,showlegend=False,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(10,10,30,0.6)",xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),margin=dict(l=20,r=20,t=20,b=20),height=400)
        st.plotly_chart(fig,use_container_width=True)
        st.caption(f"🔗 {len(relationships)} relationships found via shared key columns")
    except Exception as e:
        st.error(f"Could not load map: {e}")

# ── Compare helper ─────────────────────────────────────────
def run_single_query(q, db_config, messages):
    app = get_supervisor_app(db_config)
    result = app.invoke({"messages":messages+[HumanMessage(content=q)],"step":0})
    final = ""
    for msg in reversed(result.get("messages",[])):
        if getattr(msg,"type","")=="ai":
            c=getattr(msg,"content","")
            if c and str(c).strip(): final=str(c).strip(); break
    parsed = parse_response(final)
    df=cdf=None
    if parsed.get("type")=="table":
        df=pd.DataFrame(parsed.get("data",[]),columns=parsed.get("columns",[]))
        cdf=make_chart_df(df)
    return parsed,df,cdf

# ── Stats panel ────────────────────────────────────────────
def show_stats_panel(df):
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols: return
    with st.expander("📊 Column Statistics",expanded=False):
        for col in num_cols:
            s = df[col].dropna()
            if len(s)==0: continue
            st.markdown(f"**{col}**")
            sc=st.columns(5)
            for i,(lbl,val) in enumerate([("Mean",f"{s.mean():,.1f}"),("Median",f"{s.median():,.1f}"),("Min",f"{s.min():,.1f}"),("Max",f"{s.max():,.1f}"),("Std",f"{s.std():,.1f}")]):
                with sc[i]:
                    st.markdown(f'<div class="stat-card"><div class="stat-val">{val}</div><div class="stat-lbl">{lbl}</div></div>',unsafe_allow_html=True)
            st.markdown("")

# ── FEATURE 1: Copy to clipboard ──────────────────────────
def show_copy_button(df):
    """Renders a copy-to-clipboard button — zero tokens."""
    csv_str = df.to_csv(index=False)
    st.markdown(
        f"""
        <button onclick="navigator.clipboard.writeText({json.dumps(csv_str)}).then(()=>{{
            this.textContent='✅ Copied!';
            setTimeout(()=>{{this.textContent='📋 Copy Table'}},2000);
        }})"
        style="background:rgba(0,119,182,0.3);border:1px solid rgba(0,180,216,0.5);
               color:#90e0ef;border-radius:8px;padding:5px 14px;cursor:pointer;
               font-size:0.85rem;margin-bottom:6px;">
        📋 Copy Table
        </button>
        """,
        unsafe_allow_html=True,
    )

# ── FEATURE 3: Searchable + sortable table ─────────────────
def show_searchable_table(df, row_limit=None):
    """Search, filter, column sort — zero tokens."""
    search = st.text_input("🔍 Search / filter rows",
        placeholder="Type to filter any column…", key="table_search")
    display_df = df.copy()
    if search.strip():
        mask = display_df.astype(str).apply(
            lambda col: col.str.contains(search.strip(),case=False,na=False)
        ).any(axis=1)
        display_df = display_df[mask]
        st.caption(f"Showing {len(display_df)} of {len(df)} rows matching '{search}'")
    if row_limit and row_limit < len(display_df):
        display_df = display_df.head(row_limit)
    st.dataframe(display_df, use_container_width=True)

# ── FEATURE 9: Auto query tagger ──────────────────────────
_TAG_RULES = [
    ("Revenue",    ["revenue","sales","income","profit","earning","total"]),
    ("Trend",      ["trend","monthly","daily","weekly","over time","by month","by year"]),
    ("Metadata",   ["metadata","schema","column","structure","data type","relationship","compare table","similarity"]),
    ("Count",      ["count","how many","number of","total records"]),
    ("Comparison", ["compare","vs","versus","difference","between"]),
    ("Top",        ["top","best","highest","leading","most"]),
]

def auto_tag(query: str) -> str:
    """Zero tokens — pure keyword matching."""
    q = query.lower()
    for tag, keywords in _TAG_RULES:
        if any(kw in q for kw in keywords):
            return tag
    return "Other"

# ── Header ─────────────────────────────────────────────────
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")

c1,c2,c3=st.columns([3,3,2])
with c1: st.toggle("🧠 Memory Mode",key="memory_on")
with c2:
    if st.session_state.db_connected:
        name=st.session_state.db_config.get("name","")
        dbt=st.session_state.db_config.get("db_type","postgresql").upper()
        st.success(f"✅ {name} ({dbt})" if name else f"✅ Connected ({dbt})")
    else:
        st.warning("⚠️ Not Connected")
with c3:
    perms=st.session_state.get("permissions",{})
    if perms.get("can_connect_db",True):
        if st.button("🔌 Connect Database",use_container_width=True):
            st.session_state.show_popup=True
    else:
        st.info("🔒 Viewer role")

@st.dialog("Connect to Database",width="large")
def db_popup():
    tab1,tab2=st.tabs(["✏️ Manual Entry","💾 Saved Connections"])
    with tab1:
        conn_name=st.text_input("Connection Name",key="p_name")
        db_type=st.selectbox("Type",["postgresql","snowflake"],key="p_db_type",
                  format_func=lambda x:"PostgreSQL" if x=="postgresql" else "Snowflake")
        if db_type=="postgresql":
            host=st.text_input("Host",key="p_host"); port=st.text_input("Port",key="p_port",value="5432")
            database=st.text_input("Database",key="p_database"); user=st.text_input("Username",key="p_user")
            password=st.text_input("Password",key="p_password",type="password")
            cfg={"name":conn_name,"db_type":"postgresql","host":host,"port":port,"database":database,"user":user,"password":password}
        else:
            account=st.text_input("Account",key="p_account",value="dbcitil-nc64603")
            user=st.text_input("Username",key="p_sf_user"); password=st.text_input("Password",key="p_sf_pwd",type="password")
            warehouse=st.text_input("Warehouse",key="p_warehouse",value="COMPUTE_WH")
            database=st.text_input("Database",key="p_sf_db"); schema=st.text_input("Schema",key="p_schema",value="PUBLIC")
            role=st.text_input("Role",key="p_role")
            cfg={"name":conn_name,"db_type":"snowflake","account":account,"user":user,"password":password,"warehouse":warehouse,"database":database,"schema":schema,"role":role}
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
    role=st.session_state.get("user_role","viewer")
    uname=st.session_state.get("user_name","User")
    st.markdown(f'👤 **{uname}** &nbsp;<span class="role-badge role-{role}">{role.upper()}</span>',unsafe_allow_html=True)
    if st.button("🚪 Logout",use_container_width=True):
        logout(); st.rerun()
    st.divider()

    db_type_now=st.session_state.db_config.get("db_type","postgresql").lower() if st.session_state.db_connected else "postgresql"
    st.markdown("### 💡 Oil & Gas Questions" if db_type_now=="snowflake" else "### 💡 E-Commerce Questions")
    st.caption("Click → edit → Run Analysis")
    for i,s in enumerate(get_suggestions()):
        if st.button(s,key=f"sug_{i}",use_container_width=True):
            st.session_state.pending_text=s; st.rerun()

    st.divider()
    st.markdown("### 🗄️ Active Connection")
    if st.session_state.db_connected:
        cfg=st.session_state.db_config
        st.success(f"**{cfg.get('name','—')}**\n\n`{cfg.get('db_type','').upper()}`")
        if st.button("🔌 Disconnect",use_container_width=True):
            st.session_state.db_connected=False; st.session_state.db_config={}; st.rerun()
    else:
        st.warning("No database connected")

    st.divider()
    st.markdown("### 🎨 Chart Theme")
    st.session_state.chart_theme=st.selectbox(
        "Theme",list(CHART_THEMES.keys()),
        index=list(CHART_THEMES.keys()).index(st.session_state.chart_theme),
        key="theme_select",label_visibility="collapsed")

    # FEATURE 4: Query counter
    if st.session_state.query_count > 0:
        st.divider()
        st.markdown(f"### 🎯 Session Stats")
        st.info(f"**{st.session_state.query_count}** queries asked this session")

    if st.session_state.db_connected:
        st.divider()
        st.markdown("### 🗺️ Table Relationships")
        if st.button("Show Relationship Map",use_container_width=True):
            st.session_state["show_rel_map"]=True

    if st.session_state.query_log:
        st.divider()
        st.markdown("### 📋 Session History")
        st.caption(f"{len(st.session_state.query_log)} queries")
        try:
            hist_pdf=export_query_history_pdf(st.session_state.query_log)
            st.download_button("📥 Export History PDF",data=hist_pdf,
                file_name="query_history.pdf",mime="application/pdf",use_container_width=True)
        except Exception: pass

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

# ── Relationship map ───────────────────────────────────────
if st.session_state.get("show_rel_map") and st.session_state.db_connected:
    st.subheader("🗺️ Table Relationship Map")
    show_relationship_map(st.session_state.db_config)
    if st.button("✖ Close Map"):
        st.session_state["show_rel_map"]=False; st.rerun()
    st.divider()

# ── Pinned result ──────────────────────────────────────────
if st.session_state.pinned_result:
    pin=st.session_state.pinned_result
    st.markdown(f'<div class="pinned-banner">📌 <b>Pinned:</b> {pin["query"]}</div>',unsafe_allow_html=True)
    p=pin["parsed"]; df=pin["df"]
    if p and p.get("summary"): st.info(f"💡 {p['summary']}")
    if df is not None: st.dataframe(df,use_container_width=True)
    elif p and p.get("type")=="text": st.markdown(p.get("content",""))
    if st.button("📌 Unpin Result"):
        st.session_state.pinned_result=None; st.rerun()
    st.divider()

# ── Compare mode ───────────────────────────────────────────
st.session_state.compare_mode=st.toggle("⚖️ Compare Two Queries Mode",value=st.session_state.compare_mode,key="compare_toggle")
if st.session_state.compare_mode:
    st.info("💡 Enter two questions to compare results side by side.")
    cq1,cq2=st.columns(2)
    with cq1: q1=st.text_area("Question 1",height=80,key="cmp_q1",placeholder="e.g. Top 5 customers by revenue")
    with cq2: q2=st.text_area("Question 2",height=80,key="cmp_q2",placeholder="e.g. Top 5 products by revenue")
    if st.button("⚖️ Run Comparison",type="primary",use_container_width=True):
        if not st.session_state.db_connected: st.error("❌ Connect first.")
        elif not q1.strip() or not q2.strip(): st.warning("⚠️ Enter both questions.")
        else:
            with st.spinner("Running both queries…"):
                try:
                    p1,df1,_=run_single_query(q1.strip(),st.session_state.db_config,[])
                    p2,df2,_=run_single_query(q2.strip(),st.session_state.db_config,[])
                    st.session_state.compare_parsed1=p1; st.session_state.compare_df1=df1
                    st.session_state.compare_parsed2=p2; st.session_state.compare_df2=df2
                except Exception as e: st.error(f"Error: {e}")
    if st.session_state.compare_df1 is not None or st.session_state.compare_parsed1:
        col1,col2=st.columns(2)
        with col1:
            p1=st.session_state.compare_parsed1; df1=st.session_state.compare_df1
            if p1 and p1.get("summary"): st.info(f"💡 {p1['summary']}")
            if df1 is not None: st.dataframe(df1,use_container_width=True)
            elif p1 and p1.get("type")=="text": st.markdown(p1.get("content",""))
        with col2:
            p2=st.session_state.compare_parsed2; df2=st.session_state.compare_df2
            if p2 and p2.get("summary"): st.info(f"💡 {p2['summary']}")
            if df2 is not None: st.dataframe(df2,use_container_width=True)
            elif p2 and p2.get("type")=="text": st.markdown(p2.get("content",""))
    st.divider()

# ── Query box ──────────────────────────────────────────────
query=st.text_area("💬 Ask your business question",height=110,
    value=st.session_state.pending_text,
    placeholder="e.g. Show top 10 customers by total revenue")
run_clicked=st.button("🚀 Run Analysis",type="primary")

if run_clicked and not st.session_state.get("permissions",{}).get("can_run_query",True):
    st.warning("🔒 Your role cannot run queries."); run_clicked=False

# ── Run Analysis ───────────────────────────────────────────
if run_clicked:
    st.session_state.show_popup=False
    active_query=query.strip()
    if not active_query: st.warning("⚠️ Please enter a question."); st.stop()
    if not st.session_state.db_connected: st.error("❌ Connect to a database first."); st.stop()

    messages=clean_history(st.session_state.history)+[HumanMessage(content=active_query)] \
             if st.session_state.memory_on and st.session_state.history \
             else [HumanMessage(content=active_query)]

    app=get_supervisor_app(st.session_state.db_config)
    try:
        with st.spinner("🤖 Running Agents… (Analyst → Expert → Reviewer)"):
            _t_start=time.time()                          # FEATURE 5 start
            result=app.invoke({"messages":messages,"step":0})
            _t_end=time.time()                            # FEATURE 5 end
            st.session_state.last_resp_time=round(_t_end-_t_start,1)
            st.session_state.last_fetch_time=datetime.now().strftime("%H:%M:%S")  # FEATURE 6

        final=""
        for msg in reversed(result.get("messages",[])):
            if getattr(msg,"type","")=="ai":
                c=getattr(msg,"content","")
                if c and str(c).strip(): final=str(c).strip(); break
    except Exception as e:
        err=str(e).lower()
        if "rate" in err or "429" in err: st.error("⚠️ Rate limit. Wait 60s.")
        elif "badrequest" in err or "400" in err:
            st.session_state.history=[]; st.session_state.history_pairs=[]
            st.error("⚠️ Request error. History cleared.")
        else: st.error(f"⚠️ Error: {str(e)[:300]}")
        st.stop()

    if not final: st.warning("⚠️ No response. Try again."); st.stop()

    st.session_state.last_response=final
    st.session_state.last_run_query=active_query
    st.session_state.chart_path=None
    st.session_state.pending_text=active_query
    st.session_state.query_count+=1                       # FEATURE 4
    st.session_state.last_query_tag=auto_tag(active_query)# FEATURE 9

    parsed=parse_response(final)
    st.session_state.last_parsed=parsed

    if parsed.get("type")=="table":
        raw_df=pd.DataFrame(parsed.get("data",[]),columns=parsed.get("columns",[]))
        st.session_state.last_df=raw_df
        st.session_state.chart_df=make_chart_df(raw_df)
    else:
        st.session_state.last_df=None; st.session_state.chart_df=None

    try:
        current_db_type=st.session_state.db_config.get("db_type","postgresql").lower()
        st.session_state.followups=get_followup_questions(active_query,db_type=current_db_type)
    except Exception:
        st.session_state.followups=["Show top 5 by revenue","Show monthly trend",
            "Compare this year vs last year","Show bottom 5 performers","Show total count of records"]

    a_text=""
    if parsed:
        if parsed.get("type")=="text": a_text=parsed.get("content",final)[:200]
        else:
            cols=parsed.get("columns",[]); rows=parsed.get("data",[])
            a_text=f"Table: {len(rows)} rows — {', '.join(cols[:3])}"
    st.session_state.query_log.append({"q":active_query,"a":a_text})
    if len(st.session_state.query_log)>50: st.session_state.query_log=st.session_state.query_log[-50:]

    if st.session_state.memory_on:
        st.session_state.history.append(HumanMessage(content=active_query))
        st.session_state.history.append(AIMessage(content=final))
        if len(st.session_state.history)>8: st.session_state.history=st.session_state.history[-8:]
        st.session_state.history_pairs.append({"q":active_query,"a":a_text})
        if len(st.session_state.history_pairs)>8: st.session_state.history_pairs=st.session_state.history_pairs[-8:]

# ── FEATURES 5,6,9: Meta bar ──────────────────────────────
parsed=st.session_state.last_parsed
if st.session_state.last_response:
    meta_parts=[]
    if st.session_state.last_query_tag:
        tag=st.session_state.last_query_tag
        meta_parts.append(f'<span class="tag-badge tag-{tag}">🏷️ {tag}</span>')
    if st.session_state.last_resp_time is not None:
        meta_parts.append(f"⏱️ Response: <b>{st.session_state.last_resp_time}s</b>")
    if st.session_state.last_fetch_time:
        meta_parts.append(f"🌡️ Fetched at: <b>{st.session_state.last_fetch_time}</b>")
    if meta_parts:
        st.markdown(
            f'<div class="meta-bar">{"&nbsp;&nbsp;|&nbsp;&nbsp;".join(meta_parts)}</div>',
            unsafe_allow_html=True)

# ── Confidence score ───────────────────────────────────────
if parsed and st.session_state.last_response:
    score=calc_confidence(parsed,st.session_state.last_df)
    color="#48cae4" if score>=80 else "#ffd93d" if score>=60 else "#ff6b6b"
    st.markdown(
        f'<div class="confidence-bar">🎯 <b>AI Confidence:</b> '
        f'<span style="color:{color};font-weight:700">{score}%</span> — '
        f'{"High confidence" if score>=80 else "Moderate confidence" if score>=60 else "Low — verify result"}'
        f'</div>',unsafe_allow_html=True)

# ── KPI Cards ──────────────────────────────────────────────
if parsed and isinstance(parsed,dict):
    kpis=parsed.get("kpis",[])
    if kpis:
        st.subheader("📌 Key Metrics")
        kpi_cols=st.columns(len(kpis))
        for i,kpi in enumerate(kpis):
            with kpi_cols[i]:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value">{kpi.get("value","—")}</div><div class="kpi-label">{kpi.get("label","")}</div></div>',unsafe_allow_html=True)
        st.markdown("")

if parsed and isinstance(parsed,dict) and parsed.get("summary"):
    st.info(f"💡 {parsed['summary']}")

# ── Data table ─────────────────────────────────────────────
if st.session_state.last_df is not None:
    df=st.session_state.last_df
    st.subheader("📊 Structured Result")

    # FEATURE 7: Row limiter slider
    total_rows=len(df)
    if total_rows > 10:
        row_limit=st.slider("📏 Show rows",min_value=5,max_value=total_rows,
            value=min(25,total_rows),step=5,key="row_limit_slider")
    else:
        row_limit=total_rows

    # FEATURE 1 + 3: Copy button + searchable table
    show_copy_button(df)
    show_searchable_table(df, row_limit=row_limit)

    # Stats panel
    show_stats_panel(df)

    # Anomaly detection
    anomalies=detect_anomalies(df)
    if anomalies:
        st.subheader("⚠️ Data Anomalies")
        for atype,col,label,val in anomalies:
            icon="🔺" if atype=="high" else "🔻"
            css="anomaly-high" if atype=="high" else "anomaly-low"
            st.markdown(f'<span class="{css}">{icon} Unusual {atype} in <b>{col}</b>: <b>{label}</b> = {val:,.0f}</span>',unsafe_allow_html=True)
        st.markdown("")

    # Pin button
    pc1,pc2=st.columns([3,1])
    with pc2:
        if st.button("📌 Pin This Result",use_container_width=True):
            st.session_state.pinned_result={"query":st.session_state.last_run_query,"parsed":st.session_state.last_parsed,"df":df.copy()}
            st.success("Pinned!")

    if st.session_state.get("permissions",{}).get("can_download",True):
        csv=df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV (Power BI)",data=csv,file_name="insight_data.csv",mime="text/csv")

# ── Visualization ──────────────────────────────────────────
if st.session_state.chart_df is not None:
    cdf=st.session_state.chart_df
    num_cols=cdf.select_dtypes(include="number").columns.tolist()
    all_cols=cdf.columns.tolist()
    if not num_cols and all_cols:
        lc=all_cols[-1]
        cdf[lc]=pd.to_numeric(cdf[lc].astype(str).str.replace(",","",regex=False).str.strip(),errors="coerce")
        st.session_state.chart_df=cdf
        num_cols=cdf.select_dtypes(include="number").columns.tolist()
    if num_cols:
        st.subheader("📈 Interactive Visualization")
        vc1,vc2,vc3=st.columns(3)
        with vc1: chart_type=st.selectbox("Chart Type",["Bar","Horizontal Bar","Line","Area","Pie","Donut","Treemap","Scatter"],key="viz_chart_type")
        with vc2: val_col=st.selectbox("Value",num_cols,index=len(num_cols)-1,key="viz_value_col")
        with vc3:
            lbl_options=[c for c in all_cols if c!=val_col] or all_cols
            lbl_col=st.selectbox("Label/Group",lbl_options,key="viz_label_col")
        theme=st.session_state.chart_theme
        scale=CHART_THEMES[theme]["scale"]
        title=f"{val_col} by {lbl_col}"; fig=None
        if   chart_type=="Bar": fig=px.bar(cdf,x=lbl_col,y=val_col,color=val_col,color_continuous_scale=scale,title=title,text_auto=True)
        elif chart_type=="Horizontal Bar": fig=px.bar(cdf,x=val_col,y=lbl_col,orientation="h",color=val_col,color_continuous_scale=scale,title=title,text_auto=True)
        elif chart_type=="Line": fig=px.line(cdf,x=lbl_col,y=val_col,markers=True,title=title)
        elif chart_type=="Area": fig=px.area(cdf,x=lbl_col,y=val_col,title=title)
        elif chart_type=="Pie": fig=px.pie(cdf,names=lbl_col,values=val_col,title=title)
        elif chart_type=="Donut": fig=px.pie(cdf,names=lbl_col,values=val_col,hole=0.45,title=title)
        elif chart_type=="Treemap": fig=px.treemap(cdf,path=[lbl_col],values=val_col,title=title)
        elif chart_type=="Scatter": fig=px.scatter(cdf,x=lbl_col,y=val_col,color=val_col,color_continuous_scale=scale,title=title)
        if fig:
            fig=apply_theme(fig,theme)
            st.plotly_chart(fig,use_container_width=True)
            try:
                fig.write_image("chart_export.png",width=900,height=500,scale=2)
                st.session_state.chart_path="chart_export.png"
            except Exception: pass

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
            pdf_file=create_pdf(p,st.session_state.last_run_query or "",chart_path=st.session_state.get("chart_path"))
            with open(pdf_file,"rb") as f:
                st.download_button("📄 Download Report (PDF)",data=f,file_name="Insight_Report.pdf",mime="application/pdf")
        except Exception as e:
            st.caption(f"PDF note: {e}")
