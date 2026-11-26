# parlimen-search: progress

Current state and what is owed. `ROADMAP.md` is the plan; `docs/sources.md` is the phase 0 finding.

## Decisions the owner has made

- parlimen-search goes before spoilerless; Acts and Hansard ship together in release 1.
- Hansard of the 14th and 15th Parliaments, plus the Special Chamber (Dewan Khas) record.
- Enrichments: question-answer pairs, topic and entity tags, summaries in English and Malay,
  commitments tracker.
- Money path: Track A (topic alerts and a weekly digest) behind its gate; Track B (data licence)
  as a by-product.
- The five choices on the review page are approved (records licence, no scores on MPs,
  attendance after launch, two-language summaries, launch during a sitting). Page:
  https://claude.ai/artifact/Y7eboyDpffNvuniLQNU8gh (source `docs/roadmap-page.html`).
- Act texts come from the Laws of Malaysia portal through the installed Chrome, as a visitor gets
  them. No decryption code of our own.
  every commitment, phase 5 run before 31 October (so phase 4 comes first), and party history
  for every MP. October spend logged before them: [amount removed].

## Phase 0: done

- The owner signed off the copyright reading in chat on 2026-10-22 ("yess all confirmed"),
  recorded in the review page db (`verdicts/copyright-signoff`, `verdicts/_confirmed_step0`).

## Phase 1: the law corpus

- Done: `parlimen/acts.py` (listing in Chrome, cached raw rows in `data/raw/acts/listing.json`,
  `data/acts.csv`, PDFs under `data/raw/acts/<act>/<lang>-<as at>.pdf`, log
  `data/raw/acts/downloads.jsonl`), `tests/test_acts.py` (6 pass), `tools/check_acts.py`.
  Pilot of 10 Acts plus Acts 26, 265 and 762 checked: right Act, language and date in every file.
- Download done: 1,586 of 1,589 PDFs cached. The portal's file server fails on three (Act 781
  BM, 175 BI, 150 BI): status 200 with nginx's "500 Internal Server Error" page. Recorded in
  `docs/sources.md`. A re-run skips cached files and retries these:
  `.venv\Scripts\python.exe -m parlimen.acts`.

## Act section parser (`parlimen/act_text.py`) and OCR (`parlimen/act_ocr.py`): done

Run: `.venv\Scripts\python.exe -m parlimen.act_text [--only NUMBER ...]`. Writes
`data/act_sections.jsonl` (one record per section and language, with `notes` for the editorial
footnotes and `source` text or ocr) and `data/act-parse-report.csv` (one row per file; log
`data/act-parse.log`). `--only` rewrites both files with those Acts alone; run it without
`--only` before anything reads them.
OCR: `.venv\Scripts\python.exe -m parlimen.act_ocr --in-force` reads the scanned files of
in-force Acts into the cache `data/ocr/` (a re-run spends nothing on cached pages); then re-run
`parlimen.act_text`. Per-page report `data/act-ocr-report.csv`. Needs Tesseract at
`C:\Program Files\Tesseract-OCR` (winget `UB-Mannheim.TesseractOCR`) and the tessdata_best
models eng, msa and osd in `data/tessdata/`. The choice of readers came from
`tools/bench_ocr.py` (results `data/bench/ocr/`).
Check: `tools/check_act_text.py --sample 50 --seed N` compares text-layer sections with poppler.
Tests: `tests/test_act_text.py` (7) and `tests/test_act_ocr.py` (5); suite 21 pass.
- Measured 2026-10-22: 66,026 of 66,307 listed sections found; 1,356 of 1,420 text files have no
  section missing (1,319 of 1,368 from the text layer, 37 of 52 from OCR); six samples of 50
  (748 of 753 in-force Acts have text) are in `docs/sources.md`.
- How it reads a file, and why, is in the module docstrings: pdfium text (pdfplumber loses
  digits in the 2006 font), letter-spaced words rebuilt from character boxes, running heads
  found by their page numbers, notes found by their small type; for scans, pages turned upright,
  margin notes split from the section line, Sonnet on the pages Tesseract disagrees with.
