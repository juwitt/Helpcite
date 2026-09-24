import hashlib
import os
import re

import bibtexparser
import chromadb
import fitz  # pymupdf
from sentence_transformers import SentenceTransformer

from config import *

# Zotero writes TeX escapes such as "\&" into exported BibTeX files.
LATEX_ESCAPES = {
    r"\&": "&", r"\%": "%", r"\$": "$", r"\#": "#", r"\_": "_",
    r"\{": "{", r"\}": "}", r"--": "-", r"~": " ",
}


def require_pdf_dir():
    """Fail early with a readable message if ZOTERO_PDF_DIR is missing/wrong."""
    if not ZOTERO_PDF_DIR:
        raise SystemExit(
            "ZOTERO_PDF_DIR is not set. Put the path to your Zotero storage "
            "folder into .env (ZOTERO_PDF_DIR=...) or into config.py."
        )
    if not os.path.isdir(ZOTERO_PDF_DIR):
        raise SystemExit(f"ZOTERO_PDF_DIR does not exist: {ZOTERO_PDF_DIR}")
    return ZOTERO_PDF_DIR


def load_bibtex(path):
    """Load BibTeX file and return dict keyed by citekey.

    Works with bibtexparser 1.x (load) and 2.x (parse_string). A missing or
    empty file simply yields {} — the ingest does not depend on it.
    """
    if not os.path.isfile(path):
        print(f"No BibTeX file at {path} — continuing without it.")
        return {}
    with open(path, encoding="utf-8") as f:
        if hasattr(bibtexparser, "load"):
            db = bibtexparser.load(f)
            return {e["ID"]: e for e in db.entries}
        library = bibtexparser.parse_string(f.read())
        return {e.key: {k: str(v) for k, v in e.items()} for e in library.entries}


def field(entry, name):
    """Read one BibTeX field as a plain string, or '' if absent."""
    if not entry:
        return ""
    try:
        value = entry.get(name, "")
    except AttributeError:
        return ""
    return str(value).strip() if value else ""


def clean_latex(text):
    """Undo the escaping Zotero applies to exported BibTeX fields."""
    for escaped, plain in LATEX_ESCAPES.items():
        text = text.replace(escaped, plain)
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def format_authors(spec, max_names=4):
    """'Alwin, Duane F. and Krosnick, Jon A.' -> 'Alwin, D. F., & Krosnick, J. A.'"""
    names = [n.strip() for n in re.split(r"\s+and\s+", clean_latex(spec)) if n.strip()]
    formatted = []
    for name in names:
        if "," in name:
            family, _, given = name.partition(",")
        else:
            parts = name.rsplit(" ", 1)
            family, given = (parts[-1], parts[0]) if len(parts) > 1 else (name, "")
        initials = " ".join(f"{p[0].upper()}." for p in given.split() if p[:1].isalpha())
        formatted.append(f"{family.strip()}, {initials}".strip().rstrip(","))
    if len(formatted) > max_names:
        formatted = formatted[:max_names] + ["…"]
    if not formatted:
        return ""
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


def format_apa(entry):
    """Best-effort APA reference string from a BibTeX entry."""
    if not entry:
        return ""
    authors = format_authors(field(entry, "author"))
    year = clean_latex(field(entry, "year"))
    title = clean_latex(field(entry, "title")).strip(".")
    container = clean_latex(
        field(entry, "journal") or field(entry, "booktitle") or field(entry, "publisher")
    )
    volume = clean_latex(field(entry, "volume"))
    number = clean_latex(field(entry, "number"))
    pages = clean_latex(field(entry, "pages")).replace("--", "-")

    parts = []
    if authors:
        parts.append(f"{authors} ({year})." if year else f"{authors}.")
    if title:
        parts.append(f"{title}." + (f" ({year})." if not authors and year else ""))
    if container:
        vol = volume + (f"({number})" if number else "")
        parts.append(f"{container}{', ' + vol if vol else ''}.")
    if pages:
        parts.append(f"{pages}.")
    doi = clean_latex(field(entry, "doi"))
    if doi:
        parts.append(f"https://doi.org/{doi}")
    return " ".join(p for p in parts if p)


def build_file_map(bib):
    """Map PDF filename (lowercased) -> BibTeX entry via Zotero's `file` field."""
    mapping = {}
    for citekey, entry in bib.items():
        for segment in field(entry, "file").split(";"):
            name = segment.strip().split("/")[-1].strip()
            if name.lower().endswith(".pdf"):
                mapping[name.lower()] = entry
    return mapping


