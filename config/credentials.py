# =============================================================
# config/credentials.py
# Pre-configured database connections
# Add / edit entries here — they appear in "Saved Connections"
# =============================================================

import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --------------------------------------------------------------
# Pre-built connections (auto-loaded into Saved Connections)
# --------------------------------------------------------------
PRESET_CONNECTIONS = [

    # ----------------------------------------------------------
    # E-Commerce PostgreSQL (Neon)
    # ----------------------------------------------------------
    {
        "name":     "E-Commerce DB",
        "db_type":  "postgresql",
        "host":     "ep-super-heart-a8d6wb15-pooler.eastus2.azure.neon.tech",
        "port":     "5432",
        "database": "azure",
        "user":     "neondb_owner",
        "password": "npg_rHCI4YmD9syR",
        "warehouse": "",
        "schema":   "",
        "role":     "",
        "account":  "",
    },

    # ----------------------------------------------------------
    # MultiAgentSystem PostgreSQL (Neon)
    # ----------------------------------------------------------
    {
        "name":     "MultiAgent DB",
        "db_type":  "postgresql",
        "host":     "ep-divine-voice-a8sbaqui-pooler.eastus2.azure.neon.tech",
        "port":     "5432",
        "database": "azure",
        "user":     "neondb_owner",
        "password": "npg_0xPkYVANU1Mf",
        "warehouse": "",
        "schema":   "",
        "role":     "",
        "account":  "",
    },

    # ----------------------------------------------------------
    # Snowflake
    # ----------------------------------------------------------
    {
        "name":      "Snowflake - InsightGrid",
        "db_type":   "snowflake",
        "account":   "dbcitil-nc64603",
        "user":      "INSIGHT",
        "password":  "insightgrid@2026",
        "warehouse": "COMPUTE_WH",
        "database":  "ENERGY",          # fill in your Snowflake DB name
        "schema":    "PUBLIC",
        "role":      "",
        "host":      "",
        "port":      "",
    },
]
