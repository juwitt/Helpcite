"""Add only the PDFs that appeared in Zotero since the last ingest.

Same pipeline as ingest.py, minus the files whose chunks are already stored.
"""
from config import *
from ingest import ingest

if __name__ == "__main__":
    ingest(ZOTERO_PDF_DIR, BIBTEX_PATH, CHROMA_DIR, only_new=True)
