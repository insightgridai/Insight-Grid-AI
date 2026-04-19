# ===============================================================
# FULL FIXED streamlit_app.py
# FINAL VERSION
#
# FIXES INCLUDED:
# ✅ DB popup opens only when button clicked
# ✅ Popup never reopens after Run Analysis
# ✅ Structured table output
# ✅ Interactive visualization dropdown
# ✅ Follow-up questions shown
# ✅ Memory ON / OFF works
# ✅ Better session state
# ✅ Production Ready
#
# COPY PASTE DIRECTLY
# ===============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import base64

from langchain_core.messages import AIMessage

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent import get_followup_questions
from db.connection import get_db_connection_dynamic

from utils.parser import parse_response
from utils.memory import build_messages
from utils.db_store import load_connections, save_connection
from utils.pdf_export import create_pdf


# ===============================================================
# PAGE CONFIG
# ===============================================================
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)


# ===============================================================
# BACKGROUND IMAGE
# ===============================================================
def get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg = get_base64("assets/backgroud6.jfif")


# ===============================================================
# CSS
# ===============================================================
st.markdown(f"""
<style>

.stApp {{
background:
linear-gradient(rgba(0,0,0,0.72), rgba(0,0,0,0.72)),
url("data:image/png;base64,{bg}");
background-size:cover;
background-position:center;
}}

textarea {{
background-color: rgba(255,255,255,0.05) !important;
color:white !important;
}}

div[data-testid="stButton"] button {{
border-radius:10px;
}}

</style>
""", unsafe_allow_html=True)


