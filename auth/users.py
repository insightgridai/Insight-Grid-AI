import hashlib


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_pw(password: str, hashed: str) -> bool:
    return hash_pw(password) == hashed


# =============================================================
# USER STORE
#
# HOW TO CHANGE USERNAME:
#   - The KEY (left side) is what user types in the login box
#   - The "name" is just the display name shown in sidebar
#   - Change the KEY to change the login username
#
# HOW TO CHANGE PASSWORD:
#   - Change the text inside hash_pw("...")
#   - That text is the new password
#
# CURRENT CREDENTIALS:
#   Username : ROOMEG        Password : INSIGHT@2026   Role: Admin
#   Username : analyst       Password : analyst@2026   Role: Analyst
#   Username : viewer        Password : viewer@2026    Role: Viewer
# =============================================================

USERS = {

    # ── Admin ─────────────────────────────────────────────
    # LOGIN: username = ROOMEG  |  password = INSIGHT@2026
    "roomeg": {
        "name":     "ROOMEG",
        "password": hash_pw("INSIGHT@2026"),
        "role":     "admin",
        "email":    "admin@insightgrid.ai",
    },

    # ── Analyst ───────────────────────────────────────────
    # LOGIN: username = analyst  |  password = analyst@2026
    "analyst": {
        "name":     "Analyst User",
        "password": hash_pw("analyst@2026"),
        "role":     "analyst",
        "email":    "analyst@insightgrid.ai",
    },

    # ── Viewer ────────────────────────────────────────────
    # LOGIN: username = viewer  |  password = viewer@2026
    "viewer": {
        "name":     "Viewer User",
        "password": hash_pw("viewer@2026"),
        "role":     "viewer",
        "email":    "viewer@insightgrid.ai",
    },
}


# =============================================================
# PERMISSIONS PER ROLE
# =============================================================
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


def get_user(username: str):
    # Always lowercase the lookup so ROOMEG / roomeg / Roomeg all work
    return USERS.get(username.strip().lower())


def get_permissions(role: str) -> dict:
    return PERMISSIONS.get(role, PERMISSIONS["viewer"])
