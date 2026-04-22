# agents/followup_agent.py
# Generates 5 specific, meaningful follow-up questions
# relevant to the user's actual query and database context.

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,      # slight creativity for varied questions
    max_tokens=120,       # enough for 5 questions
    max_retries=1,
    request_timeout=15,
)

_FALLBACK_ECOMMERCE = [
    "Show top 10 customers by total revenue",
    "Which product category has highest sales",
    "Show monthly revenue trend for 2021",
    "Which stores have highest sales this year",
    "Show total sales by payment type",
]

_FALLBACK_OILGAS = [
    "Show total oil production by field",
    "Which wells have highest production BBL",
    "Compare onshore vs offshore production",
    "Show monthly production trend for 2025",
    "Which wells have status Producing now",
]


def get_followup_questions(query: str, db_type: str = "postgresql") -> list[str]:
    """
    Generate 5 specific follow-up questions based on the user's query.
    db_type: 'postgresql' or 'snowflake'
    """
    fallback = _FALLBACK_OILGAS if db_type == "snowflake" else _FALLBACK_ECOMMERCE

    if db_type == "snowflake":
        context = (
            "Database: Oil & Gas production data. "
            "Tables: OIL_GAS_PRODUCTION with columns FIELD_ID, FIELD_NAME, WELL_ID, "
            "LOCATION, DATE, OIL_PRODUCTION_BBL, GAS_PRODUCTION_MCF, "
            "WATER_PRODUCTION_BBL, Water_Cut_%, API_GRAVITY, STATUS."
        )
    else:
        context = (
            "Database: E-commerce data. "
            "Tables: customer_dim, item_dim, sales_fact, store_dim, time_dim, trans_dim."
        )

    try:
        r = _llm.invoke([
            SystemMessage(content=(
                f"{context}\n\n"
                "The user just asked: the query below.\n"
                "Generate exactly 5 specific follow-up business questions "
                "that would give useful insights from this database.\n"
                "Rules:\n"
                "- Max 10 words per question\n"
                "- Each question must be answerable from the database\n"
                "- Questions must be different from each other\n"
                "- One question per line\n"
                "- No numbers, bullets, or extra text\n"
                "- Make questions specific to the data context"
            )),
            HumanMessage(content=str(query)[:200]),
        ]).content

        qs = [x.strip() for x in r.strip().split("\n") if x.strip()]
        # Clean any leading numbers/bullets like "1." or "-"
        cleaned = []
        for q in qs:
            q = q.lstrip("0123456789.-) ").strip()
            if q:
                cleaned.append(q)
        return cleaned[:5] if len(cleaned) >= 3 else fallback

    except Exception:
        return fallback
