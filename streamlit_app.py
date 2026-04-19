import streamlit as st
import pandas as pd
import json
import plotly.express as px
from fpdf import FPDF

from langchain_core.messages import HumanMessage

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

st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "db_connected" not in st.session_state:
    st.session_state.db_connected = False

if "db_config" not in st.session_state:
    st.session_state.db_config = {}

if "last_df" not in st.session_state:
    st.session_state.last_df = None

if "last_response" not in st.session_state:
    st.session_state.last_response = ""

if "followups" not in st.session_state:
    st.session_state.followups = []


# -------------------------------------------------
# DB POPUP (FIXED)
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

            st.success("Database Connected Successfully ✅")

            # Refresh UI + close dialog
            st.rerun()

        except Exception as e:
            st.error(f"Connection Failed ❌ {str(e)}")


# -------------------------------------------------
# TOP BAR
# -------------------------------------------------
col1, col2 = st.columns([8, 2])

with col2:
    if st.button("🔌 Connect DB"):
        db_popup()

if st.session_state.db_connected:
    st.success("Connected ✅")
else:
    st.warning("Not Connected")


# -------------------------------------------------
# QUERY INPUT
# -------------------------------------------------
query = st.text_area(
    "Ask your business question",
    height=120,
    placeholder="Example: Show top 10 customers for latest year"
)

run = st.button("🚀 Run Analysis")


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
# VISUALS
# -------------------------------------------------
def show_visual(df):

    num_cols = df.select_dtypes(include="number").columns

    if len(num_cols) == 0:
        return

    value_col = num_cols[-1]
    label_col = [c for c in df.columns if c != value_col][0]

    chart = st.selectbox(
        "Choose Visual",
        ["Bar", "Line", "Pie", "Treemap"]
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


# -------------------------------------------------
# MAIN RUN
# -------------------------------------------------
if run:

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

    with st.spinner("Running AI Agents..."):

        app = get_supervisor_app(
            st.session_state.db_config
        )

        result = app.invoke({
            "messages": [HumanMessage(content=query)],
            "step": 0
        })

        messages = result["messages"]

        final_text = ""

        for msg in reversed(messages):
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

                st.subheader("📊 Result")
                st.dataframe(df, use_container_width=True)

                st.subheader("📈 Visual")
                show_visual(df)

            elif parsed["type"] == "text":
                st.success(parsed["content"])

        else:
            st.code(final_text)

        # Follow-up questions
        st.session_state.followups = get_followup_questions(query)


# -------------------------------------------------
# KEEP LAST RESULT
# -------------------------------------------------
if st.session_state.last_df is not None and not run:

    st.subheader("📊 Last Result")
    st.dataframe(
        st.session_state.last_df,
        use_container_width=True
    )


# -------------------------------------------------
# FOLLOW-UP QUESTIONS
# -------------------------------------------------
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")

    for q in st.session_state.followups:
        st.button(q)


# -------------------------------------------------
# PDF DOWNLOAD
# -------------------------------------------------
if st.session_state.last_response:

    if st.button("📄 Download Report"):

        pdf = FPDF()
        pdf.add_page()

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Insight Grid AI Report", ln=True)

        pdf.ln(10)

        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, st.session_state.last_response)

        pdf.output("report.pdf")

        with open("report.pdf", "rb") as f:
            st.download_button(
                "Download PDF",
                f,
                file_name="report.pdf"
            )