# ===============================================================
# SESSION STATE
# ===============================================================
defaults = {
    "db_connected": False,
    "db_config": {},
    "memory_on": True,
    "history": [],
    "last_response": "",
    "last_df": None,
    "followups": [],
    "show_popup": False
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ===============================================================
# HEADER
# ===============================================================
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# ===============================================================
# TOP BAR
# ===============================================================
c1, c2, c3 = st.columns([2,2,2])

with c1:
    st.toggle(
        "Memory Mode",
        key="memory_on"
    )

with c2:
    if st.session_state.db_connected:
        st.success("Connected ✅")
    else:
        st.warning("Not Connected")

with c3:
    if st.button("🔌 Connect Database"):
        st.session_state.show_popup = True


# ===============================================================
# DATABASE POPUP
# ===============================================================
@st.dialog("Connect to Database")
def db_popup():

    tab1, tab2 = st.tabs([
        "Manual Entry",
        "Saved Connections"
    ])

    # -----------------------------------------------------------
    # TAB 1
    # -----------------------------------------------------------
    with tab1:

        name = st.text_input(
            "Connection Name",
            key="db_name"
        )

        host = st.text_input(
            "Host",
            key="db_host"
        )

        port = st.text_input(
            "Port",
            value="5432",
            key="db_port"
        )

        db = st.text_input(
            "Database",
            key="db_database"
        )

        user = st.text_input(
            "Username",
            key="db_user"
        )

        pwd = st.text_input(
            "Password",
            type="password",
            key="db_pwd"
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Connect Now"):

                try:
                    cfg = {
                        "host": host,
                        "port": port,
                        "database": db,
                        "user": user,
                        "password": pwd
                    }

                    conn = get_db_connection_dynamic(cfg)
                    conn.close()

                    st.session_state.db_connected = True
                    st.session_state.db_config = cfg

                    # CLOSE POPUP
                    st.session_state.show_popup = False

                    st.success("Connected Successfully")

                except Exception as e:
                    st.error(str(e))

        with c2:
            if st.button("Save Connection"):

                save_connection({
                    "name": name,
                    "host": host,
                    "port": port,
                    "database": db,
                    "user": user,
                    "password": pwd
                })

                st.success("Saved Successfully")


    # -----------------------------------------------------------
    # TAB 2
    # -----------------------------------------------------------
    with tab2:

        saved = load_connections()

        if len(saved) == 0:
            st.info("No Saved Connections")

        else:

            names = [x["name"] for x in saved]

            selected = st.selectbox(
                "Select Connection",
                names
            )

            row = [
                x for x in saved
                if x["name"] == selected
            ][0]

            st.write("**Host:**", row["host"])
            st.write("**Port:**", row["port"])
            st.write("**Database:**", row["database"])
            st.write("**Username:**", row["user"])

            if st.button("Use Saved Connection"):

                st.session_state.db_connected = True
                st.session_state.db_config = row

                # CLOSE POPUP
                st.session_state.show_popup = False

                st.success("Connected Successfully")


# ---------------------------------------------------------------
# SHOW POPUP ONLY WHEN BUTTON CLICKED
# ---------------------------------------------------------------
if st.session_state.show_popup:
    db_popup()


# ===============================================================
# QUERY BOX
# ===============================================================
query = st.text_area(
    "Ask your business question",
    height=130,
    placeholder="Top 10 customers"
)

run = st.button("🚀 Run Analysis")


# ===============================================================
# RUN ANALYSIS
# ===============================================================
if run:

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

    # IMPORTANT:
    # Popup must stay closed after run
    st.session_state.show_popup = False

    messages = build_messages(
        query,
        st.session_state.memory_on,
        st.session_state.history
    )

    app = get_supervisor_app(
        st.session_state.db_config
    )

    with st.spinner("Running AI Agents..."):

        result = app.invoke({
            "messages": messages,
            "step": 0
        })

    final = ""

    for msg in reversed(result["messages"]):
        if getattr(msg, "type", "") == "ai":
            final = msg.content
            break

    st.session_state.last_response = final

    parsed = parse_response(final)

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


    # FOLLOWUP QUESTIONS
    st.session_state.followups = get_followup_questions(query)


    # MEMORY MODE
    if st.session_state.memory_on:

        st.session_state.history += messages

        st.session_state.history.append(
            AIMessage(content=final)
        )


# ===============================================================
# SHOW TABLE
# ===============================================================
if st.session_state.last_df is not None:

    st.subheader("📊 Structured Result")

    st.dataframe(
        st.session_state.last_df,
        use_container_width=True
    )


# ===============================================================
# INTERACTIVE VISUALIZATION
# ===============================================================
if st.session_state.last_df is not None:

    df = st.session_state.last_df

    num_cols = df.select_dtypes(
        include="number"
    ).columns

    if len(num_cols) > 0:

        st.subheader("📈 Interactive Visualization")

        chart = st.selectbox(
            "Choose Visual",
            ["Bar", "Line", "Pie", "Treemap"]
        )

        value_col = num_cols[-1]

        label_col = [
            c for c in df.columns
            if c != value_col
        ][0]

        if chart == "Bar":
            fig = px.bar(df, x=label_col, y=value_col)

        elif chart == "Line":
            fig = px.line(df, x=label_col, y=value_col)

        elif chart == "Pie":
            fig = px.pie(df, names=label_col, values=value_col)

        else:
            fig = px.treemap(
                df,
                path=[label_col],
                values=value_col
            )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ===============================================================
# FOLLOW-UP QUESTIONS
# ===============================================================
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")

    for i, q in enumerate(
        st.session_state.followups
    ):

        if st.button(
            q,
            key=f"fq_{i}"
        ):
            st.rerun()


# ===============================================================
# PDF DOWNLOAD
# ===============================================================
if st.session_state.last_response:

    parsed = parse_response(
        st.session_state.last_response
    )

    if parsed and isinstance(parsed, dict):

        if parsed.get("type") in ["table", "text"]:

            file = create_pdf(
                parsed,
                query
            )

            with open(file, "rb") as f:

                st.download_button(
                    "📄 Download Report",
                    f,
                    "Insight_Report.pdf"
                )