# -----------------------------------------
# Cache background image for speed
# -----------------------------------------

import streamlit as st
import base64

@st.cache_data
def load_bg(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()