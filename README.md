# Helpcite

A small retrieval-augmented chatbot over your own Zotero library. You type a claim
("satisficing is more common in web surveys than in face-to-face surveys"), it searches the
full text of your PDFs, and answers with the passages it used.

```
Zotero PDFs + BibTeX
        |
   [1] Ingestion        <- once per library (takes a while)
   PDF -> chunks -> embeddings -> ChromaDB
        |
   [2] Query pipeline   <- on every question
   Query -> embedding -> similarity search -> top-K chunks
        |
   [3] Generation
   Chunks + query -> Groq -> answer + sources + passages
        |
   [4] Streamlit UI
```

```
helpcite/
|-- config.py           # paths and parameters (fallback defaults, normally untouched)
|-- ingest.py           # run once: builds the index from all your PDFs
|-- ingest_new.py       # run later: adds PDFs you put in Zotero since then
|-- retriever.py        # ChromaDB similarity search
|-- generator.py        # Groq API call + assistant prompt (tweak the persona here)
|-- app.py              # Streamlit UI ("streamlit run app.py")
|-- requirements.txt    # pip packages
|-- library.bib         # your Zotero BibTeX export
|-- .env.example        # template (ships with the repo)
|-- .env                # your secrets + paths (you create this, git-ignored)
`-- chroma_db/          # vector index, created automatically
`-- chroma_db/          # vector index, created automatically
```

## What you need beforehand

| Requirement | Notes |
| --- | --- |
| Python 3.10-3.12 | 3.12 recommended |
| A free Groq API key | <https://console.groq.com/keys> - no payment details needed |
| Zotero, installed locally | With the PDFs you want to search already synced to your computer |
| ~5 GB free disk space | For the local embedding model (downloads once) |

## Step-by-step setup

### 1. Install Python packages

From the project folder:

```bash
python -m venv .venv          # Windows: py -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create your `.env` file

The app keeps everything personal - your API key and your local paths - out of the source
code, in one small text file called `.env`. Two plain-text files with confusingly similar
names are involved:

| File | What it is | In git? |
| --- | --- | --- |
| `.env.example` | Template that ships with the project. Only placeholders and documentation - **never put your real key in here.** | yes |
| `.env` | Your own copy with the real values. Created by you, read by the app, **git-ignored so nothing private is committed.** | no (local only) |

So you make a copy of the template under the shorter name, then edit the copy. In the project
folder:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

That is literally "make `.env` from `.env.example`". No software installs anything here; if
your file manager hides files starting with a dot, you can instead open `.env.example` in an
editor and save it as `.env`, or copy manually.

Open the new `.env` and replace the two placeholders:

```ini
GROQ_API_KEY=gsk_replace_me_with_your_key
ZOTERO_PDF_DIR=
```

becomes, for example:

```ini
GROQ_API_KEY=gsk_1a2b3c..............................
ZOTERO_PDF_DIR=C:/Users/you/Zotero/storage
```

- `GROQ_API_KEY`: paste the key from <https://console.groq.com/keys>.
- `ZOTERO_PDF_DIR`: path to your Zotero **storage** folder - the one full of randomly named
  subfolders like `Zotero/storage/3XK9QP7T`, each holding a PDF.
  - Windows: `C:/Users/you/Zotero/storage` (forward slashes are fine)
  - macOS: `/Users/you/Zotero/storage`
  - Linux: `/home/you/Zotero/storage`
  - Not sure? In Zotero: Settings -> Advanced -> Files and Folders -> **Data Directory
    Location**; `storage` sits inside that folder.
  - Use the `storage` folder, **not** `Zotero/files` (that one only holds files you opened
    outside Zotero).

Rules for the file: one `NAME=value` per line, no spaces around `=`, no quotes needed (paths
may contain spaces without them). If the key ever rotates, edit `.env` and restart Streamlit.

You can alternatively set these values directly in `config.py`, but `.env` wins over
`config.py` defaults and stays out of your commits.

### 3. Export your Zotero library to BibTeX

This fills `library.bib`. Ingest matches the exported entries to your PDFs and stores a
proper reference (author, year, title, journal) next to every chunk, so the chatbot can cite
real bibliographic data instead of file names. Do it once:

1. In Zotero select **File -> Export Library...** (or select single items first and use
   **File -> Export Items...**).
2. Format: **BibTeX**.
3. Tick **Export Files** off (the app reads the PDFs directly) and **Keep updated** if you
   want it refreshed automatically.
4. Make sure **Export Notes / Files** does not strip the `file` field - the exporter includes
   `file = {files/123/Author - Year - Title.pdf}`, and that file name is how a PDF gets
   matched to its citation.
5. Save as `library.bib` in this project folder, replacing the one that ships here.

Can it be empty or missing? Yes - ingestion still works, you just get a warning and the
chunks fall back to being labelled by file name. An empty `library.bib` never removes
anything from the index.

The final ingest line tells you how well matching went, e.g.
`321/340 matched to a BibTeX entry`.

### 4. Build the index (ingestion)

Only PDFs with a text layer can be searched. Only *stored* attachments (the ones Zotero copied
into `storage`) are found - **linked files** stay outside that folder and are skipped.

```bash
python ingest.py
```

This walks every `*.pdf` under `ZOTERO_PDF_DIR`, splits it into ~1000-character chunks with a
150-character overlap, embeds them locally with `all-MiniLM-L6-v2` and writes everything to
`chroma_db/`. Each chunk remembers **which page it came from** and the APA reference of its
paper. Expect this to take a while: roughly 1-3 seconds per PDF on a laptop CPU, so a
1000-item library is a couple of hours. Run it overnight or do a first round with a small
subset.

You can safely stop it and restart later, and re-running it will not duplicate anything -
existing chunks are overwritten. Because `python ingest.py` re-reads everything, it is also
the way to rebuild after you changed `CHUNK_SIZE`, `CHUNK_OVERLAP` or `EMBED_MODEL`.

### 5. Start the app

```bash
streamlit run app.py
```

The browser opens the chat window automatically (otherwise go to
<http://localhost:8501>). Type your claim or question, press **Search**, and you get two
columns:

- **Answer** - up to 8 bullet points from the Groq model. Each claim carries the number of
  the excerpt it came from, e.g. `[3]`. The model is told to answer only from the retrieved
  excerpts and to say so when your library does not support a claim.
- **Retrieved passages** - numbered to match the answer. Expand one to see its reference,
  the **page number**, the PDF path and the verbatim text the model saw. Outdated/default
  pieces of the model output (` ```markdown ` fences) are stripped, so the answer renders as
  clean Markdown.