Owed: optional polish, by the report: 281 listed sections not found (64 files; 63 of the sections
   in OCR files, some from years such as "1949" read as entries on faded arrangement pages),
   2,689 sections with no heading line in the body, 61 Acts whose two languages list different
   sections, about 550 sections that still hold a "NOTE" line in normal type, 13 letter-spaced
   runs left. Five OCR pages flagged `check` in `data/act-ocr-report.csv`.

## Phase 2: the Hansard parser: done

Run: `.venv\Scripts\python.exe -m parlimen.hansard [--pilot] [--chamber DR|KK] [--dates ISO ...]`.
It downloads each sitting through `parlimen/fetch.py`, then writes `data/speeches.jsonl` (one
record per speech: speaker label, role, name, seat or Senator, time, page, topic, question
number, verbatim text), `data/hansard-report.csv` (one row per sitting, with the labels left
unresolved) and `data/members.csv` (each Parliament's members from every cached Dewan Rakyat
attendance list). A sitting with no PDF or a failed download gets a report row and the run goes
on. Tests: `tests/test_hansard.py` (10); suite 30 pass.
- How it reads a sitting is in the module docstrings: bold leads ending in ":" are speaker
  labels, wholly bold capitals are headings, "■1010" and the clerk's "2.49 ptg." notes set the
  time, a numbered bold lead opens a question and its number holds until the next one or the
  next heading. A speaker with no seat in the label takes it from the sitting's attendance list,
  then from the Parliament's register (the Special Chamber prints no list).
- Pilot (measured 2026-10-22, 5 days per Parliament and per chamber, 20 days): 6,969 speeches,
  6,004 of 6,009 named speeches resolve to a seat or a Senator, 0 date mismatches, 0 failures.
  Hand checks against the PDF text: speakers, register matches, question numbers (gaps are
  questions the source skips), topics and times. Two unresolved labels are source typos
  ("[Kuala baharu]" on 2022-12-19).
- Full run (measured 2026-10-22, log `data/hansard-full.log`): 1,033 sittings, 359,904 speeches
  (349,114 Dewan Rakyat, 10,790 Special Chamber); 319,312 of 319,484 named speeches (99.95%)
  resolve to a seat or a Senator; 0 failures; 1 sitting with no PDF (KK 2018-11-15); 10 date
  mismatches, all typos in the PDF date line (`docs/sources.md`). A hand sample of 48 matches
  made by name alone was all correct.
- After a parser fix, `python tools/reparse.py --dates ISO ...` re-parses those sittings in place
  in `data/speeches.jsonl` and `data/enrich/units.jsonl`; it refuses when extract ids or speech
  seqs change. DR 2023-10-18 is re-parsed: its stray "researcher" before a heading is gone (160
  speeches, 12 extracts).
