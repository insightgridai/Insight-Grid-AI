# =============================================================
# auth/users.py
# User store — hashed passwords + roles
#
# ROLES:
#   admin  — full access: connect DB, run queries, manage users
#   analyst — run queries, view results, download
#   viewer  — view results only, no DB connect, no download
#
# To add a new user:
#   python -c "from auth.users import hash_pw; print(hash_pw('mypassword'))"
#   Then paste the hash into USERS below.
# =============================================================

import hashlib


def hash_pw(password: str) -> str:
    """SHA-256 hash of password. Use this to generate new hashes."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_pw(password: str, hashed: str) -> bool:
    return hash_pw(password) == hashed


# =============================================================
# USER STORE
# Add / edit users here.
# Never store plain-text passwords.
#
# Default credentials:
#   admin   / admin@2026
#   analyst / analyst@2026
#   viewer  / viewer@2026
# =============================================================

USERS = {
    "admin": {
        "name":     "Admin User",
        "password": hash_pw("admin@2026"),
        "role":     "admin",
        "email":    "admin@insightgrid.ai",
    },
    "analyst": {
        "name":     "Analyst User",
        "password": hash_pw("analyst@2026"),
        "role":     "analyst",
        "email":    "analyst@insightgrid.ai",
    },
    "viewer": {
        "name":     "Viewer User",
        "password": hash_pw("viewer@2026"),
        "role":     "viewer",
        "email":    "viewer@insightgrid.ai",
    },
}


# Role permissions map
PERMISSIONS = {
    "admin": {
        "can_connect_db":   True,
        "can_run_query":    True,
        "can_download":     True,
        "can_manage_users": True,
    },
    "analyst": {
        "can_connect_db":   True,
        "can_run_query":    True,
        "can_download":     True,
        "can_manage_users": False,
    },
    "viewer": {
        "can_connect_db":   False,
        "can_run_query":    False,
        "can_download":     False,
        "can_manage_users": False,
    },
}


def get_user(username: str) -> dict | None:
    return USERS.get(username.strip().lower())


def get_permissions(role: str) -> dict:
    return PERMISSIONS.get(role, PERMISSIONS["viewer"])
