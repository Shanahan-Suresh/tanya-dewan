# parlimen-search

Ask Malaysian law and Malaysia's Parliament in plain Malay or English. Answers quote the Act and
section, or the Hansard sitting, date, speaker and page, so every claim can be checked. Each Act
links to the debates on the bill that made it. Oral questions are joined to the ministers'
answers, and ministers' commitments are tracked with their quotes.

The corpus, the enrichment, the search index, the eval and the pages with the MCP server
(phases 0 to 6) are built; phase 7 (public demo and launch) is planned and starts after the
owner's refinement passes. The eval passes five of six targets: law recall@10 0.907, language gap 0 points, search 95th percentile 2.83 s on a CPU,
answers correct 77%, every claim backed in 82% of answers. Hansard recall@10 (0.727 against
0.80) falls short; the table is in `ROADMAP.md`, Phase 5. Answer sentences that no citation
reaches are dropped in code.
`ROADMAP.md` holds the plan, phases and targets; `PROGRESS.md` holds the current state. The
name is a working name, and the repository stays private until the owner says otherwise.

## What it holds

- 1,586 Act reprints (English and Malay) from the Laws of Malaysia portal, cut into 66,026
  sections, scanned reprints read by OCR.
- 1,037 sittings of the Dewan Rakyat and its Special Chamber, 14th and 15th Parliaments to
  22 October 2026: 361,676 speeches, each with its speaker, seat, party on the day, time, page
  and question number.
- For each of 30,091 agenda extracts, from Claude: question-answer pairs, topics, entities,
  summaries in English and Malay, and ministers' commitments, each commitment's quote checked
  against the Hansard text.
- A hybrid index of 282,184 chunks: BM25 (SQLite FTS5), Qwen3-Embedding-0.6B vectors and rank
  fusion, with Claude Haiku 5.5 reranking the top 20 hits through the API, and filters by Act,
  language, date, Parliament, chamber, speaker, party and topic.

## Run

From the repo root, with the `.venv` (Python 3.14):

```
.venv\Scripts\python.exe -m parlimen.search "cuti bersalin pekerja" --kind law
.venv\Scripts\python.exe -m parlimen.ingest            # bring new sittings into the index
.venv\Scripts\python.exe -m parlimen.records build     # the page database, after each ingest (site stopped)
.venv\Scripts\python.exe -m parlimen.web               # the site on http://127.0.0.1:8780
.venv\Scripts\python.exe -m parlimen.digest --sector energy --from 2026-10-19 --to 2026-10-23
.venv\Scripts\python.exe tools\check_phase6.py         # click-through check against the running site
.venv\Scripts\python.exe -m parlimen.evaluate run      # retrieval eval, all arms (Haiku arms: about [amount removed])
.venv\Scripts\python.exe -m parlimen.judge             # answer quality on the hand set (about [amount removed])
.venv\Scripts\python.exe -m pytest -q
```

The MCP server (`parlimen/mcp_server.py`, registered in `.mcp.json`) gives Claude five tools:
`search_law`, `search_debates`, `read_section`, `read_sitting` and `list_commitments`.
Install the packages with `uv pip install --python .venv\Scripts\python.exe -r requirements.txt`.

Search, reranking, answers and the digest call the Claude API with the key in `~/.claude/anthropic-api-key.txt`;
every call is logged with its cost in `data/api-usage.jsonl`.

Each module's docstring gives its inputs, outputs and options. The source texts and everything
built from them stay in the git-ignored `data/`.