- Owed: optional polish. 172 named speeches stay unresolved, mostly source typos ("Tuan Look
  Siew Fook", "Tuan Pengerus") and Speakers from outside the House. `data/members.csv` keeps
  81 keys seen once, some with the office in front of the name ("timbalan menteri ... hanifah
  hajar taib"); the word match still finds them. Members' dates and party changes are not
  recorded.

## Phase 3: enrichment: done

Run: `.venv\Scripts\python.exe -m parlimen.enrich pilot|audit|submit|collect|finish` (module
docstring). Extracts: `data/enrich/units.jsonl` (29,971, median 6,906 characters, one agenda item
each, a question kept with its answers). Raw answers `data/enrich/raw.jsonl`; checked pilot
records `data/enrich/pilot.jsonl`; full records `data/enriched.jsonl`. Tests:
`tests/test_enrich.py` (4); suite 34 pass.
- Pilot (measured 2026-10-22; DR 2019-07-02, 2020-07-21, 2023-02-28, 2025-12-04, KK 2024-06-27;
  log `data/enrich-pilot.log`): 212 extracts, 0 failures, 207 question-answer pairs, 100
  commitments kept and 1 dropped, 8 figures and 720 entities dropped by the code checks;
  1,260,545 input and 660,248 output tokens, [amount removed] at standard rates.
- The entity check searches the speech text, the speaker labels and the agenda heading: 16 of
  3,672 pilot entities fail it.
- Blind Opus audit of 40 pilot records (`enrich audit`, log `data/enrich-audit.log`, files
  `data/enrich/audits/`, [amount removed]): 30 publishable, 16 major defects. One is a judge error
  (Muhammad Bakhtiar Wan Chik was MP for Balik Pulau, as the parser says), so 31 of 40. The
  real defects are in summaries: a second exchange left out (DR-2019-07-02-006), proposals or
  progress overstated (-003, -025, DR-2023-02-28-028), an exchange misread (DR-2020-07-21-021,
  -031), a motion understated (DR-2025-12-04-026, -028), one extract with its question-answer
  pairs and offers missed (DR-2025-12-04-022). The benchmark had 23 of 24.
- A/B (`tools/ab_enrich.py`, results `data/bench/enrich-ab/`, log `data/bench/ab-enrich.log`),
  on the 10 failing and 10 passing audited extracts, blind Opus audit: base 0 and 10
  publishable, 16 major; strict summary instruction 7 and 9, 8 major, 30% more cost; strict
  with effort "high" 8 and 8, 8 major, twice the cost. The strict instruction is in
  `enrich.SYSTEM` as prompt version 2 (`PROMPT_VERSION`; raw answers carry it, older answers
  count as not done; audits go to `data/enrich/audits/prompt<N>/`). The prompt-1 pilot records
  are kept in `data/enrich/pilot-prompt1.jsonl`.
- Prompt 2 pilot (measured 2026-10-22): 212 records, 0 failures, 192 question-answer pairs, 93
  commitments kept and 1 dropped, 5 figures and 12 entities dropped; [amount removed] at standard
  rates, so the full run is about [amount removed] on the Batch API. Blind audit, 40 records, seed 2 (`data/enrich/audits/prompt2/`, [amount removed]): 33 publishable, 8
  major defects (5 unsupported_or_wrong, 1 missed_item, 1 false_commitment, 1 malay_quality).
- Owner review page: https://claude.ai/artifact/YVjbeGgS1Bu28rAtFS9hHc (source
  `docs/enrich-pilot-review.html`, built by `python tools/pilot_review.py` from
  `tools/pilot_review_template.html`; capabilities `{db: {}}`). 20 prompt-2 records; each
  starts "Right"; db collection `verdicts` (`verdicts/<unit id>` with verdict and note,
  `verdicts/overall`, Confirm writes `verdicts/_confirmed` with the list of mistakes).
- The owner does no human review (2026-10-22): Claude reviews the 20 records in its place. The
  review page stays as a record and is not waited on.
- Submitted 2026-10-22: 29,759 extracts in 6 batches (`data/enrich/batches.json`, log
  `data/enrich-submit.log`). A detached loop runs `enrich collect` every 10 minutes (log
  `data/enrich-collect.log`); a re-run is `.venv\Scripts\python.exe -m parlimen.enrich collect`.
  A Sonnet subagent reviews the 20 page records against their speeches (findings in
  `data/enrich/claude-review.md`).
- Claude's review of the 20 records in place of the owner (`data/enrich/claude-review.md`): 13
  right, 7 with one minor defect each, 0 major; 10 of 11 commitments are real (one routine
  Tabung Haji quota request listed as a promise). No defect class beyond the audit's, so the
  prompt stays at version 2.
- Batch msgbatch_014qE6Y3YoDdYuyWPSD9CRu2 collected: 4,998 of 5,000 ok.
- Batch msgbatch_013RSxm9G8ZMYmWtXy9ELTUp collected: 5,000 of 5,000 ok. `cmd_submit` sends
  again any extract of a collected batch that has no ok answer.
- After 5 of 6 batches (16:02): 24,969 records, 26,663 question-answer pairs, 16,707
  commitments kept and 69 dropped, [amount removed] logged so far.
- Full run (measured 2026-10-22): 29,971 of 29,971 extracts have a checked record in
  `data/enriched.jsonl`; 31,668 question-answer pairs; 19,866 commitments kept and 89 dropped
  (quote not in the speech); 429 figures and 2,004 entities dropped; 175,434,244 input and
  137,785,797 output tokens; [amount removed] for pilots and full run, plus [amount removed] of Opus audits.
- Exit samples drawn by `tools/exit_samples.py` (seed 100) into
  `data/enrich/exit-samples.json`: 100 of 17,249 question-time pairs and 100 of 19,866
  commitments. A Sonnet subagent checks them in place of the owner (findings in
  `data/enrich/exit-review.md`).
- Exit result (`data/enrich/exit-review.md`): 99 of 100 oral questions joined to their answer
  (target 95%); 92 of 100 commitments real (target 85%; 89 under a stricter reading that drops
  conditional promises and forecasts). Failures: existing policy or past action given as a
  promise (5), vague aims with no action (3), one answer joined to the wrong question.

## Commitment check (`parlimen/commit_check.py`): done

Sonnet 5.5 (thinking "between_tools") reads each kept commitment with a 1,200-character window
of its speech and gives a verdict: promise, routine (kept, flagged), past_or_existing, vague,
not_government (dropped). It may correct a wrong paraphrase (`promise_fixed`). Verdicts in
`data/enrich/commit-check.jsonl`; `enrich.finish` applies them, so `enrich finish` keeps them.
Prompt version `CHECK_VERSION = 3`. Tests: `tests/test_commit_check.py` (4).
- Pilot on the exit sample (logs `data/commit-check-pilot*.log`): version 1 dropped 15 real
  promises; version 3 agrees with the exit review on 93 of 100, catches 6 of its 8 false ones,
  and found one reviewer error (C 97: a "promise" dated before the sitting). Kept share real
  about 98% in the sample. [amount removed] per pilot run.
- Full run (measured 2026-10-22, batches in `data/enrich/commit-check-batches.json`): every one
  of the 19,866 commitments has a verdict: 13,758 promise, 4,718 routine, 672 past or existing,
  674 vague, 51 not government; 2,519 paraphrases corrected; [amount removed]. `data/enriched.jsonl`
  keeps 18,469 commitments (89 dropped as not in the speech, 1,397 as not real).

## Party history (`parlimen/parties.py`): done

`python -m parlimen.parties` writes `data/parties.csv` (parliament, code, seat, member, party,
from, to; "" = term start or end, "?" = change with no date in the sources). Sources: Wikipedia
"Members of the Dewan Rakyat, 14th/15th Malaysian Parliament" and "Results of the 2022 Malaysian
general election by parliamentary constituency", fetched once through Chrome (Wikipedia returns
403 to the crawler's user agent) into `data/raw/wikipedia/`. Haiku reads only the 98 rows with
notes or by-elections (`data/parties-llm.jsonl`, [amount removed]); code checks dates and parties against
the row text, drops coalition names, bounds by-election members, takes the first party from the
election result (pendulum's DAP over the results page's PKR logo; Jeli fixed by hand in
`ELECTED_FIXES`). `parties.lookup()` gives party by (parliament, seat, date). Tests:
`tests/test_parties.py` (7); suite 45 pass.
- Measured 2026-10-22: 545 spells for 444 seats; 310,461+ of 313,974 speeches with a seat get a
  party (99.27%). Misses: 4 members with an undated change (Kuala Nerus, Tebrau, Silam/Lahad
  Datu, Tenom) and parser noise in seat names.

## Phase 4: links and index: done

Design (settled): novel-rag's pipeline (BM25 FTS5 + Qwen3-Embedding-0.6B + RRF +
Qwen3-Reranker-0.6B), settings added to `parlimen/config.py` (INDEX = `data/index/`).
- Law chunks: one per Act section and language, long sections cut at sentences (~400 tokens,
  60 overlap). Header: Act title, number, section and heading, reprint date.
