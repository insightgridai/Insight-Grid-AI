# =============================================================
# utils/db_store.py
# Manages saved connections:
#   - Preset connections from config/credentials.py
#   - User-saved connections stored in saved_connections.json
# =============================================================

import json
import os

FILE = "saved_connections.json"


def load_connections() -> list[dict]:
    """Return preset + user-saved connections (no duplicates by name)."""

    # Load presets from credentials
    try:
        from config.credentials import PRESET_CONNECTIONS
        presets = PRESET_CONNECTIONS
    except Exception:
        presets = []

    # Load user-saved from file
    saved = []
    if os.path.exists(FILE):
        try:
            with open(FILE, "r") as f:
                saved = json.load(f)
        except Exception:
            saved = []

    # Merge: user-saved overrides preset with same name
    preset_names = {p["name"] for p in presets}
    merged = list(presets)  # start with presets

    for item in saved:
        if item["name"] in preset_names:
            # Replace preset with user version
            merged = [x for x in merged if x["name"] != item["name"]]
        merged.append(item)

    return merged


def save_connection(data: dict):
    """Save or update a connection in the local JSON file."""

    # Load only user-saved (not presets)
    saved = []
    if os.path.exists(FILE):
        try:
            with open(FILE, "r") as f:
                saved = json.load(f)
        except Exception:
            saved = []

    # Remove existing entry with same name
    saved = [x for x in saved if x["name"] != data["name"]]
    saved.append(data)

    with open(FILE, "w") as f:
        json.dump(saved, f, indent=2)


def delete_connection(name: str):
    """Delete a user-saved connection by name."""
    saved = []
    if os.path.exists(FILE):
        try:
            with open(FILE, "r") as f:
                saved = json.load(f)
        except Exception:
            saved = []

    saved = [x for x in saved if x["name"] != name]

    with open(FILE, "w") as f:
        json.dump(saved, f, indent=2)
