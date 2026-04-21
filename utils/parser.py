# utils/parser.py
# Robust parser — NEVER returns None.
# If JSON extraction fails, wraps raw text in text-type dict
# so UI always has something to render (no "Could not format result").

import json
import re


def parse_response(response: str) -> dict:
    if not response or not response.strip():
        return {"type": "text", "content": "No response received.", "kpis": [], "summary": ""}

    text = response.strip()

    # ── Try bare JSON object ──────────────────────────────
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, dict):
                parsed.setdefault("kpis",    [])
                parsed.setdefault("summary", "")
                parsed.setdefault("type",    "text")
                if parsed["type"] == "table":
                    if not parsed.get("columns") or not parsed.get("data"):
                        parsed["type"]    = "text"
                        parsed["content"] = parsed.get("summary") or text
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Try JSON in code fences ───────────────────────────
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict):
                parsed.setdefault("kpis",    [])
                parsed.setdefault("summary", "")
                parsed.setdefault("type",    "text")
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Fallback: show raw text ───────────────────────────
    clean = re.sub(r"\{[^}]{0,30}$", "", text).strip() or text
    return {"type": "text", "content": clean, "kpis": [], "summary": ""}