- Debate chunks: speeches packed inside one enrichment unit to ~400 tokens (half of all
  speeches are under 61 characters), with every speaker and party (side table) and the business
  heading; the note (variant "hn") is the unit's English summary and topics. A gold debate key is
  (chamber, date, speech seq); any chunk covering the seq counts.
- Bill links: `python -m parlimen.links` -> `data/index/bill_links.csv`: 387 bill headings, 298
  linked, 46 supply bills, 19 not an Act (Constitution, ordinances), 24 unlinked. Penal Code is
  "KANUN KESEKSAAN" (no AKTA, no year).
- Cross-references: `links.xrefs(text, own)`; a reference followed by another law's name does
  not count. Kept only when the Act has the section.
- Chunks (`parlimen/chunk.py`): law text is cleaned of the reprints' U+FFFE hyphens and
  Symbol-font characters. Index (`parlimen/index.py`): `index.db` with FTS5 `fts_h` and
  `fts_hn`, side tables `speakers`, `topics`, `xrefs`; vectors in
  `data/index/vectors-<size>-<variant>/part-NNNN.npy`. Run: `python -m parlimen.index build`,
  then `embed --variant h hn`, then `stats`.
- Build (measured 2026-10-23, rebuild): 281,364 chunks (87,807 law, 193,557 debate), mean 314
  tokens, max 479; 28,856 cross-references; 3,866 debate extracts linked to an Act. The ingest
  of DR and KK 2026-10-21 added 431 chunks (281,795).
