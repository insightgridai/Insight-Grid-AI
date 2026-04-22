import streamlit as st
from auth.users import get_user, get_permissions, verify_pw


def check_auth() -> bool:
    return bool(st.session_state.get("logged_in", False))


def logout():
    for key in ["logged_in", "username", "user_name", "user_role", "permissions"]:
        st.session_state.pop(key, None)


def show_login_popup():

    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {display:none!important;}
    header {display:none!important;}
    footer {display:none!important;}
    #MainMenu {display:none!important;}
    .block-container {padding:0!important; max-width:100%!important;}
    .stApp {
        background: radial-gradient(ellipse at 50% 40%,
            rgba(0,119,182,0.25) 0%, #000d1a 65%);
        min-height:100vh;
    }
    div[data-testid="stVerticalBlock"] > div {padding:0!important;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.2, 1])

    with col:

        # Logo + heading
        st.markdown("""
        <div style="text-align:center; margin-bottom:8px;">
            <div style="
                width:78px; height:78px; border-radius:50%;
                background: conic-gradient(#00b4d8,#0077b6,#023e8a,#48cae4,#00b4d8);
                margin:0 auto 14px auto;
                display:flex; align-items:center; justify-content:center;
                font-size:2rem;
                box-shadow:0 0 28px rgba(0,180,216,0.6);">
                🤖
            </div>
            <div style="font-size:1.7rem;font-weight:800;color:#caf0f8;letter-spacing:0.01em;">
                Insight Grid AI
            </div>
            <div style="font-size:0.82rem;color:rgba(144,224,239,0.7);margin-bottom:22px;">
                Where Data, Agents and Decisions Connect
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Card
        st.markdown("""
        <div style="
            background:rgba(0,25,50,0.92);
            border:1.5px solid rgba(0,200,255,0.3);
            border-radius:20px;
            padding:32px 30px 24px 30px;
            box-shadow:0 0 50px rgba(0,180,216,0.15);">
        """, unsafe_allow_html=True)

        st.markdown("""
        <p style="text-align:center;color:#90e0ef;
                  font-size:1rem;font-weight:600;margin-bottom:18px;">
            Sign In
        </p>
        """, unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Enter username",
                                 key="lg_user", label_visibility="collapsed")
        st.markdown("<p style='color:#90e0ef;font-size:0.82rem;"
                    "margin:0 0 4px 2px;'>Username</p>",
                    unsafe_allow_html=True)

        password = st.text_input("Password", placeholder="Enter password",
                                 type="password", key="lg_pass",
                                 label_visibility="collapsed")
        st.markdown("<p style='color:#90e0ef;font-size:0.82rem;"
                    "margin:0 0 16px 2px;'>Password</p>",
                    unsafe_allow_html=True)

        login_btn = st.button("Sign In →", type="secondary",
                              use_container_width=True, key="lg_btn")

        if login_btn:
            u = username.strip()
            p = password.strip()
            if not u or not p:
                st.error("Please enter username and password.")
            else:
                user = get_user(u)
                if user and verify_pw(p, user["password"]):
                    st.session_state.logged_in   = True
                    st.session_state.username    = u.lower()
                    st.session_state.user_name   = user["name"]
                    st.session_state.user_role   = user["role"]
                    st.session_state.permissions = get_permissions(user["role"])
                    st.rerun()
                else:
                    st.error("❌ Wrong username or password.")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        with st.expander("👤 Demo credentials"):
            st.markdown("""
| Username | Password | Role |
|---|---|---|
| `admin` | `admin@2026` | Admin — full access |
| `analyst` | `analyst@2026` | Analyst — query + download |
| `viewer` | `viewer@2026` | Viewer — view only |
""")
