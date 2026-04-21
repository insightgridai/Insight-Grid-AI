# =============================================================
# auth/login_ui.py
# Full-page blocking login screen — neon blue theme
# Styled like a professional Sign In card (ref Image 2)
# Shows BEFORE any app content. App is completely hidden.
# =============================================================

import streamlit as st
from auth.users import get_user, get_permissions, verify_pw


def show_login_popup():
    """
    Renders a full-screen login page that completely blocks the app.
    The main app content never renders until login succeeds.
    """

    # Hide ALL default Streamlit chrome so nothing leaks through
    st.markdown("""
    <style>
    /* Hide sidebar, header, footer completely */
    section[data-testid="stSidebar"]   { display: none !important; }
    header[data-testid="stHeader"]     { display: none !important; }
    footer                             { display: none !important; }
    #MainMenu                          { display: none !important; }
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }

    /* Full-screen dark background */
    .stApp {
        background: radial-gradient(ellipse at 60% 40%,
            rgba(0,119,182,0.18) 0%,
            rgba(0,0,0,0.97) 70%);
        min-height: 100vh;
    }

    /* Login card */
    .login-outer {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 20px;
    }
    .login-card {
        background: rgba(0, 30, 55, 0.92);
        border: 1.5px solid rgba(0, 200, 255, 0.35);
        border-radius: 22px;
        padding: 44px 40px 36px 40px;
        width: 100%;
        max-width: 400px;
        box-shadow:
            0 0 40px rgba(0, 180, 216, 0.18),
            0 0 80px rgba(0, 119, 182, 0.10);
    }

    /* Logo circle */
    .login-logo {
        width: 80px; height: 80px;
        border-radius: 50%;
        background: conic-gradient(
            #00b4d8 0deg, #0077b6 90deg,
            #023e8a 180deg, #48cae4 270deg, #00b4d8 360deg
        );
        margin: 0 auto 18px auto;
        display: flex; align-items: center; justify-content: center;
        font-size: 2rem;
        box-shadow: 0 0 24px rgba(0,180,216,0.5);
    }

    /* Title */
    .login-title {
        text-align: center;
        font-size: 1.5rem;
        font-weight: 800;
        color: #caf0f8;
        margin-bottom: 4px;
        letter-spacing: 0.02em;
    }
    .login-subtitle {
        text-align: center;
        font-size: 0.82rem;
        color: rgba(144,224,239,0.7);
        margin-bottom: 28px;
    }

    /* Override input styling inside card */
    .login-card input {
        background: rgba(0,50,80,0.6) !important;
        border: 1px solid rgba(0,180,216,0.3) !important;
        border-radius: 8px !important;
        color: white !important;
        font-size: 0.95rem !important;
    }
    .login-card input:focus {
        border-color: rgba(0,180,216,0.8) !important;
        box-shadow: 0 0 8px rgba(0,180,216,0.3) !important;
    }

    /* Label styling */
    .login-card label {
        color: #90e0ef !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
    }

    /* Login button */
    .login-card div[data-testid="stButton"] button {
        background: linear-gradient(135deg, #00b4d8, #0077b6) !important;
        border: none !important;
        color: white !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        border-radius: 10px !important;
        height: 46px !important;
        letter-spacing: 0.04em !important;
        box-shadow: 0 4px 20px rgba(0,180,216,0.35) !important;
        transition: all 0.2s !important;
    }
    .login-card div[data-testid="stButton"] button:hover {
        background: linear-gradient(135deg, #48cae4, #0096c7) !important;
        box-shadow: 0 6px 28px rgba(0,180,216,0.5) !important;
    }

    /* Error message */
    .login-card div[data-testid="stAlert"] {
        border-radius: 8px !important;
    }

    /* Demo table */
    .login-card table {
        width: 100%;
        font-size: 0.8rem;
        color: #90e0ef;
        border-collapse: collapse;
    }
    .login-card table td, .login-card table th {
        padding: 4px 8px;
        border: 1px solid rgba(0,180,216,0.2);
    }
    .login-card table th { color: #48cae4; }
    </style>
    """, unsafe_allow_html=True)

    # ── Render card via columns trick ──────────────────────
    # Use st.columns to center the card on screen
    left, mid, right = st.columns([1, 1.4, 1])

    with mid:
        # Logo + title (HTML)
        st.markdown("""
        <div style="margin-top:8vh;">
            <div class="login-logo">🤖</div>
            <div class="login-title">Insight Grid AI</div>
            <div class="login-subtitle">Where Data, Agents and Decisions Connect</div>
        </div>
        """, unsafe_allow_html=True)

        # Card wrapper open
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        # Input fields
        username = st.text_input(
            "Username",
            placeholder="Enter your username",
            key="login_username"
        )
        password = st.text_input(
            "Password",
            placeholder="Enter your password",
            type="password",
            key="login_password"
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("Sign In →", type="primary", use_container_width=True):
            if not username.strip() or not password.strip():
                st.error("Please enter both username and password.")
            else:
                user = get_user(username)
                if user and verify_pw(password, user["password"]):
                    # ✅ Success — set session state
                    st.session_state.logged_in   = True
                    st.session_state.username    = username.strip().lower()
                    st.session_state.user_name   = user["name"]
                    st.session_state.user_role   = user["role"]
                    st.session_state.permissions = get_permissions(user["role"])
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")

        # Demo credentials hint
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        with st.expander("👤 Demo credentials"):
            st.markdown("""
| Username | Password | Role |
|---|---|---|
| `admin` | `admin@2026` | Admin |
| `analyst` | `analyst@2026` | Analyst |
| `viewer` | `viewer@2026` | Viewer |
""")

        # Card wrapper close
        st.markdown('</div>', unsafe_allow_html=True)


def check_auth() -> bool:
    """Returns True if user is already authenticated."""
    return st.session_state.get("logged_in", False)


def logout():
    """Clear all auth-related session state keys."""
    for key in ["logged_in", "username", "user_name", "user_role", "permissions"]:
        st.session_state.pop(key, None)