- Search (`parlimen/search.py`): BM25 + dense + RRF + rerank, `mode` bm25 | dense | hybrid |
  full for the eval arms. Filters: kind, act, lang, date range (sittings; reprint dates only
  with kind=law), parliament, chamber, speaker, party, topic. A speaker or party filter skips
  speakers under 20 tokens in a chunk. Law passages add the sections they name (XREFS);
  `debates_for_act` lists an Act's bill debates.
- Ingest (`python -m parlimen.ingest [--dates ...] [--no-refresh] [--dry-run]`): a sitting not in
  `data/hansard-report.csv` is fetched, parsed and appended; every extract whose sitting
  `index.db` lacks is enriched (Messages API), commitment-checked, bill-linked, chunked, appended
  and embedded. A stopped run resumes.
- Tests: `tests/test_chunk_index.py`, `tests/test_search.py`, `tests/test_ingest.py`,
  `tests/test_eval.py`, `tests/test_answer.py`.
- The venv has sentence-transformers 6.2, transformers 5.20, accelerate; torch 2.14.1+cu130 comes
  from the user site through `.venv\Lib\site-packages\zz-user-torch.pth` (uv installs a CPU torch
  with sentence-transformers: uninstall it).
- Embed: measured rate on this GPU 222 s per 20,000 law rows, about 300-364 s per 20,000 debate
  rows (log `data/embed.log`). A re-run resumes at the first row with no vector; stop it by
  ending the inner `parlimen.index embed` process, so `gpu_run.py` restarts Forge and releases
  the lease. Launch (swap `embed` for `rebuild` and the log name for a rebuild):
  `powershell -NoProfile -File D:\Projects\personal\forge-tools\launch-hidden.ps1 -Dir D:\Projects\work\parlimen-search -Command "C:\Python314\python.exe -u tools\gpu_run.py --label parlimen-embed --minutes 90 -- .venv\Scripts\python.exe -u -m parlimen.index embed --variant h hn" -Log D:\Projects\work\parlimen-search\data\embed.log`
- Rebuild after a parser or chunk fix: `python -m parlimen.index rebuild --variant h hn` under
  the GPU lease (log `data/rebuild.log`). It moves the old build to `data/index/prev/`, builds
  afresh, keeps the vector of every chunk whose indexed text is unchanged and embeds the rest;
  a stopped rebuild resumes. The last rebuild (measured 2026-10-23) embedded 2,600 changed
  chunks for "h" in 50 s; "hn" was new, so it embedded all debate rows (5,057 s).
- Exit checks: `tools/check_phase4.py` all pass (log `data/check-phase4.log`): the bills of Acts
  265, 574 and 333, searched by name over the debates, return their bill debates; a section's
  heading inside Acts 265, 136 and 574 brings the sections it names. Ingest of DR and KK
  2026-10-21 (log `data/ingest-2026-10-21.log`): 421 speeches, 62 extracts enriched, [amount removed].

## Phase 5: the eval: done

The owner closed phase 5 on 2026-10-23 with five of six targets met, accepting Hansard recall
under target. The results table and their causes are in ROADMAP Phase 5. October spend logged
(measured 2026-10-23): [amount removed] in `data/api-usage.jsonl`.

The chosen setup (`parlimen/config.py`, `parlimen/answer.py`):
- Search: BM25 + Qwen3-Embedding-0.6B vectors on "h" (header + text; the notes lower recall
  under the reranker) + RRF, then Haiku 5.5 reranks the top 20 fused hits through the Messages
  API (`parlimen/llm_rerank.py`: one call, thinking off, effort low, JSON schema output; a failed
  call keeps the fused order). `config.RERANKER = "haiku"`, `RERANK_POOL = 20`;
  `config.LOCAL_RERANKER` is the Qwen3 size the local arms use. The local reranker takes about
  29 s a search on 2 CPU threads, so it cannot serve the CPU container.
