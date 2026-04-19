# ==========================================================
# FULL streamlit_app.py
# FIXED VERSION (No DuplicateElementId Error)
# Popup + Manual Entry + Saved Dropdown + Memory + Multi Agent
# COPY PASTE DIRECTLY
# ==========================================================

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


# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)


# ==========================================================
# BACKGROUND IMAGE
# ==========================================================
def get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg = get_base64("assets/backgroud6.jfif")


# ==========================================================
# CSS
# ==========================================================
st.markdown(f"""
<style>

.stApp {{
    background:
        linear-gradient(rgba(0,0,0,0.70), rgba(0,0,0,0.70)),
        url("data:image/png;base64,{bg}");
    background-size: cover;
    background-position: center;
}}

textarea {{
    background-color: rgba(255,255,255,0.06) !important;
    color: white !important;
}}

div[data-testid="stButton"] button {{
    border-radius: 10px;
}}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# SESSION STATE
# ==========================================================
defaults = {
    "db_connected": False,
    "db_config": {},
    "memory_on": True,
    "history": [],
    "last_response": "",
    "last_df": None,
    "followups": [],
    "open_popup": False
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==========================================================
# HEADER
# ==========================================================
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# ==========================================================
# TOP BAR
# ==========================================================
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
    if st.button("🔌 Connect Database", key="open_db_btn"):
        st.session_state.open_popup = True


# ==========================================================
# DATABASE POPUP
# ==========================================================
@st.dialog("Connect to Database")
def db_popup():

    tab1, tab2 = st.tabs([
        "Manual Entry",
        "Saved Connections"
    ])

    # ------------------------------------------------------
    # TAB 1 - MANUAL ENTRY
    # ------------------------------------------------------
    with tab1:

        st.subheader("Manual Entry")

        save_name = st.text_input(
            "Connection Name",
            key="manual_name"
        )

        host = st.text_input(
            "Host",
            key="manual_host"
        )

        port = st.text_input(
            "Port",
            value="5432",
            key="manual_port"
        )

        db = st.text_input(
            "Database",
            key="manual_db"
        )

        user = st.text_input(
            "Username",
            key="manual_user"
        )

        pwd = st.text_input(
            "Password",
            type="password",
            key="manual_pwd"
        )

        c1, c2 = st.columns(2)

        # CONNECT NOW
        with c1:
            if st.button(
                "Connect Now",
                key="manual_connect_btn"
            ):

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

                    st.success("Connected Successfully")

                except Exception as e:
                    st.error(str(e))

        # SAVE
        with c2:
            if st.button(
                "Save Connection",
                key="save_conn_btn"
            ):

                save_connection({
                    "name": save_name,
                    "host": host,
                    "port": port,
                    "database": db,
                    "user": user,
                    "password": pwd
                })

                st.success("Connection Saved")


    # ------------------------------------------------------
    # TAB 2 - SAVED CONNECTIONS
    # ------------------------------------------------------
    with tab2:

        st.subheader("Saved Connections")

        saved = load_connections()

        if len(saved) == 0:

            st.info("No saved connections")

        else:

            names = [x["name"] for x in saved]

            selected = st.selectbox(
                "Select Connection",
                names,
                key="saved_dropdown"
            )

            row = [
                x for x in saved
                if x["name"] == selected
            ][0]

            # USE WRITE INSTEAD OF TEXT INPUT
            st.write("**Host:**", row["host"])
            st.write("**Port:**", row["port"])
            st.write("**Database:**", row["database"])
            st.write("**Username:**", row["user"])

            if st.button(
                "Use Saved Connection",
                key="use_saved_btn"
            ):

                st.session_state.db_connected = True
                st.session_state.db_config = row

                st.success("Connected Successfully")


# OPEN POPUP
if st.session_state.open_popup:
    db_popup()


# ==========================================================
# QUERY BOX
# ==========================================================
query = st.text_area(
    "Ask your business question",
    height=130,
    placeholder="Show top 10 customers for latest year",
    key="main_query"
)

run = st.button(
    "🚀 Run Analysis",
    key="run_btn"
)


# ==========================================================
# RUN AGENTS
# ==========================================================
if run:

    if not st.session_state.db_connected:
        st.error("Please connect database first.")
        st.stop()

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

    if parsed and parsed["type"] == "table":

        df = pd.DataFrame(
            parsed["data"],
            columns=parsed["columns"]
        )

        st.session_state.last_df = df

    else:
        st.session_state.last_df = None

    st.session_state.followups = get_followup_questions(query)

    # MEMORY SAVE
    if st.session_state.memory_on:

        st.session_state.history += messages

        st.session_state.history.append(
            AIMessage(content=final)
        )


# ==========================================================
# SHOW RESULT
# ==========================================================
if st.session_state.last_df is not None:

    st.subheader("📊 Result")

    st.dataframe(
        st.session_state.last_df,
        use_container_width=True
    )

    # CHART
    num = st.session_state.last_df.select_dtypes(
        include="number"
    ).columns

    if len(num) > 0:

        val = num[-1]

        lab = [
            c for c in st.session_state.last_df.columns
            if c != val
        ][0]

        fig = px.bar(
            st.session_state.last_df,
            x=lab,
            y=val
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ==========================================================
# FOLLOWUP QUESTIONS
# ==========================================================
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")

    for i, q in enumerate(
        st.session_state.followups
    ):

        if st.button(
            q,
            key=f"followup_{i}"
        ):
            st.rerun()


# ==========================================================
# DOWNLOAD PDF
# ==========================================================
if st.session_state.last_response:

    parsed = parse_response(
        st.session_state.last_response
    )

    if parsed:

        file = create_pdf(
            parsed,
            query
        )

        with open(file, "rb") as f:

            st.download_button(
                "📄 Download Report",
                f,
                "Insight_Report.pdf",
                key="pdf_btn"
            )