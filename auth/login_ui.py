# =============================================================
# auth/login_ui.py
# Renders the login screen and handles authentication.
# Called from streamlit_app.py BEFORE any app content.
# =============================================================

import streamlit as st
from auth.users import get_user, get_permissions, verify_pw


def _login_css():
    st.markdown("""
    <style>
    .login-box {
        max-width: 420px;
        margin: 6vh auto 0 auto;
        background: rgba(0,50,80,0.75);
        border: 1px solid rgba(0,180,216,0.4);
        border-radius: 18px;
        padding: 40px 36px 32px 36px;
        box-shadow: 0 8px 40px rgba(0,180,216,0.15);
    }
    .login-title {
        text-align: center;
        font-size: 1.9rem;
        font-weight: 800;
        color: #48cae4;
        margin-bottom: 4px;
    }
    .login-sub {
        text-align: center;
        font-size: 0.85rem;
        color: #90e0ef;
        margin-bottom: 28px;
    }
    .role-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.05em;
    }
    .role-admin   { background:#0077b6; color:white; }
    .role-analyst { background:#00b4d8; color:white; }
    .role-viewer  { background:#48cae4; color:#0e0e1a; }
    </style>
    """, unsafe_allow_html=True)


def show_login() -> bool:
    """
    Renders login form. Returns True if user is authenticated.
    Manages st.session_state: logged_in, username, user_name,
    user_role, permissions.
    """

    _login_css()

    # ── Centre the login box ──────────────────────────────
    _, mid, _ = st.columns([1, 2, 1])

    with mid:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🤖 Insight Grid AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Where Data, Agents and Decisions Connect</div>',
                    unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Enter username", key="li_user")
        password = st.text_input("Password", placeholder="Enter password",
                                 type="password", key="li_pass")

        if st.button("🔐 Login", type="primary", use_container_width=True):
            user = get_user(username)
            if user and verify_pw(password, user["password"]):
                st.session_state.logged_in   = True
                st.session_state.username    = username.strip().lower()
                st.session_state.user_name   = user["name"]
                st.session_state.user_role   = user["role"]
                st.session_state.permissions = get_permissions(user["role"])
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

        st.markdown("</div>", unsafe_allow_html=True)

        # Demo credentials hint
        with st.expander("👤 Demo credentials"):
            st.markdown("""
| Username | Password | Role |
|---|---|---|
| admin | admin@2026 | Admin |
| analyst | analyst@2026 | Analyst |
| viewer | viewer@2026 | Viewer |
""")

    return False


def check_auth() -> bool:
    """Returns True if user is already logged in."""
    return st.session_state.get("logged_in", False)


def logout():
    """Clear all auth session state."""
    for key in ["logged_in", "username", "user_name", "user_role", "permissions"]:
        st.session_state.pop(key, None)