- Answers: Haiku 5.5 at effort high (`answer.EFFORT`), with two prompt rules (answer only what is
  asked; write only claims a cited sentence states). Each debate quote carries its speaker's
  label (`answer.speaker_at`), each source carries the passage header (`Source.context`), and
  `answer.keep_cited` drops every sentence no citation reaches (it keeps lead-ins ending in ":",
  text with no letters, the lawyer referral and an answer with no citation at all;
  `Answer.dropped` holds what it took out).

Measured 2026-10-23 on the chosen setup:
- Retrieval (`results/eval-2026-10-23.md`, runs `data/eval/runs/`, logs `data/eval-run.log`,
  `data/eval-run-haiku.log`): law recall@10 0.907, Hansard 0.727, filters 0.720, language gap 0
  points; CPU search median 1,758 ms, 95th percentile 2,834 ms (embedder not held to 2 threads);
  about [amount removed] a search.
- Answers (`results/answers-2026-10-23-effort-high.md`, rows `data/eval/answers-effort-high.json`,
  log `data/judge-full-effort-high.log`): 77% correct, 82% with every claim backed; 9.9 s and
  [amount removed] an answer. The medium-effort run with BM25 alongside is
  `results/answers-2026-10-23.md` (rows `data/eval/answers.json`); the runs before the drop and
  before the prompt rules are `data/eval/answers-prompt-fix.json` and
  `data/eval/answers-before-fix.json`.

The tools:
- `parlimen/evalset.py` (Sonnet 5.5 writes questions from random chunks): law 150, debate 150,
  pairs 50, filters 25. `data/eval/hand.json`: 30 hand-written questions with reference answers
  (10 student, 10 journalist, 10 business owner; 10 in Malay), checked by Claude.
- `parlimen/evaluate.py run [--only NAME] [--device cpu]` scores the arms (recall@k, MRR@10,
  nDCG@10, language gap, stage medians); `latency [--reranker haiku|local]` times one setup on a
  2-thread CPU.
- `parlimen/judge.py [--arms ...] [--ids ...] [--answer-effort E]`: Haiku answers, Opus 5.5
  grades each answer blind, twice.

Open, for later: Hansard recall. Most misses are questions that name no date, where the top hits
are the same topic in another sitting.

## Phase 6: the pages and the MCP server: built, exit check passes

Scope and exit are in ROADMAP Phase 6.

## Phase 7: launch plan confirmed, owner's refinement passes next

The owner confirmed the plan in ROADMAP Phase 7 on its review page; the data stays on D:.
Owed: the owner's refinement notes on the local site; the host (step 3); the systemd timers of
step 4 (nightly ingest, rebuild and restart; weekly `drafts recheck`) and the Redis answer cache.
The owner chose Redis with systemd timers and no Celery, and a nightly restart over a swap with no
downtime (ROADMAP Phase 7 steps 2 and 4). Nothing goes public until the owner gives the word
(CLAUDE.md rules 1 and 8).

Open: each question is answered alone, with no memory of the previous one.

- Draft flag (`parlimen/drafts.py`): `python -m parlimen.drafts scan` reads page 1 of every cached
  sitting PDF for "Naskhah belum disemak" into `data/drafts.csv`; an ingest adds each new
  sitting's row. Measured 2026-11-26: 54 of 1,036 sittings are drafts, all Dewan Rakyat, from DR
  2019-11-06 (still a draft on the site) to DR 2026-10-22. The Special Chamber's PDFs never print
  the line, so they carry no flag. Sitting, debate and sitting-list pages and the ask page's
  sources show the mark.
- Re-check: `python -m parlimen.drafts recheck [--all] [--dry-run]` fetches each draft PDF of the
  last 365 days again; changed bytes replace the cache and the sitting is processed again
  (parse, rows put in place, old records dropped, chunks retired with `index.retire`, then
  `ingest.index_pending` enriches, checks, chunks and embeds). Retired rows keep their ids and
  vectors and leave search; a rebuild drops them. Rebuild `site.db` and restart the site after
  it. Not run on the real data yet.
