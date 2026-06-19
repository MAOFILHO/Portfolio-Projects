"""Chat page — Multimodal RAG chat interface."""

import os
import time
from pathlib import Path

import streamlit as st

from src.config import IMAGES_DIR, PDFS_DIR, SERP_API_KEY, SOPS_DIR


def render_chat():
    st.markdown(
        """
        <div class="contoso-header">
            <h1>\U0001f3d9️ Contoso Smart Incident Assistant</h1>
            <p>AI-Powered Urban Safety Intelligence | Multimodal RAG on Azure</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Initialize RAG engine lazily
    if st.session_state.rag_engine is None:
        try:
            from src.rag.engine import RAGEngine
            st.session_state.rag_engine = RAGEngine()
        except SystemExit:
            st.session_state.rag_engine = None

    # --- Chat sidebar controls ---
    with st.sidebar:
        st.divider()

        st.markdown("### Data Overview")
        col1, col2, col3 = st.columns(3)
        pdf_count = len([f for f in os.listdir(PDFS_DIR) if f.endswith(".pdf")]) if PDFS_DIR.exists() else 0
        img_count = len([f for f in os.listdir(IMAGES_DIR) if os.path.splitext(f)[1].lower() in {".jpg", ".jpeg", ".png"}]) if IMAGES_DIR.exists() else 0
        sop_count = len([f for f in os.listdir(SOPS_DIR) if f.endswith(".txt")]) if SOPS_DIR.exists() else 0
        col1.metric("PDFs", pdf_count)
        col2.metric("Images", img_count)
        col3.metric("SOPs", sop_count)

        st.divider()

        if SERP_API_KEY:
            web_search_option = st.radio(
                "\U0001f310 Web Search",
                options=["Off", "On"],
                index=1 if st.session_state.web_search_enabled else 0,
                horizontal=True,
                label_visibility="visible",
            )
            st.session_state.web_search_enabled = web_search_option == "On"
        else:
            st.caption("\U0001f310 Web Search unavailable (set SERP_API_KEY)")

        st.divider()

        st.markdown("### Sample Queries")
        sample_queries = [
            "What fire incidents were reported in Zone A?",
            "What incidents occurred in Zone B?",
            "Which SOP is used for fire response?",
            "List pothole incidents and their actions taken",
            "Show me all flooding incidents with photos",
            "What actions were taken for severe incidents in Zone C?",
            "What is the protocol for electrical hazards?",
            "Give me reports involving both fire and flooding",
        ]
        for q in sample_queries:
            if st.button(q, key=f"sample_{q}", use_container_width=True):
                st.session_state.pending_query = q

        st.divider()

        if st.button("\U0001f5d1️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            if st.session_state.rag_engine:
                st.session_state.rag_engine.clear_history()
            st.rerun()

    # --- Check engine ---
    if st.session_state.rag_engine is None:
        st.error(
            "RAG engine not initialized. Ensure `.env` is configured.\n\n"
            "Run: `python -m src.provision`"
        )
        st.stop()

    # --- Display chat history ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            _render_sources(msg)
            _render_web_results(msg)

    # --- Handle input ---
    pending = st.session_state.pop("pending_query", None)
    user_input = st.chat_input("Ask about urban safety incidents...")
    query = pending or user_input

    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            start_time = time.time()
            with st.spinner("Searching incidents and generating response..."):
                result = st.session_state.rag_engine.query(query)
            elapsed = time.time() - start_time

            # Update metrics
            st.session_state.query_metrics["count"] += 1
            st.session_state.query_metrics["total_latency"] += elapsed

            st.markdown(result["answer"])

            sources = result["sources"]
            web_results_html = ""

            if sources:
                with st.expander(f"\U0001f4ce View Sources ({len(sources)} documents)"):
                    for src in sources:
                        _render_source_card(src)

            if st.session_state.web_search_enabled and SERP_API_KEY:
                with st.spinner("Searching the web..."):
                    try:
                        from src.search.web_search import search_web
                        web_result = search_web(query)
                        if web_result:
                            web_results_html = web_result.get("analysis", "")
                            links = web_result.get("links", [])
                            with st.expander("\U0001f310 Web Search Results"):
                                st.markdown(web_results_html)
                                if links:
                                    st.markdown("**References:**")
                                    for link in links:
                                        st.markdown(f"- {link}")
                    except Exception as e:
                        st.caption(f"Web search failed: {e}")
                        st.session_state.query_metrics["errors"] += 1

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": sources,
            "web_results": web_results_html,
        })


def _render_sources(msg):
    if msg["role"] == "assistant" and msg.get("sources"):
        with st.expander(f"\U0001f4ce View Sources ({len(msg['sources'])} documents)"):
            for src in msg["sources"]:
                _render_source_card(src)


def _render_web_results(msg):
    if msg["role"] == "assistant" and msg.get("web_results"):
        with st.expander("\U0001f310 Web Search Results"):
            st.markdown(
                f'<div class="web-search-card">{msg["web_results"]}</div>',
                unsafe_allow_html=True,
            )


def _render_source_card(src):
    src_type = src.get("type", "unknown")
    src_name = src.get("source", "unknown")
    src_content = src.get("content", "")[:250]

    st.markdown(
        f'<div class="source-card">'
        f'<span class="source-type">{src_type}</span>'
        f'<span class="source-name">{src_name}</span>'
        f"<br/>{src_content}...</div>",
        unsafe_allow_html=True,
    )

    if src_type == "image":
        img_path = IMAGES_DIR / src_name
        if img_path.exists():
            st.image(str(img_path), caption=src_name, width=300)
