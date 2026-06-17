import streamlit as st


def render(username: str, secret: dict) -> None:
    st.title("My Profile")
    st.caption("Account information from Contoso Identity Services")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(
            f"""
            <div style="
                width:80px; height:80px; border-radius:50%;
                background: linear-gradient(135deg, #0078d4, #004e8c);
                display:flex; align-items:center; justify-content:center;
                font-size:2rem; color:#fff; font-weight:700;
            ">{username[0].upper()}</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(f"**{username}**")
        st.caption("Customer Account")

    st.divider()

    st.subheader("Account Details")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Username**")
        st.code(username, language=None)
        st.markdown("**User Pool ID**")
        st.code(secret.get("pool_id", "—"), language=None)
    with col_b:
        st.markdown("**Client ID**")
        st.code(secret.get("client_id", "—"), language=None)
        st.markdown("**Cognito Domain**")
        st.code(secret.get("cognito_domain", "—"), language=None)

    st.divider()
    st.subheader("Session")
    session_id = st.session_state.get("session_id", "Not started")
    st.markdown("**Current Session ID**")
    st.code(session_id, language=None)
    if st.button("Start New Session"):
        import uuid
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["messages"] = []
        st.success("New session started.")
        st.rerun()