- Limits (`parlimen/web/limits.py`): 20 questions per visitor an hour and [amount removed] a day of Claude
  spend (rerank plus answer), in Redis at `PARLIMEN_REDIS_URL`, else an in-process fakeredis.
  Past the budget the ask page shows the fused passages with no rerank and no answer. While the
  index loads after a restart, a question gets HTTP 503 and "ask again in a minute". Each
  question that runs goes to `data/questions.jsonl` with no IP address. The About page says
  what is stored.
- Search engines: `/robots.txt`, `/sitemap.xml` (an index of pages, law, MPs, bills, topics and
  one sitemap per year of sittings), page descriptions, Open Graph tags with
  `static/og.png`; the correction form and the 404 page are noindex. Absolute URLs come from
  `PARLIMEN_SITE_URL`.
- Sepang: one MP, "Raj Munni Sabu @ Aiman Athirah" in the 2022 results; `records.RENAMED` merges
  her two name keys under the name she uses now.

- Page database: `python -m parlimen.records build|stats` writes `data/site.db` (about 620 MB)
  from the corpus and enrichment files. Stop the site first: Windows refuses to replace an open
  file. Last build (measured 2026-11-26, 73 s): 30,091 extracts, 361,676 speeches, 31,767
  question-answer pairs, 18,523 commitments, 341 MPs, 54 draft sittings. Rebuild after
  every ingest, so the pages show the new sittings.
- Site: `python -m parlimen.web [--port 8780]` (`parlimen/web/`). Record pages need no model and
  load in 0.02 to 0.6 s. At start the server loads the index, the vectors and the embedder on
  the CPU in the background (149 to 162 s measured 2026-10-25, while other jobs used the D:
  hard disk); record pages serve during that. The embedder stays on the CPU (about 90 ms a
  question, 3.4 GB RAM for the process), so the site holds no GPU; `PARLIMEN_SITE_DEVICE=cuda`
  puts it on the GPU, unloaded after 10 idle minutes. A warm question takes 6.8 to 12.7 s and
  about [amount removed] (Haiku rerank plus answer). Corrections go to
  `data/corrections.jsonl`.
- MCP server: `python -m parlimen.mcp_server` (stdio), registered in `.mcp.json`. The read tools
  answer in under 1 s; the search tools load the searcher on the first call (minutes on the
  cold D: disk) and unload the embedder after `PARLIMEN_IDLE_MINUTES` (10).
- Digest: `python -m parlimen.digest --sector energy --from 2026-10-19 --to 2026-10-23` writes
  `data/digests/energy-2026-10-19-2026-10-23.html` and `.json` (raw answer, kept items,
  dropped ids). One Haiku 5.5 call; ids not in the week's records are dropped in code, and
  every quote on the page comes from the record. Sectors are in `digest.SECTORS`.
- Exit check: `python tools/check_phase6.py [--lang ms]` against the running site, 4 of 4 pass
  in both languages (measured 2026-10-25); shots in `data/shots/check-*.png`.
  `tools/site_shots.py [--ask "..."] [--lang ms]` shoots every page at desktop and phone width
  with load times and any overflow.
- Ingest of DR and KK 2026-10-22 (log `data/ingest-2026-10-22.log`): 444 speeches, 58 extracts
  enriched, [amount removed]. October spend logged (measured 2026-10-25): [amount removed].
- Tests: `tests/test_records.py`, `tests/test_web.py`, `tests/test_mcp_server.py`,
  `tests/test_digest.py`, `tests/test_drafts.py`; suite 118 pass.

Open:
- The D: hard disk holds the venv, the model and the index, so every cold start is slow. Moving
  `data/index` and the HF cache to the NVMe C: drive would cut it; that is the owner's call.

## Site redesign (Phase 7 step 1): design directions in progress

The owner finds the site far too plain and approved every richer item (2026-11-26): a design
system (Tailwind standalone CLI), the answer streamed word by word, htmx filters and paging,
richer record pages (MP activity over time, bill timeline, topic trend by year), and a better
Ask page (suggested questions, filter chips, sources beside the answer). The stack stays
FastAPI with server-rendered Jinja; no framework change. A small React island only if the Ask
page later grows into an app.

