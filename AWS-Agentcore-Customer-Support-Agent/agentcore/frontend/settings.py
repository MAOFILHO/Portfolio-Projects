import os
import sys

import streamlit as st

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "..")))

from utils import get_ssm_parameter

SSM_KEYS = {
    "Runtime ARN": "/app/customersupport/agentcore/runtime_arn",
    "Memory ID": "/app/customersupport/agentcore/memory_id",
    "Gateway ID": "/app/customersupport/agentcore/gateway_id",
    "Gateway URL": "/app/customersupport/agentcore/gateway_url",
    "Cognito Domain": "/app/customersupport/agentcore/cognito_domain",
}


def render() -> None:
    st.title("Settings")
    st.caption("Read-only configuration — managed via AWS SSM Parameter Store")

    st.subheader("Model Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Foundation Model**")
        st.code("us.amazon.nova-2-lite-v1:0", language=None)
    with col2:
        st.markdown("**AWS Region**")
        region = st.session_state.get("region", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        st.code(region, language=None)

    st.divider()
    st.subheader("Infrastructure Parameters")
    st.caption("Retrieved live from AWS SSM Parameter Store")

    for label, param_path in SSM_KEYS.items():
        col_label, col_value = st.columns([1, 3])
        with col_label:
            st.markdown(f"**{label}**")
        with col_value:
            try:
                value = get_ssm_parameter(param_path)
                st.code(value, language=None)
            except Exception:
                st.caption("_Not configured — run the pipeline first_")

    st.divider()
    st.subheader("About")
    cols = st.columns(3)
    with cols[0]:
        st.metric("Pipeline Steps", "7")
    with cols[1]:
        st.metric("AWS Services", "12+")
    with cols[2]:
        st.metric("Auth", "JWT / Cognito")

    st.caption(
        "AWS Bedrock AgentCore Customer Support · "
        "[GitHub](https://github.com/djmau1974/aws-bedrock-agentcore-customer-support)"
    )
