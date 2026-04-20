# =============================================================
# agents/followup_agent.py
# Generates 4 smart follow-up questions related to the query
# =============================================================

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)


def get_followup_questions(query: str) -> list[str]:

    msgs = [
        SystemMessage(content="""
You are a business intelligence assistant.

Given a user's analytics query, generate exactly 4 smart follow-up questions
a business analyst would ask next.

Rules:
- Each question must be actionable and data-driven
- Questions should drill deeper, compare, or look at trends
- No numbering, no bullet points
- One question per line
- Keep each question under 15 words
"""),
        HumanMessage(content=query)
    ]

    try:
        r = llm.invoke(msgs).content
        questions = [
            x.strip()
            for x in r.split("\n")
            if x.strip() and not x.strip()[0].isdigit()
        ]
        return questions[:4]
    except Exception:
        return [
            "What is the trend over the last 12 months?",
            "Which category contributes most to the total?",
            "How does this compare to the previous period?",
            "What are the bottom 5 performers?",
        ]
