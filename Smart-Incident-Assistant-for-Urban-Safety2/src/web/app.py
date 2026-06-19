"""Contoso Smart Incident Assistant — Streamlit Web Application."""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import SERP_API_KEY
from src.telemetry import init_telemetry

init_telemetry()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Contoso Smart Incident Assistant",
    page_icon="\U0001f3d9️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Contoso theme CSS
# ---------------------------------------------------------------------------
CONTOSO_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --contoso-blue: #0078D4;
    --contoso-dark: #1B1B1B;
    --contoso-light: #F3F2F1;
    --contoso-accent: #005A9E;
    --contoso-sidebar: #1E2A3A;
}

.stApp { font-family: 'Inter', 'Segoe UI', sans-serif; }

/* Login page */
.login-container {
    max-width: 420px;
    margin: 80px auto;
    padding: 2.5rem;
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
}
.login-header {
    text-align: center;
    margin-bottom: 2rem;
}
.login-header h1 {
    color: var(--contoso-blue);
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0.5rem 0 0.3rem 0;
}
.login-header p {
    color: #666;
    font-size: 0.85rem;
    margin: 0;
}

/* Sidebar dark theme */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E2A3A 0%, #15202E 100%);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}
section[data-testid="stSidebar"] .stMarkdown p {
    color: rgba(255,255,255,0.7) !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
}

/* Hide ALL default Streamlit page navigation */
section[data-testid="stSidebar"] nav,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"],
section[data-testid="stSidebar"] ul[data-testid="stSidebarNavItems"],
div[data-testid="stSidebarNavItems"],
div[data-testid="stSidebarNav"] {
    display: none !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* Sidebar buttons — dark transparent with visible text */
section[data-testid="stSidebar"] button {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] button span,
section[data-testid="stSidebar"] button div {
    color: rgba(255,255,255,0.85) !important;
}
section[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,0.15) !important;
    border-color: rgba(255,255,255,0.3) !important;
}
section[data-testid="stSidebar"] button:hover p,
section[data-testid="stSidebar"] button:hover span,
section[data-testid="stSidebar"] button:hover div {
    color: white !important;
}
/* Active nav button — blue */
section[data-testid="stSidebar"] button[kind="primary"] {
    background: var(--contoso-blue) !important;
    border-color: var(--contoso-blue) !important;
}
section[data-testid="stSidebar"] button[kind="primary"] p,
section[data-testid="stSidebar"] button[kind="primary"] span,
section[data-testid="stSidebar"] button[kind="primary"] div {
    color: white !important;
}
section[data-testid="stSidebar"] button[kind="primary"]:hover {
    background: var(--contoso-accent) !important;
}

/* Radio buttons (Web Search On/Off) on dark sidebar */
section[data-testid="stSidebar"] .stRadio label p,
section[data-testid="stSidebar"] .stRadio label span {
    color: white !important;
}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    border-radius: 6px !important;
    padding: 0.3rem 0.8rem !important;
}
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label[data-checked="true"] {
    background: var(--contoso-blue) !important;
    border-color: var(--contoso-blue) !important;
}
/* Hide help tooltip icons in sidebar */
section[data-testid="stSidebar"] [data-testid="stTooltipIcon"],
section[data-testid="stSidebar"] .stTooltipIcon {
    display: none !important;
}

/* Header banner */
.contoso-header {
    background: linear-gradient(135deg, #0078D4 0%, #005A9E 100%);
    padding: 1.2rem 2rem;
    border-radius: 0 0 12px 12px;
    margin: -1rem -1rem 1.5rem -1rem;
    color: white;
}
.contoso-header h1 {
    color: white !important;
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
}
.contoso-header p {
    color: rgba(255,255,255,0.85);
    font-size: 0.9rem;
    margin: 0.3rem 0 0 0;
}

/* Source cards */
.source-card {
    background: var(--contoso-light);
    border-left: 4px solid var(--contoso-blue);
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.85rem;
}
.source-card .source-type {
    display: inline-block;
    background: var(--contoso-blue);
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    margin-right: 8px;
}
.source-card .source-name {
    font-weight: 600;
    color: var(--contoso-dark);
}

/* Web search card */
.web-search-card {
    background: #FFF8E1;
    border-left: 4px solid #FFA000;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.85rem;
}

/* Profile avatar */
.profile-avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: var(--contoso-blue);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    font-weight: 700;
    margin: 0 auto 1rem auto;
}

/* Settings card */
.settings-card {
    background: white;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 1.2rem;
    margin: 0.8rem 0;
}
.settings-card h4 {
    color: var(--contoso-dark);
    margin: 0 0 0.8rem 0;
    font-size: 1rem;
}
.settings-field {
    background: #F5F5F5;
    padding: 0.5rem 0.8rem;
    border-radius: 4px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.82rem;
    color: #333;
    margin: 0.3rem 0;
    word-break: break-all;
}
.settings-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #666;
    margin: 0.6rem 0 0.2rem 0;
}

/* Metric card for telemetry */
.metric-card {
    background: white;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}
.metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--contoso-blue);
}
.metric-label {
    font-size: 0.78rem;
    color: #888;
    margin-top: 0.3rem;
}
</style>
"""
st.markdown(CONTOSO_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Auth credentials
# ---------------------------------------------------------------------------
VALID_USERNAME = os.getenv("APP_USERNAME", "testuser")
VALID_PASSWORD = os.getenv("APP_PASSWORD", "MyPassword123!")


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "login_time" not in st.session_state:
    st.session_state.login_time = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Chat"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = None
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = False
if "query_metrics" not in st.session_state:
    st.session_state.query_metrics = {"count": 0, "total_latency": 0.0, "errors": 0}


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------
def show_login():
    st.markdown(
        """
        <div class="login-container">
            <div class="login-header">
                <h1>\U0001f3d9️ Contoso</h1>
                <p>Smart Incident Assistant for Urban Safety</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("#### Sign In")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if username == VALID_USERNAME and password == VALID_PASSWORD:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.login_time = datetime.now()
                    st.rerun()
                else:
                    st.error("Invalid username or password")


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
def show_sidebar():
    with st.sidebar:
        logo_path = Path(__file__).parent / "assets" / "contoso_logo.svg"
        if logo_path.exists():
            st.image(str(logo_path), width=180)

        st.markdown("**Smart Incident Assistant for Urban Safety**")
        st.markdown(
            "This application helps city officials and emergency response teams "
            "analyze urban safety incidents. Ask questions about incidents, SOPs, "
            "and safety images."
        )

        st.divider()

        menu_items = [
            ("\U0001f4ac Chat", "Chat"),
            ("\U0001f464 Profile", "Profile"),
            ("⚙️ Settings", "Settings"),
        ]

        for label, page in menu_items:
            btn_type = "primary" if st.session_state.current_page == page else "secondary"
            if st.button(label, key=f"nav_{page}", use_container_width=True, type=btn_type):
                st.session_state.current_page = page
                st.rerun()

        st.divider()
        st.markdown(f"Signed in as\n\n**{st.session_state.username}**")

        if st.button("\U0001f6aa Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ---------------------------------------------------------------------------
# Page router
# ---------------------------------------------------------------------------
def main():
    if not st.session_state.authenticated:
        show_login()
        return

    show_sidebar()

    if st.session_state.current_page == "Chat":
        from src.web.views.chat import render_chat
        render_chat()
    elif st.session_state.current_page == "Profile":
        from src.web.views.profile import render_profile
        render_profile()
    elif st.session_state.current_page == "Settings":
        from src.web.views.settings import render_settings
        render_settings()


main()
