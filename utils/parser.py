import json, re

def parse_response(response: str) -> dict:
    """Always returns a dict. Never returns None."""
    if not response or not response.strip():
        return {"type":"text","content":"No response received.","kpis":[],"summary":""}

    text = response.strip()

    # Remove markdown code fences first
    text_clean = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

    # Try to extract JSON object
    s = text_clean.find("{")
    e = text_clean.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            p = json.loads(text_clean[s:e])
            if isinstance(p, dict):
                p.setdefault("kpis",    [])
                p.setdefault("summary", "")
                p.setdefault("type",    "text")
                # Validate table has actual data
                if p.get("type") == "table":
                    if not p.get("columns") or not p.get("data"):
                        p["type"]    = "text"
                        p["content"] = p.get("summary") or "No table data returned."
                return p
        except Exception:
            pass

    # Fallback — return raw text
    return {"type": "text", "content": text, "kpis": [], "summary": ""}