- Brief: `docs/design/BRIEF.md`. Real content: `docs/design/data.json`, built by
  `python docs/design/build_data.py [--no-ask]` (MP Dzulkefly Ahmad, debate DR-2026-10-22-017
  from a draft sitting, bill KERJA (PINDAAN) 2021, one real answer about targeted diesel
  subsidies: [amount removed], 93 s on the cold D: disk).
- Three directions, one folder each under `docs/design/<direction>/` (home, MP and debate
  prototypes, shots at 1440 and 390 px, NOTES.md), built by three subagents from the brief:
  `gazette` (editorial broadsheet, chamber green), `console` (dark analyst instrument, Plex,
  amber and teal), `civic` (warm public-service app, navy and yellow, songket motif). Shots come
  from `python docs/design/shoot.py <direction> [--dark]`.
- Generators: `gazette/gen.py` and `civic/build.py` wrote those pages from `data.json`; the
  console pages have no generator, so edit their HTML directly.
- Showcase: https://claude.ai/artifact/KWLv7EmBCyYXLt1XbJK4d8, source `docs/design/showcase/`
  (index.html plus WebP shots; the three prototype folders publish beside it and run live in
  the page). The owner picks a design in chat. A Design canvas
  artifact made first (https://claude.ai/artifact/XbvPXQXhyvKmcWg3SjxjX1) is empty and unused:
  delete it only if the owner asks.
- The owner picked Civic with three Console features (citation hover lights its source, MP
  month-by-year grid, debate speaker map with J/K). Plan: no Tailwind (Civic is token CSS), fonts
  self-hosted, htmx for list filters and paging. Backend built and tested: `POST /api/ask/stream`
  (stage, text, done, error events; `answer.ask(on_text=)` streams; `Searcher.search(on_stage=)`),
  htmx partials (`results` block on `HX-Request`), `--replay docs/design/data.json` for no-spend
  design runs, new `Records` member and topic-trend queries, `config.SITE_NAME`. The template and
  CSS port to every page is done (all 17 templates, `ask.js`, `debate.js`, `shell.js`, vendored
  htmx 2.0.4, self-hosted Geist and Literata with licences; `tools/site_shots.py --dark --full`;
  125 tests pass). Owed: a polish round from shots (unread: questions, commitments, Act, topics,
  MPs list, bill page, Malay pages), "1 speeches" plural, the citation popover covering the
  answer on phone, dark heat-grid level 0 too faint, then restart the site on 8780 and ask one
  real question through the stream.
- Name: the owner wants a better name than parlimen-search. Shortlist page
  https://claude.ai/artifact/Pv5MVDAfWr2bwy8g1qK7YE (source `docs/design/names/`); my pick is
  Tanya Dewan. The rename is `config.SITE_NAME` plus docs, OG image and the MCP description.
- Next: the owner picks a name; finish the port, then build the chosen
  design into `parlimen/web/` (templates, Tailwind build, htmx, streaming answer endpoint).

## Phase 3 model: Haiku 5.5 with adaptive thinking

- Chosen from `tools/bench_enrich.py` (results `data/bench/enrich/`, table in ROADMAP Phase 3).
  The owner's rule: Haiku unless it falls short; never Sonnet only because it costs more.
- Two flagged defects were checked against the source and hold up.
- The review page shows the choice and the [amount removed] cost.

The Special Chamber is in `data/sittings.csv` (`chamber` column: DR or KK; 539 and 494 days),
measured and costed in `docs/sources.md`.

## Environment

- `.venv` (Python 3.14, uv), packages pinned in `requirements.txt`: httpx, pdfplumber,
  pypdfium2, anthropic, sentence-transformers, fastapi, uvicorn, jinja2, mcp, pytest,
  playwright (drives the installed Chrome with `channel="chrome"`; no bundled browser needed).
  torch comes from the user site (see Phase 4).
- Tesseract 5.4 at `C:\Program Files\Tesseract-OCR`; poppler's `pdftotext` from Git's mingw64.
- API key: `~/.claude/anthropic-api-key.txt`; usage log `data/api-usage.jsonl`.