def extract_chunks(pdf_path, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Extract text from PDF and split into overlapping chunks.

    Returns [(text, page_number)] so every chunk knows where it came from.
    """
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()

    # Join with a separator: without it the last word of a page can glue onto
    # the first word of the next one.
    full_text = "\n".join(pages)

    # char offsets per page, used to stamp each chunk with its page number
    bounds = []
    pos = 0
    for number, text in enumerate(pages, start=1):
        bounds.append((pos, pos + len(text), number))
        pos += len(text) + 1

    chunks = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(full_text):
        piece = re.sub(r"[ \t]{2,}", " ", full_text[start:start + chunk_size]).strip()
        if piece:
            page = next((n for s, e, n in bounds if start < e), 1)
            chunks.append((piece, page))
        start += step
    return chunks


def find_pdfs(pdf_dir):
    """All PDFs under pdf_dir, sorted so runs are reproducible."""
    pdfs = []
    for root, _, files in os.walk(pdf_dir):
        for fname in files:
            if fname.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fname))
    return sorted(pdfs)


def already_ingested(collection):
    """Set of doc_id/source values already stored in the collection."""
    seen = set()
    offset = 0
    batch_size = 5000
    while True:
        batch = collection.get(include=["metadatas"], limit=batch_size, offset=offset)
        if not batch["metadatas"]:
            break
        for meta in batch["metadatas"]:
            seen.add(meta.get("doc_id") or meta.get("source"))
        offset += batch_size
    return seen


def ingest(pdf_dir, bibtex_path, chroma_dir, only_new=False):
    """Main ingestion pipeline: PDF -> chunks -> embeddings -> ChromaDB.

    only_new=True skips PDFs whose chunks are already stored (that is what
    ingest_new.py uses); only_new=False re-embeds everything, which keeps
    `python ingest.py` a safe way to rebuild after changing config.py.
    """
    pdf_dir = require_pdf_dir()
    bib = load_bibtex(bibtex_path)
    file_map = build_file_map(bib)
    print(f"Loaded {len(bib)} BibTeX entries ({len(file_map)} with file links)")

    pdfs = find_pdfs(pdf_dir)
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}. Check your ZOTERO_PDF_DIR.")
        return

    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection("literature")
    done = already_ingested(collection) if only_new else set()

    ingested = skipped_known = skipped_empty = matched = 0
    for n, pdf_path in enumerate(pdfs, start=1):
        fname = os.path.basename(pdf_path)
        rel = os.path.relpath(pdf_path, pdf_dir)
        # Unique per *file*, so two PDFs with the same name don't overwrite
        # each other (Zotero does store duplicates).
        doc_id = hashlib.md5(rel.encode("utf-8")).hexdigest()[:8]

        if doc_id in done or fname[:-4] in done:
            skipped_known += 1
            continue

        try:
            chunks = extract_chunks(pdf_path)
        except Exception as exc:
            print(f"[{n}/{len(pdfs)}] skipped (unreadable) {fname}: {exc}")
            skipped_empty += 1
            continue

        if not chunks:
            print(f"[{n}/{len(pdfs)}] skipped (no text layer, probably a scan) {fname}")
            skipped_empty += 1
            continue

        entry = file_map.get(fname.lower())
        apa = format_apa(entry)
        matched += bool(apa)
        base_meta = {
            "source": fname[:-4],
            "doc_id": doc_id,
            "apa": apa,
            "author": format_authors(field(entry, "author")),
            "year": clean_latex(field(entry, "year")),
            "title": clean_latex(field(entry, "title")).strip("."),
            "path": pdf_path,
        }

        print(f"[{n}/{len(pdfs)}] ingesting {fname} ({len(chunks)} chunks)")
        embeddings = model.encode([c[0] for c in chunks]).tolist()
        for i, ((text, page), emb) in enumerate(zip(chunks, embeddings)):
            meta = dict(base_meta, chunk_id=i, page=page)
            collection.upsert(
                documents=[text],
                embeddings=[emb],
                metadatas=[meta],
                ids=[f"{doc_id}__{i}"]
            )
        ingested += 1

    print(
        f"Ingestion complete: {ingested} PDF(s) indexed, "
        f"{skipped_known} already known, {skipped_empty} unreadable/scan-only, "
        f"{matched}/{ingested} matched to a BibTeX entry."
    )


if __name__ == "__main__":
    ingest(ZOTERO_PDF_DIR, BIBTEX_PATH, CHROMA_DIR)
