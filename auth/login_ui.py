# =============================================================
# auth/login_ui.py
# Login as a small popup dialog — appears automatically when
# the app opens and the user is not yet authenticated.
# =============================================================

import streamlit as st
from auth.users import get_user, get_permissions, verify_pw


# =============================================================
# POPUP LOGIN DIALOG
# st.dialog renders a small centered modal window —
# exactly like a mobile/desktop app login popup.
# =============================================================

@st.dialog("🔐 Login to Insight Grid AI")
def _login_dialog():
    """Small popup dialog for username + password entry."""

    st.markdown(
        "<p style='text-align:center; color:#90e0ef; font-size:0.9rem;'>"
        "Enter your credentials to continue</p>",
        unsafe_allow_html=True
    )

    username = st.text_input("Username", placeholder="e.g. admin", key="dlg_user")
    password = st.text_input("Password", placeholder="••••••••",
                             type="password", key="dlg_pass")

    st.markdown("")  # small spacer

    if st.button("🚀 Login", type="primary", use_container_width=True):
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

    st.divider()

    # Hint for demo
    with st.expander("👤 Demo credentials"):
        st.markdown("""
| Username | Password | Role |
|---|---|---|
| `admin` | `admin@2026` | Admin |
| `analyst` | `analyst@2026` | Analyst |
| `viewer` | `viewer@2026` | Viewer |
""")


def show_login_popup():
    """
    Shows the background app shell (blurred) + login dialog popup.
    Called from streamlit_app.py before rendering any real content.
    """
    # Render a minimal locked background so the app
    # is visible but not usable behind the popup
    st.markdown("""
    <style>
    /* Dim everything behind the dialog */
    [data-testid="stAppViewContainer"] > .main {
        filter: blur(2px);
        pointer-events: none;
        user-select: none;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🤖 Insight Grid AI")
    st.caption("Where Data, Agents and Decisions Connect")
    st.info("🔐 Please log in to continue.")

    # Open the popup dialog immediately
    _login_dialog()


def check_auth() -> bool:
    """Returns True if user is already authenticated."""
    return st.session_state.get("logged_in", False)


def logout():
    """Clear all auth-related session state."""
    for key in ["logged_in", "username", "user_name", "user_role", "permissions"]:
        st.session_state.pop(key, None)
