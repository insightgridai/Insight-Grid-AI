from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=80,
                  max_retries=1, request_timeout=15)

_FALLBACK = [
    "Show top 5 by revenue",
    "Show monthly trend",
    "Compare this year vs last year",
    "Show bottom 5 performers",
]

def get_followup_questions(query: str) -> list[str]:
    try:
        r = _llm.invoke([
            SystemMessage(content=(
                "Generate 4 short follow-up business questions. "
                "Max 7 words each. One per line. No numbers or bullets."
            )),
            HumanMessage(content=str(query)[:150]),
        ]).content
        qs = [x.strip() for x in r.split("\n") if x.strip()]
        return qs[:4] if qs else _FALLBACK
    except Exception:
        return _FALLBACK
