# =============================================================
# streamlit_app.py  — Insight Grid AI FINAL (PDF + WORD EXPORT)
# =============================================================

import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px

from langchain_core.messages import AIMessage, HumanMessage

from agents.supervisor_agent import get_supervisor_app
from agents.followup_agent import get_followup_questions
from db.connection import test_connection

from utils.pdf_export import create_pdf
from utils.word_export import create_word


# =============================================================
# PAGE CONFIG
# =============================================================

st.set_page_config(
    page_title="Insight Grid AI",
    layout="wide",
    page_icon="📊"
)

# =============================================================
# SESSION STATE
# =============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_parsed" not in st.session_state:
    st.session_state.last_parsed = None

if "last_run_query" not in st.session_state:
    st.session_state.last_run_query = ""

if "chart_path" not in st.session_state:
    st.session_state.chart_path = None


# =============================================================
# TITLE
# =============================================================

st.title("📊 Insight Grid AI")
st.caption("AI Powered Analytics Assistant")

# =============================================================
# DB CHECK
# =============================================================

db_status = test_connection()

if db_status:
    st.success("✅ Database Connected")
else:
    st.error("❌ Database Connection Failed")


# =============================================================
# AGENT LOAD
# =============================================================

app = get_supervisor_app()


# =============================================================
# CHAT HISTORY
# =============================================================

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# =============================================================
# USER INPUT
# =============================================================

query = st.chat_input("Ask your business question...")

if query:

    st.session_state.messages.append(
        {"role": "user", "content": query}
    )

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            result = app.invoke(
                {
                    "messages": [
                        HumanMessage(content=query)
                    ]
                }
            )

            final_response = result["messages"][-1].content

            st.markdown(final_response)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": final_response
                }
            )

            # =====================================
            # Parse JSON if returned
            # =====================================

            try:
                parsed = json.loads(final_response)

                st.session_state.last_parsed = parsed
                st.session_state.last_run_query = query

                # =================================
                # TABLE
                # =================================
                if parsed.get("type") == "table":

                    df = pd.DataFrame(
                        parsed["data"],
                        columns=parsed["columns"]
                    )

                    st.dataframe(df, use_container_width=True)

                    # CSV
                    csv = df.to_csv(index=False).encode("utf-8")

                    st.download_button(
                        "📊 Download CSV",
                        data=csv,
                        file_name="Insight_Report.csv",
                        mime="text/csv"
                    )

                    # Chart Auto
                    if len(df.columns) >= 2:
                        try:
                            fig = px.bar(
                                df,
                                x=df.columns[0],
                                y=df.columns[1],
                                title="Visualization"
                            )

                            st.plotly_chart(
                                fig,
                                use_container_width=True
                            )

                            chart_path = "chart.png"
                            fig.write_image(chart_path)

                            st.session_state.chart_path = chart_path

                        except:
                            st.session_state.chart_path = None

                # =================================
                # TEXT OUTPUT
                # =================================
                elif parsed.get("type") == "text":
                    st.write(parsed.get("content", ""))

            except:
                st.session_state.last_parsed = {
                    "type": "text",
                    "content": final_response
                }

                st.session_state.last_run_query = query


# =============================================================
# EXPORT SECTION
# =============================================================

if st.session_state.last_parsed:

    st.divider()
    st.subheader("📥 Export Reports")

    col1, col2 = st.columns(2)

    # PDF
    with col1:

        pdf_file = create_pdf(
            st.session_state.last_parsed,
            st.session_state.last_run_query,
            st.session_state.chart_path
        )

        with open(pdf_file, "rb") as f:
            st.download_button(
                "📄 Download PDF",
                data=f,
                file_name="Insight_Report.pdf",
                mime="application/pdf"
            )

    # WORD
    with col2:

        word_file = create_word(
            st.session_state.last_parsed,
            st.session_state.last_run_query,
            st.session_state.chart_path
        )

        with open(word_file, "rb") as f:
            st.download_button(
                "📝 Download Word",
                data=f,
                file_name="Insight_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
