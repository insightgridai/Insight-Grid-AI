from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=60,        # 4 short questions = ~60 tokens max
    max_retries=1,
    request_timeout=15,
)

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
                "4 follow-up questions. Max 6 words each. "
                "One per line. No numbers."
            )),
            HumanMessage(content=query[:100]),
        ]).content
        qs = [x.strip() for x in r.split("\n") if x.strip()]
        return qs[:4] if qs else _FALLBACK
    except Exception:
        return _FALLBACK
