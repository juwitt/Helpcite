import re

from groq import Groq

from config import *

_client = None

# The prompt is split in two so you can swap the subject without touching the
# answer rules. See README ("Writing your own prompt") for tips and examples.

# WHO you are talking to and about what. Keep it short and specific.
DOMAIN_EXPERTISE = """You are a careful research assistant for a private literature library.
You answer strictly from the literature excerpts the user hands you, not from general
knowledge. The user is an expert reader: no textbook basics, no small talk, no padding.
State the field and the recurring concepts you should know (edit this block to fit your
library, e.g. "empirical social research; be precise about study design, sample and effect
sizes")."""

# HOW to answer. These rules keep the output checkable against the sources.
ANSWER_RULES = """How to answer:
- Use only the numbered excerpts below. Each one starts with [n], an APA-style reference and
  its page number. Nothing else is available to you.
- Maximum 8 bullets. One claim per bullet, no preamble and no summary at the end.
- Put the excerpt number directly behind the claim it supports, e.g. [3]. When you name a
  source, use its reference line (author, year, page).
- Never invent authors, titles, page numbers, statistics or quotations. If you are unsure
  whether a statement is in the excerpts, leave it out.
- Quote the decisive wording verbatim and briefly, in quotation marks.
- Flag weak evidence openly: single study, old publication year, different population,
  statement taken from a literature review rather than the original study.
- If the excerpts do not answer the question, say exactly that - and say what kind of source
  would be needed. Do not fall back on general knowledge.
- Distinguish what the literature says from your own evaluation.
- Reply in Markdown only: bullet lists, **bold** for the key term, no headings, no code
  fences, no "Here is your answer" introduction."""

SYSTEM_PROMPT = DOMAIN_EXPERTISE + "\n\n" + ANSWER_RULES


def get_client():
    """Create the Groq client lazily so importing this module never fails."""
    global _client
    if _client is None:
        _client = Groq()  # reads GROQ_API_KEY from environment variable
    return _client


def build_context(retrieved_chunks) -> str:
    """Turn retrieved chunks into one numbered block for the prompt."""
    context_parts = []
    for i, (doc, meta) in enumerate(zip(
        retrieved_chunks["documents"][0],
        retrieved_chunks["metadatas"][0]
    ), start=1):
        label = meta.get("apa") or meta.get("source") or "unknown source"
        page = meta.get("page")
        where = f"p. {page}" if page else "p. n/a"
        context_parts.append(f"[{i}] {label} ({where})\n{doc}")
    return "\n\n---\n\n".join(context_parts)


def clean_answer(text: str) -> str:
    """Strip the ``` fences chat models like to add around Markdown answers."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def generate_answer(query: str, retrieved_chunks: dict) -> str:
    """Send query + retrieved chunks to Groq and return the answer."""
    context = build_context(retrieved_chunks)
    user_prompt = f"""Query: {query}

Literature excerpts:
{context}

Answer with citations:"""

    response = get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    return clean_answer(response.choices[0].message.content)
