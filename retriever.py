import os

import chromadb
from sentence_transformers import SentenceTransformer

from config import *

_model = None


def get_model():
    """Load the embedding model once and reuse it for later queries."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def open_collection():
    """Open the index created by ingest.py."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection("literature")


def index_stats():
    """Number of stored chunks, or None when the index does not exist yet."""
    if not os.path.isdir(CHROMA_DIR):
        return None
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    if "literature" not in [c.name for c in client.list_collections()]:
        return None
    return client.get_collection("literature").count()


def retrieve(query: str, top_k: int = TOP_K):
    """Embed query and retrieve top-K most similar chunks from ChromaDB."""
    model = get_model()
    collection = open_collection()

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count() or top_k),
        include=["documents", "metadatas", "distances"]
    )
    return results


def dedupe(results):
    """Drop repeated passages: same source, same page, neighbouring chunk."""
    seen = set()
    kept_docs, kept_metas, kept_dists = [], [], []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        key = (meta.get("source"), meta.get("page"), doc[:80])
        if key in seen:
            continue
        seen.add(key)
        kept_docs.append(doc)
        kept_metas.append(meta)
        kept_dists.append(dist)
    results["documents"][0] = kept_docs
    results["metadatas"][0] = kept_metas
    results["distances"][0] = kept_dists
    return results