The sidebar shows how many chunks live in your index and lets you raise/lower the number of
passages per query for the current search.

### 6. Adding new papers later

Put the new PDFs into Zotero as usual (they end up in `storage`), then:

```bash
python ingest_new.py
```

It compares what is already in `chroma_db/` with what is in your storage folder and only
embeds the difference - a couple of seconds per new paper instead of a full re-run.

## Tuning

All knobs live in `config.py`:

| Setting | Default | What it does |
| --- | --- | --- |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embedding model. Small and fast; swap for `BAAI/bge-base-en-v1.5` for better recall |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chat model. See <https://console.groq.com/docs/models> |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 1000 / 150 | Chunk length in characters. Larger = more context, fuzzier matches |
| `TOP_K` | 10 | How many chunks are shown to the model |

## Writing your own prompt

The assistant's behaviour is set in `generator.py` and split into two blocks so you can change
the subject without touching the answer rules:

- `DOMAIN_EXPERTISE` - who you are and what field you work in.
- `ANSWER_RULES` - how the answer must be formatted, cited and hedged.

`SYSTEM_PROMPT = DOMAIN_EXPERTISE + ANSWER_RULES` is what goes to the model; the query and the
numbered excerpts are appended as the user message at runtime. Tips for both blocks:

- Say what the model **is allowed** to use ("only the excerpts below"), not just what to do.
  That single line is what stops it filling gaps from memory.
- Name your field and recurring concepts. The narrower the domain, the better the wording:
  "survey methodology: satisficing, mode effects, CAPI/CATI/CAWI" beats "science".
- Demand a citation per claim and forbid invented ones explicitly. "Never invent page
  numbers" measurably reduces plausible-looking fabrications.
- Ask it to admit gaps. Without "say so when the excerpts do not support an answer", models
  guess instead of staying silent.
- Ask for verbatim quotes. That makes every bullet checkable in the sidebar column.
- Fix the shape: bullet count, Markdown only, no code fences, no preamble.
- Change **one thing per iteration** and re-run two or three real queries. Compare retrieved
  passages first - if the right chunk is missing, the problem is retrieval (`TOP_K`,
  `CHUNK_SIZE`), not the prompt.

