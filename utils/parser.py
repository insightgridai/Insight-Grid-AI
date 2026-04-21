# =============================================================
# utils/parser.py
# Robust response parser — never returns None for valid text
# FIX: If JSON parse fails, wrap raw text in a text-type dict
#      so "Could not format result" never appears
# =============================================================

import json
import re


def parse_response(response: str) -> dict:
    """
    Parse the AI agent's response into a structured dict.

    Priority:
    1. Find and parse embedded JSON  → return as-is
    2. Try JSON inside ```json ... ``` code block
    3. Fallback — wrap raw text in {"type":"text",...}
       so the UI always has something to render.

    Returns a dict — NEVER None.
    """
    if not response or not response.strip():
        return {
            "type": "text",
            "content": "No response received.",
            "kpis": [],
            "summary": ""
        }

    text = response.strip()

    # ── Step 1: Extract bare JSON object ─────────────────────
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, dict):
                parsed.setdefault("kpis",    [])
                parsed.setdefault("summary", "")
                if "type" not in parsed:
                    parsed["type"] = "text"
                # Degrade table→text if columns/data missing
                if parsed["type"] == "table":
                    if not parsed.get("columns") or not parsed.get("data"):
                        parsed["type"]    = "text"
                        parsed["content"] = parsed.get("summary") or text
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Step 2: JSON inside code fences ──────────────────────
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

    # ── Step 3: Fallback — show raw text in UI ───────────────
    clean = re.sub(r"\{[^}]{0,30}$", "", text).strip() or text
    return {
        "type":    "text",
        "content": clean,
        "kpis":    [],
        "summary": ""
    }
