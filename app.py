import os

import streamlit as st

from config import EMBED_MODEL, GROQ_MODEL, TOP_K
from generator import generate_answer
from retriever import dedupe, index_stats, retrieve

st.set_page_config(page_title="Literature RAG Chatbot", layout="wide")
st.title("Literature RAG Chatbot")
st.caption("Semantic search over your Zotero library")


def passage_label(i, meta):
    """Readable label for one retrieved passage."""
    title = meta.get("apa") or meta.get("source") or "unknown source"
    page = meta.get("page")
    tail = f" (p. {page})" if page else ""
    return f"[{i}] {title}{tail}"


with st.sidebar:
    st.markdown("### Index")
    chunk_count = index_stats()
    if chunk_count:
        st.success(f"{chunk_count:,} chunks ready")
    else:
        st.warning("No index yet. Run `python ingest.py` first.")
    top_k = st.slider("Passages retrieved", 3, 30, TOP_K)
    st.caption(f"Embeddings: {EMBED_MODEL}")
    st.caption(f"Answer model: {GROQ_MODEL}")

query = st.text_area("Your query or statement to verify:", height=100)

if st.button("Search") and query:
    if not os.getenv("GROQ_API_KEY"):
        st.error("No GROQ_API_KEY found. Put it into your .env file, then restart the app.")
    elif chunk_count is None:
        st.error("No literature index found. Run `python ingest.py` first.")
    else:
        try:
            with st.spinner("Searching literature..."):
                chunks = dedupe(retrieve(query, top_k=top_k))
                answer = generate_answer(query, chunks)
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
        else:
            passages = list(zip(chunks["documents"][0], chunks["metadatas"][0]))
            if not passages:
                st.warning("Nothing found in your library for that query.")
            else:
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.markdown("### Answer")
                    st.markdown(answer)
                with col2:
                    st.markdown("### Retrieved passages")
                    for i, (doc, meta) in enumerate(passages, start=1):
                        with st.expander(passage_label(i, meta)):
                            st.caption(meta.get("path", ""))
                            st.write(doc)