Example of a narrower `DOMAIN_EXPERTISE` (the app's previous survey-methodology persona):

```text
You are a research assistant for empirical social research, especially survey methodology.
Core concepts: satisficing (non-differentiation, acquiescence, straight-lining) and survey
modes: CAPI/face-to-face (interviewer administers in person), CATI (telephone), CAWI (web
self-administered), CALVI (interview via live video). Distinguish carefully between modes
when comparing results. The user is an expert: no textbook explanations, no small talk.
```

**Citations:** every chunk carries an APA-style reference built from `library.bib` (author,
year, title, journal, volume, pages, DOI) plus its page number, and that is what the model
sees. It is a best-effort approximation of APA, not a bibliography checker - skim the
reference before pasting it into a paper. Papers whose PDF name is not present in the bib
`file` field fall back to being labelled by file name, so keep the `<Author> - <Year> -
<Title>.pdf` naming Zotero produces by default.

## What the `chroma_db/` folder is

After the first ingest you will find a new folder `chroma_db/` next to the scripts. It is
created automatically - nothing to install, no account, no server to start. ChromaDB is an
embedded vector database: a library the app uses through Python, stored as plain files.

**Why it exists.** Similarity search cannot run on PDF text directly. During ingest every
chunk is translated into a list of 384 numbers - an *embedding* - by the local model
`all-MiniLM-L6-v2`. Chunks with similar meaning end up close together in that number space,
which is how a question like "does mode affect satisficing?" finds the right passage even
though it shares no words with it. ChromaDB is simply where text, embeddings and metadata
(reference, page, file path) are kept between runs. Without it, every query would have to
re-read your whole library.

In short: the folder **is** your search index. Everything in it can be rebuilt from your PDFs
and `library.bib` at any time; it holds nothing that cannot be regenerated.

Practical notes:

- **Size:** roughly 3 KB per chunk, so a library of a few hundred papers lands around
  a few tens of MB. It grows with `CHUNK_SIZE` and with the number of pages.
- **Local only.** Everything before the answer happens on your machine. Only your question
  and the handful of retrieved excerpts are sent to Groq - never your whole library.
- **Leave it alone** during normal use. Never edit the files inside, and do not commit it
  (it is already in `.gitignore`).
- **Delete it only to rebuild.** `rm -rf chroma_db` (Windows: delete the folder in Explorer)
  followed by `python ingest.py` restores a clean index. You need that after changing
  `EMBED_MODEL`, `CHUNK_SIZE` or `CHUNK_OVERLAP`: embeddings are tied to the model and to how
  text was split, so keeping old and new chunks mixed gives poor retrieval. Losing or
  deleting the folder by accident costs nothing but ingest time - that is what a fresh clone
  or a new laptop does anyway, since the index is not shared.

## Known limitations

- Reference lists and indexes inside your PDFs are ingested too, so occasionally a match
  comes from a bibliography rather than the body text.
- Only English text retrieves well - `all-MiniLM-L6-v2` is monolingual. Use a multilingual
  embedding model for a German library.
- Two copies of the same file are indexed twice (they keep separate ids); retrieval may show
  the same passage twice.
- `ingest.py` reads the whole library each time, so updating one paper's file contents needs
  a full re-run to be picked up (same name = no change detected).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ZOTERO_PDF_DIR is not set` | Set it in `.env` (see step 2) |
| `No PDFs found in <path>` | You pointed at the wrong folder - use `Zotero/storage`, not `Zotero/files` or the data directory itself |
| Lots of `Skipped (no text layer, probably a scan)` | Those are scans without OCR. Run them through an OCR tool first
  (`ocrmypdf`), or accept that they are not searchable |
| `Your system has an unsupported version of sqlite3` | ChromaDB needs sqlite >= 3.35. Use Python 3.11/3.12 from python.org, or install `pysqlite3-binary` and add `__import__("pysqlite3")` patching before importing chromadb |
| Citations come out as file names instead of "Author (Year)" | The paper was not matched in `library.bib`. Re-export it including the `file` field (step 3) and re-run `python ingest.py` |
| `No GROQ_API_KEY found` | Missing or empty key in `.env`; restart `streamlit run` after editing it |
| `No literature index found` | Ingest has not run yet, or `chroma_db/` was deleted - run `python ingest.py` |
| Answer arrives wrapped in ` ``` ` code fences | Should not happen any more - `clean_answer()` in `generator.py` strips them. If a model variant still does, extend that helper |
| Several identical passages listed | Duplicated PDFs in your Zotero storage; `retriever.dedupe()` removes exact repeats within one query |
| Answers are generic / off topic | Nothing in your index matched. Try `ingest_new.py`, raise `TOP_K`, or re-check step 2's folder |
| Everything is slow on the first query | The embedding model is being loaded once; later queries are faster |
| Answers got worse after changing `config.py` | Delete `chroma_db/` and re-run `python ingest.py` - see ["What the `chroma_db/` folder is"](#what-the-chroma_db-folder-is) |
