"""Settings page — Model config, Azure resources, pipeline status, telemetry."""

import json
import os
from pathlib import Path

import streamlit as st

from src.config import (
    AZURE_EMBEDDING_DEPLOYMENT,
    AZURE_GPT_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    DATA_DIR,
    DOC_INTELLIGENCE_ENDPOINT,
    OPENAI_API_VERSION,
    SEARCH_API_VERSION,
    SERP_API_KEY,
)


def render_settings():
    st.markdown(
        """
        <div class="contoso-header">
            <h1>⚙️ Settings</h1>
            <p>Read-only configuration — managed via .env and Azure provisioning</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Model Configuration ---
    st.markdown("## Model Configuration")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Foundation Model</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{AZURE_GPT_DEPLOYMENT}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Embedding Model</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{AZURE_EMBEDDING_DEPLOYMENT}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">OpenAI API Version</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{OPENAI_API_VERSION}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Search API Version</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{SEARCH_API_VERSION}</div>', unsafe_allow_html=True)

    st.divider()

    # --- Azure Resources ---
    st.markdown("## Azure Resources")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Azure OpenAI Endpoint</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{_mask(AZURE_OPENAI_ENDPOINT)}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Document Intelligence Endpoint</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{_mask(DOC_INTELLIGENCE_ENDPOINT)}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="settings-label">Azure AI Search Endpoint</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{_mask(AZURE_SEARCH_ENDPOINT)}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="settings-label">Search Index Name</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">{AZURE_SEARCH_INDEX}</div>', unsafe_allow_html=True)

    st.divider()

    # --- Pipeline Status ---
    st.markdown("## Pipeline Status")

    parsed_files = {
        "Incidents": ("parsed_incidents.json", "incident"),
        "Images": ("parsed_images.json", "image"),
        "SOPs": ("parsed_sops.json", "sop"),
    }

    cols = st.columns(3)
    for i, (label, (filename, dtype)) in enumerate(parsed_files.items()):
        path = DATA_DIR / filename
        count = 0
        status = "Not generated"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                count = len(data)
                status = f"{count} documents"
            except (json.JSONDecodeError, OSError):
                status = "Error reading file"

        with cols[i]:
            st.metric(label, count)
            st.caption(status)

    st.divider()

    # --- Integrations ---
    st.markdown("## Integrations")

    col1, col2 = st.columns(2)
    with col1:
        serp_status = "Connected" if SERP_API_KEY else "Not configured"
        serp_color = "green" if SERP_API_KEY else "gray"
        st.markdown(f'<p class="settings-label">SerpAPI (Web Search)</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">:{serp_color}[{serp_status}]</div>', unsafe_allow_html=True)
    with col2:
        appinsights_conn = os.getenv("APPINSIGHTS_CONNECTION_STRING", "")
        ai_status = "Connected" if appinsights_conn else "Not configured"
        ai_color = "green" if appinsights_conn else "gray"
        st.markdown(f'<p class="settings-label">Application Insights (Telemetry)</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="settings-field">:{ai_color}[{ai_status}]</div>', unsafe_allow_html=True)

    st.divider()

    # --- Session Telemetry ---
    st.markdown("## Session Telemetry")

    metrics = st.session_state.get("query_metrics", {"count": 0, "total_latency": 0.0, "errors": 0})
    avg_latency = (metrics["total_latency"] / metrics["count"]) if metrics["count"] > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{metrics["count"]}</div>'
            f'<div class="metric-label">Queries This Session</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{avg_latency:.1f}s</div>'
            f'<div class="metric-label">Avg Response Time</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{metrics["errors"]}</div>'
            f'<div class="metric-label">Errors</div></div>',
            unsafe_allow_html=True,
        )

    # Deep link to Azure Portal
    if appinsights_conn:
        st.markdown("")
        st.info(
            "For detailed traces, metrics, and the Agents view, visit "
            "[Azure Portal > Application Insights](https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/microsoft.insights%2Fcomponents)"
        )


def _mask(endpoint: str) -> str:
    if not endpoint:
        return "—"
    return endpoint
