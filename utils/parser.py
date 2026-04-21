# utils/parser.py — never returns None

import json, re

def parse_response(response: str) -> dict:
    if not response or not response.strip():
        return {"type":"text","content":"No response received.","kpis":[],"summary":""}
    text = response.strip()
    # Try bare JSON
    s, e = text.find("{"), text.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            p = json.loads(text[s:e])
            if isinstance(p, dict):
                p.setdefault("kpis",    [])
                p.setdefault("summary", "")
                p.setdefault("type",    "text")
                if p["type"] == "table" and (not p.get("columns") or not p.get("data")):
                    p["type"] = "text"
                    p["content"] = p.get("summary") or text
                return p
        except Exception:
            pass
    # Try code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            p = json.loads(m.group(1))
            if isinstance(p, dict):
                p.setdefault("kpis",[]); p.setdefault("summary",""); p.setdefault("type","text")
                return p
        except Exception:
            pass
    # Fallback
    return {"type":"text","content":text,"kpis":[],"summary":""}
