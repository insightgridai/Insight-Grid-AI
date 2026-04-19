# -----------------------------------------
# Generate smart follow-up questions
# -----------------------------------------

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

llm = ChatOpenAI(model="gpt-4o-mini")

def get_followup_questions(query):

    msgs = [
        SystemMessage(content="""
Generate exactly 4 smart business follow-up questions.
No numbering.
One per line.
"""),
        HumanMessage(content=query)
    ]

    r = llm.invoke(msgs).content

    return [x.strip() for x in r.split("\n") if x.strip()][:4]