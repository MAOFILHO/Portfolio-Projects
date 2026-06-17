import json
import os
import sys

import streamlit as st
from streamlit_cognito_auth import CognitoAuthenticator
from streamlit_option_menu import option_menu

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

from utils import get_customer_support_secret

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Contoso Support",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Contoso brand styles ──────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Contoso blue palette */
    :root {
        --contoso-blue: #0078d4;
        --contoso-dark: #004e8c;
        --contoso-light: #deecf9;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #004e8c 0%, #0078d4 100%);
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    /* Force option_menu container to be transparent so sidebar gradient shows */
    [data-testid="stSidebar"] .nav { background-color: transparent !important; }
    [data-testid="stSidebar"] .nav-pills { background-color: transparent !important; }
    [data-testid="stSidebar"] .nav-link { color: #ffffff !important; }
    [data-testid="stSidebar"] .nav-link:hover { background-color: rgba(255,255,255,0.2) !important; }
    [data-testid="stSidebar"] .nav-link.active { background-color: rgba(255,255,255,0.3) !important; color: #ffffff !important; }
    [data-testid="stSidebar"] .nav-link i { color: #ffffff !important; }
    [data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.15);
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.4);
        border-radius: 6px;
        width: 100%;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.25);
    }
    .contoso-logo {
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #ffffff;
        padding: 0.5rem 0 0.2rem 0;
    }
    .contoso-tagline {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.75);
        margin-bottom: 1.5rem;
    }
    .user-bubble {
        background: var(--contoso-light);
        border-left: 3px solid var(--contoso-blue);
        padding: 0.6rem 0.9rem;
        border-radius: 0 8px 8px 8px;
        margin: 0.25rem 0;
    }
    .assistant-bubble {
        background: #f8f9fa;
        border-left: 3px solid #6c757d;
        padding: 0.6rem 0.9rem;
        border-radius: 0 8px 8px 8px;
        margin: 0.25rem 0;
    }
    .thinking-bubble { color: #6c757d; font-style: italic; }
    .streaming { border-left-color: var(--contoso-blue) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Auth ──────────────────────────────────────────────────────────────────────
secret = json.loads(get_customer_support_secret())
authenticator = CognitoAuthenticator(
    pool_id=secret["pool_id"],
    app_client_id=secret["client_id"],
    app_client_secret=secret["client_secret"],
    use_cookies=False,
)

is_logged_in = authenticator.login()
if not is_logged_in:
    st.stop()

username = authenticator.get_username()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="contoso-logo">🔷 Contoso</div>', unsafe_allow_html=True)
    st.markdown('<div class="contoso-tagline">Customer Support Portal</div>', unsafe_allow_html=True)

    nav = option_menu(
        menu_title=None,
        options=["Chat", "Profile", "Settings"],
        icons=["chat-dots-fill", "person-circle", "gear-fill"],
        default_index=0,
        styles={
            "container": {"padding": "4px", "background-color": "#004e8c"},
            "icon": {"color": "#ffffff", "font-size": "14px"},
            "nav-link": {
                "color": "#ffffff",
                "font-size": "14px",
                "padding": "8px 12px",
                "border-radius": "6px",
                "--hover-color": "rgba(255,255,255,0.2)",
            },
            "nav-link-selected": {
                "background-color": "rgba(255,255,255,0.25)",
                "color": "#ffffff",
                "font-weight": "600",
            },
        },
    )

    st.markdown("---")
    st.markdown(f"<small>Signed in as<br><b>{username}</b></small>", unsafe_allow_html=True)
    st.button("Logout", key="logout_btn", on_click=authenticator.logout)

# ── Page routing ──────────────────────────────────────────────────────────────
if nav == "Chat":
    from chat import ChatManager
    from chat_utils import make_urls_clickable, create_safe_markdown_text

    st.title("Customer Support")
    st.caption("Powered by AWS Bedrock AgentCore · Amazon Nova 2 Lite")

    chat_manager = ChatManager("default")

    bearer_token = st.session_state.get("auth_access_token", "")
    actor_id = st.session_state.get("auth_username", username)

    chat_manager.initialize_default_conversation(username, actor_id, bearer_token)
    chat_manager.display_chat_history()

    if prompt := st.chat_input("How can we help you today?"):
        chat_manager.process_user_message(prompt, actor_id, bearer_token)
        st.rerun()

elif nav == "Profile":
    import profile as profile_page
    profile_page.render(username, secret)

elif nav == "Settings":
    import settings as settings_page
    settings_page.render()
