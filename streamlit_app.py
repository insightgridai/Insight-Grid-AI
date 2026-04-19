# -----------------------------------------
# MAIN STREAMLIT APP
# -----------------------------------------

import streamlit as st
import pandas as pd
import plotly.express as px
from langchain_core.messages import AIMessage

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent import get_followup_questions
from db.connection import get_db_connection_dynamic

from utils.cache import load_bg
from utils.parser import parse_response
from utils.memory import build_messages
from utils.db_store import load_connections, save_connection
from utils.pdf_export import create_pdf


# -----------------------------------------
# Page config
# -----------------------------------------
st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide"
)

# -----------------------------------------
# Background image
# -----------------------------------------
bg = load_bg("assets/backgroud6.jfif")

st.markdown(f"""
<style>
.stApp {{
background:
linear-gradient(rgba(0,0,0,0.65),rgba(0,0,0,0.65)),
url("data:image/png;base64,{bg}");
background-size:cover;
}}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------
# Session state defaults
# -----------------------------------------
defaults = {
    "db_connected": False,
    "db_config": {},
    "history": [],
    "memory_on": True,
    "last_response": "",
    "last_df": None,
    "followups": []
}

for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -----------------------------------------
# Header
# -----------------------------------------
st.title("🤖 Insight Grid AI")
st.caption("Where Data, Agents and Decisions Connect")


# -----------------------------------------
# Top Bar
# -----------------------------------------
c1,c2,c3 = st.columns([3,2,2])

with c1:
    st.toggle("Memory Mode", key="memory_on")

with c2:
    if st.session_state.db_connected:
        st.success("Connected ✅")
    else:
        st.warning("Not Connected")

with c3:
    open_db = st.button("Connect Database")


# -----------------------------------------
# DB Panel
# -----------------------------------------
if open_db:

    tab1,tab2 = st.tabs(["Connect Now","Saved"])

    with tab1:

        name = st.text_input("Save Name")
        host = st.text_input("Host")
        port = st.text_input("Port", "5432")
        db = st.text_input("Database")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")

        if st.button("Connect"):

            cfg = {
                "host":host,
                "port":port,
                "database":db,
                "user":user,
                "password":pwd
            }

            conn = get_db_connection_dynamic(cfg)
            conn.close()

            st.session_state.db_connected = True
            st.session_state.db_config = cfg

            st.success("Connected Successfully")

        if st.button("Save"):

            save_connection({
                "name":name,
                "host":host,
                "port":port,
                "database":db,
                "user":user,
                "password":pwd
            })

    with tab2:

        data = load_connections()

        if data:

            names = [x["name"] for x in data]
            selected = st.selectbox("Saved Connections", names)

            row = [x for x in data if x["name"] == selected][0]

            if st.button("Use Saved"):

                st.session_state.db_connected = True
                st.session_state.db_config = row


# -----------------------------------------
# Query box
# -----------------------------------------
query = st.text_area(
    "Ask your business question",
    height=130
)

run = st.button("🚀 Run Analysis")


# -----------------------------------------
# Run Agents
# -----------------------------------------
if run:

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

    if st.session_state.memory_on:

        st.session_state.history += messages
        st.session_state.history.append(
            AIMessage(content=final)
        )


# -----------------------------------------
# Show Result
# -----------------------------------------
if st.session_state.last_df is not None:

    st.subheader("📊 Result")

    st.dataframe(
        st.session_state.last_df,
        use_container_width=True
    )

    num = st.session_state.last_df.select_dtypes(include="number").columns

    if len(num) > 0:

        val = num[-1]
        lab = [c for c in st.session_state.last_df.columns if c != val][0]

        fig = px.bar(
            st.session_state.last_df,
            x=lab,
            y=val
        )

        st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------
# Follow-up Buttons
# -----------------------------------------
if st.session_state.followups:

    st.subheader("💡 Follow-up Questions")

    for i,q in enumerate(st.session_state.followups):

        if st.button(q, key=f"f{i}"):
            st.rerun()


# -----------------------------------------
# Download PDF
# -----------------------------------------
if st.session_state.last_response:

    parsed = parse_response(
        st.session_state.last_response
    )

    if parsed:

        file = create_pdf(parsed, query)

        with open(file, "rb") as f:

            st.download_button(
                "📄 Download Report",
                f,
                "Insight_Report.pdf"
            )