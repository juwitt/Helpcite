import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Points at the files/folders this app uses. Every value can be overridden
# via .env — see .env.example.

# Folder that holds your Zotero PDFs: Zotero/storage (NOT the "files" folder).
# Set it in .env as ZOTERO_PDF_DIR, e.g. C:/Users/you/Zotero/storage
ZOTERO_PDF_DIR = os.getenv("ZOTERO_PDF_DIR", "")

# BibTeX export of your Zotero library. Used for reference; PDF ingest alone
# works without it.
BIBTEX_PATH = os.getenv("BIBTEX_PATH", str(BASE_DIR / "library.bib"))

# Where ChromaDB stores the vector index. Created automatically on ingest.
CHROMA_DIR = os.getenv("CHROMA_DIR", str(BASE_DIR / "chroma_db"))

EMBED_MODEL = "all-MiniLM-L6-v2"  # local, fast, good enough
GROQ_MODEL = "openai/gpt-oss-120b"
CHUNK_SIZE = 1000       # characters
CHUNK_OVERLAP = 150
TOP_K = 10              # number of chunks to retrieve
