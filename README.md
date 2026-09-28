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

![Example use of Helpcite: a claim in the query box, the cited answer on the left, the
retrieved passages with page numbers on the right](docs/example_use.png)

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
|-- docs/               # documentation, incl. the screenshot above
|-- chroma_db/          # vector index, created automatically
```

## What you need beforehand

| Requirement | Notes |
| --- | --- |
| Python 3.10-3.12 | 3.12 recommended |
| A free Groq API key | <https://console.groq.com/keys> - no payment details needed |
| Zotero, installed locally | With the PDFs you want to search already synced to your computer |
| ~5 GB free disk space | For the local embedding model (downloads once) |

## Three similarly named things

This project uses three names that are easy to mix up. They have nothing to do with each
other, and step 1 creates the first one while step 2 asks you to create the second:

| Name | Kind | Created by | Purpose |
| --- | --- | --- | --- |
| `.venv` | folder | **you**, in step 1 | Virtual environment: an isolated copy of Python holding the installed packages |
| `.env` | file | **you**, in step 2 | Settings: your Groq key and your Zotero path |
| `.env.example` | file | ships with the repo | Template you copy `.env` from |

(`chroma_db/` - a fourth one - is the generated search index, see its own section below.)

## Step-by-step setup

### 1. Install Python packages

First, open the project folder in a terminal. In Windows: open **PowerShell**, then
`cd "C:\path\to\helpcite"`.

Creating the virtual environment (`.venv`) is optional but recommended: it keeps this app's
packages out of your global Python. If you skip it, just run `python -m pip install -r
requirements.txt` and step 1 is done.

**PowerShell (Windows - the default terminal in VS Code and Terminal app):**

```powershell
python -m venv .venv              # creates the .venv folder
.venv\Scripts\Activate.ps1        # starts using it
python -m pip install -r requirements.txt
```

Use `python -m pip`, not `pip`: `pip` runs a separate `pip.exe` launcher that Windows often
blocks with `Zugriff verweigert` / access denied, while `python -m pip` uses the interpreter
you just started and always works.

If activating fails with a message about "running scripts is disabled", allow it once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

then repeat `.venv\Scripts\Activate.ps1`. When it worked, the prompt starts with `(.venv)`.

**Command Prompt (cmd), another Windows option - type two lines:**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

**macOS / Linux (for completeness):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Notes:

- The **`.venv` folder is a Python package space**, nothing you ever open or edit. The
  **`.env` file** from step 2 is your config - that is the one you fill in.
- Installing takes a few minutes and downloads roughly 2 GB (PyTorch for the embedding
  model). Run it once.
- Every time you open a new terminal for this app, activate again - otherwise Python cannot
  find `streamlit`. VS Code users can instead select the interpreter once:
  Ctrl+Shift+P -> `Python: Select Interpreter` -> `.venv`.

### 2. Create your `.env` file

The app keeps everything personal - your API key and your local paths - out of the source
code, in one small text file called `.env`. Two plain-text files with confusingly similar
names are involved:

| File | What it is | In git? |
| --- | --- | --- |
| `.env.example` | Template that ships with the project. Only placeholders and documentation - **never put your real key in here.** | yes |
| `.env` | Your own copy with the real values. Created by you, read by the app, **git-ignored so nothing private is committed.** | no (local only) |

So you make a copy of the template under the shorter name, then edit the copy. In the project
folder, in the same terminal as step 1:

**PowerShell (Windows):**

```powershell
Copy-Item .env.example .env
notepad .env
```

**Command Prompt (cmd):**

```bat
copy .env.example .env
notepad .env
```

That is literally "make `.env` from `.env.example`" - nothing is installed, no admin rights
needed. If your file manager hides files starting with a dot, you can also open
`.env.example` in an editor and use **Save as** with the name `.env` (Notepad appends `.txt`
when you type `.env` - instead choose **Save as type: All files** and enter `.env`).

**macOS / Linux:**

```bash
cp .env.example .env
```

Open the new `.env` (the previous step opened it in Notepad) and replace the two placeholders:

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
  - Windows tip: navigate into the folder in Explorer, then Shift+right-click it ->
    **Copy as path** and paste it after `ZOTERO_PDF_DIR=`. Keep either slash style.

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

### 5. Write your prompt (do this before the first launch)

Do this step **before** you start the app for the first time - the prompt decides what the
model does with every query, and changing it later means comparing answers across two
different settings.

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
Two very important concepts, you should be aware of (and assume the user is aware of, too):

1. Survey satisficing: respondent behavior where answers are "good enough" rather than
   optimal, including phenomena such as non-differentiation (which is sometimes also called
   straight-lining), extremes or midpoint selection, speeding, and heaping.
2. Survey modes: the different methods of data collection, including:
   - CAPI (Computer-Assisted Personal Interviewing), sometimes synonymous with F2F
     (face-to-face): an interviewer administers the survey in person using a device.
   - CATI (Computer-Assisted Telephone Interviewing): an interviewer conducts the survey
     by phone.
   - CAWI (Computer-Assisted Web Interviewing): self-administered survey via web browser.
   - CALVI (Computer-Assisted Live Video Interviewing): an online mode where interviewers
     and respondents interact via live video feed.

Distinguish carefully between modes when comparing results. The user is an expert: no
textbook explanations, no small talk.
```

**Citations:** every chunk carries an APA-style reference built from `library.bib` (author,
year, title, journal, volume, pages, DOI) plus its page number, and that is what the model
sees. It is a best-effort approximation of APA, not a bibliography checker - skim the
reference before pasting it into a paper. Papers whose PDF name is not present in the bib
`file` field fall back to being labelled by file name, so keep the
`Author - Year - Title.pdf` naming Zotero produces by default.

### 6. Start the app

```bash
python -m streamlit run app.py
```

`streamlit` on its own launches a `streamlit.exe` that Windows can block with the same
`Zugriff verweigert` you may already have seen from `pip`; `python -m streamlit` avoids it.

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

### 7. Adding new papers later

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
- **Delete it only to rebuild.** Delete the folder in Windows Explorer (or
  `Remove-Item -Recurse -Force chroma_db` in PowerShell; `rm -rf chroma_db` on
  macOS/Linux) and run `python ingest.py` again for a clean index. You need that after changing
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

### Setup problems (Windows)

| Symptom | Fix |
| --- | --- |
| `run scripts is disabled` after `.venv\Scripts\Activate.ps1` | Once per PC: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force`. Or skip activation entirely and call the venv's Python directly: `.venv\Scripts\python.exe -m pip install -r requirements.txt`, later `.venv\Scripts\python.exe -m streamlit run app.py` |
| `pip.exe: Zugriff verweigert` / access denied | Don't use `pip`: run `python -m pip install -r requirements.txt` with the venv active. The `pip.exe` launcher is a separate executable that Windows often refuses to start, especially inside `Documents`, while `python -m pip` runs through the interpreter that is already running. (`python pip install ...` without `-m` is also wrong: Python then looks for a file named `pip`.) Still failing? Windows Defender -> **Ransomware protection -> Controlled folder access** may be blocking writes into `Documents`; allow `python.exe` there, or move the project to `C:\dev\helpcite` |
| `python` is not recognized | Reinstall Python from python.org and tick **Add python.exe to PATH**; then restart the terminal |
| `No module named ...` although the install ran | You are using a different interpreter. With the venv active use `python -m pip <package>`; in VS Code pick the interpreter once: Ctrl+Shift+P -> `Python: Select Interpreter` -> `.venv` |
| Install seems frozen | First run downloads ~2 GB (PyTorch). Let it finish; after that it is cached |

### Running the app

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
