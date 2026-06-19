"""Profile page — User account details and session info."""

from datetime import datetime

import streamlit as st


def render_profile():
    st.markdown(
        """
        <div class="contoso-header">
            <h1>\U0001f464 My Profile</h1>
            <p>Account information from Contoso Identity Services</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    username = st.session_state.get("username", "unknown")
    first_letter = username[0].upper() if username else "U"

    # Avatar and name
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(
            f'<div class="profile-avatar">{first_letter}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(f"### {username}")
        st.markdown("Municipal Safety Analyst")

    st.divider()

    # Account details
    st.markdown("## Account Details")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Username</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{username}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Role</p>', unsafe_allow_html=True)
        st.markdown('<div class="settings-field">Municipal Safety Analyst</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Department</p>', unsafe_allow_html=True)
        st.markdown('<div class="settings-field">Urban Safety &amp; Emergency Response</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Organization</p>', unsafe_allow_html=True)
        st.markdown('<div class="settings-field">Contoso Municipal Services</div>', unsafe_allow_html=True)

    st.divider()

    # Session info
    st.markdown("## Session")

    login_time = st.session_state.get("login_time")
    session_id = st.session_state.get("session_id", "—")
    login_str = login_time.strftime("%Y-%m-%d %H:%M:%S") if login_time else "—"
    duration = ""
    if login_time:
        delta = datetime.now() - login_time
        minutes = int(delta.total_seconds() // 60)
        duration = f"{minutes} min" if minutes > 0 else "< 1 min"

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Session ID</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{session_id}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Login Time</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{login_str}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Session Duration</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{duration}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Chat Messages</p>', unsafe_allow_html=True)
        msg_count = len(st.session_state.get("messages", []))
        st.markdown(f'<div class="settings-field">{msg_count}</div>', unsafe_allow_html=True)
