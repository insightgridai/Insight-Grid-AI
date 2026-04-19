from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# ---------------------------------------------------
# LLM
# ---------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini")


# ---------------------------------------------------
# GENERATOR
# ---------------------------------------------------
def get_followup_questions(user_query: str):

    system_prompt = """
You generate smart business follow-up questions.

RULES:
1. Based on user's original question.
2. Return exactly 4 follow-up questions.
3. Keep each short.
4. Must be relevant analytical next steps.
5. No numbering.
6. One per line.

Example:

User:
Show top 10 customers latest year

Output:
Show top 10 customers previous year
Compare latest year vs previous year customers
Show top customers by region
Monthly trend for top customers
"""

    msgs = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ]

    response = llm.invoke(msgs).content

    lines = [
        x.strip()
        for x in response.split("\n")
        if x.strip()
    ]

    return lines[:4]
