import streamlit as st
import pandas as pd
import json
import plotly.express as px
from fpdf import FPDF
from langchain_core.messages import HumanMessage
import base64

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
# BOTTOM IMAGE ONLY
# Save image in assets/background.png
# -------------------------------------------------
def get_base64_image(image_path):
    with open(image_path, "rb") as img:
        return base64.b64encode(img.read()).decode()


bg_img = get_base64_image("assets/backgroud6.jfif")

st.markdown(
    f"""
    <style>

    .stApp {{
        background: linear-gradient(
            90deg,
            #050814,
            #081426,
            #0b1020
        );
    }}

    .bottom-banner {{
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 220px;
        background-image: url("data:image/png;base64,{bg_img}");
        background-size: cover;
        background-position: center bottom;
        background-repeat: no-repeat;
        z-index: -1;
        opacity: 0.95;
    }}

    .block-container {{
        padding-top: 2rem;
        padding-bottom: 240px;
    }}

    div[data-testid="stButton"] button {{
        border-radius: 10px;
    }}

    textarea {{
        background-color: rgba(255,255,255,0.06) !important;
        color: white !important;
    }}

    </style>

    <div class="bottom-banner"></div>
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
    "auto_run": False
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -------------------------------------------------
# RESPONSE PARSER
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
@st.dialog("Connect to PostgreSQL Database")
def db_popup():

    host = st.text_input("Host")
    port = st.text_input("Port", value="5432")
    db = st.text_input("Database")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    if st.button("Connect Now"):

        try:
            config = {
                "host": host,
                "port": port,
                "database": db,
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

            st.rerun()

        except Exception as e:
            st.error(str(e))


# -------------------------------------------------
# TOP BAR
# -------------------------------------------------
c1, c2 = st.columns([8, 2])

with c2:
    if st.button("🔌 Connect DB"):
        db_popup()

if st.session_state.db_connected:
    st.success("Connected ✅")
else:
    st.warning("Not Connected")


# -------------------------------------------------
# APPLY PENDING FOLLOWUP
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
# VISUAL FUNCTION
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
# RUN QUERY
# -------------------------------------------------
should_run = run or st.session_state.auto_run

if should_run:

    st.session_state.auto_run = False

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

    with st.spinner("Running AI Agents..."):

        app = get_supervisor_app(
            st.session_state.db_config
        )

        result = app.invoke({
            "messages": [
                HumanMessage(content=st.session_state.query_text)
            ],
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

                df = pd.DataFrame(
                    parsed["data"],
                    columns=parsed["columns"]
                )

                st.session_state.last_df = df
                st.session_state.chart_df = df

            elif parsed["type"] == "text":

                st.session_state.last_df = None
                st.session_state.chart_df = None

        st.session_state.followups = get_followup_questions(
            st.session_state.query_text
        )


# -------------------------------------------------
# RESULT
# -------------------------------------------------
if st.session_state.last_df is not None:

    st.subheader("📊 Result")

    st.dataframe(
        st.session_state.last_df,
        use_container_width=True
    )


# -------------------------------------------------
# VISUAL
# -------------------------------------------------
fig = None

if st.session_state.chart_df is not None:

    st.subheader("📈 Interactive Visual")

    fig = show_visual(
        st.session_state.chart_df
    )


# -------------------------------------------------
# FOLLOWUP QUESTIONS
# -------------------------------------------------
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")

    for i, q in enumerate(st.session_state.followups):

        if st.button(q, key=f"fq_{i}"):

            st.session_state.pending_query = q
            st.session_state.auto_run = True
            st.rerun()


# -------------------------------------------------
# PDF EXPORT
# -------------------------------------------------
if st.session_state.last_response:

    parsed = parse_response(
        st.session_state.last_response
    )

    if parsed:

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)

        pdf.ln(5)

        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(
            0,
            8,
            f"Query: {st.session_state.query_text}"
        )

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
                    pdf.cell(
                        col_width,
                        8,
                        str(item)[:22],
                        border=1
                    )
                pdf.ln()

            if fig:
                try:
                    fig.write_image("chart.png")
                    pdf.ln(8)
                    pdf.image("chart.png", x=10, w=190)
                except:
                    pass

        elif parsed["type"] == "text":

            pdf.multi_cell(
                0,
                8,
                parsed["content"]
            )

        pdf.output("report.pdf")

        with open("report.pdf", "rb") as f:
            st.download_button(
                "📄 Download Report",
                data=f,
                file_name="Insight_Report.pdf",
                mime="application/pdf"
            )
