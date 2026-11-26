# parlimen-search: roadmap

Ask Malaysian law and Malaysia's Parliament in plain Malay or English. One search covers two
sources:

- **The law:** what an Act says, cited to the Act and section.
- **The debate:** what MPs said in the Dewan Rakyat, cited to the sitting, the date, the speaker
  and the page of the Hansard (the official record of debates).

The two are linked: an Act points to the debates on its bill, so "why was this section added?"
finds the minister's speech that explained it. AI enrichment turns the debates into structured
records: each oral question joined to the minister's answer, topic and entity tags, a short
summary per speech, and a tracker of ministers' commitments.

It reuses the hybrid RAG pipeline of novel-rag (`D:\Projects\personal\novel-rag`): keyword and
vector search, fusion, a reranker, cited answers and the eval method.

## Goals

1. **Useful:** a law student, journalist, researcher or small business finds the rule and the
   reason for it in one place, in either language, with sources they can check.
2. **Career:** the strongest public proof for AI product engineer roles in Malaysia and Singapore:
   legal text structure, two languages, structured extraction at corpus scale, date and speaker
   filters, and published eval numbers.
3. **Visible:** a public tool that local press, civic tech groups and universities can point to.
4. **Income later:** the free tool is the shop window for a paid monitoring product (Money path).
   Release 1 is portfolio work; the paid tier is built only after its demand gate passes.

Targets for release 1, fixed before the first measurement:

| Measure | Target |
|---|---|
| Recall@10, law questions (answer section in the top 10) | 0.85 or more |
| Recall@10, Hansard questions (answer speech in the top 10) | 0.80 or more |
| Language gap: the same question asked in Malay and in English | under 5 points of recall@10 |
| Answer correctness on hand-written questions (blind judge) | 65 % or more |
| Answers whose every claim is backed by a quoted source | 80 % or more |
| Speeches whose speaker resolves to an MP record | 95 % or more |
| Oral questions correctly joined to their answer (hand-checked sample of 100) | 95 % or more |
| Commitments whose quote matches the Hansard text exactly | 100 % (checked by code) |
| Commitments that a human agrees are real commitments (sample of 100) | 85 % or more |
| Search latency on the public container, 95th percentile | under 3 seconds |

## Who it is for

**Free users:** law and politics students, journalists, NGO and policy researchers (Sinar Project's
audience), small business owners with a compliance question, and voters who want to know what
their MP said.

**Paying buyers, later:** public affairs and government relations consultancies (Vriens & Partners,
BowerGroupAsia and local firms), chambers of commerce (AmCham Malaysia, EuroCham, the bilateral
business councils), corporate affairs teams of large companies, embassies, and newsrooms. They pay
abroad for alerts and digests on their topics (Money path).

## What exists already

Searched 2026-10-18 and 2026-10-22 (GitHub, web).

- **Parliament's Hansard Digital** (GovTech Malaysia, handed over 9 June 2026): keyword search, a
  word cloud and filters by MP and chamber, 1959 to 2026, Malay and English. No AI answers, no
  links to the Acts, no API or export found. The ministry says it does not replace the official
  Hansard. This is the main rival for plain lookup; parlimen-search wins on meaning-based search,
  cited answers, the Act links, structured records and alerts.
- **Singapore's Pair Search** (GovTech Open Government Products, pilot since 2024): semantic search
  over Hansard, judgments and Acts, with AI trend summaries. It proves the demand, and it shows that
  Malaysia's government could add AI search too. The paid value therefore sits in monitoring and
  structured history, not in search alone.
- **Sinar Project:** an archive of written parliamentary replies and Billwatcher, a bill tracker.
  Partners for data and launch, not rivals.
- **Small AI demos:** ParlimenGPT (a Microsoft demo on Hansard) and Dewan AI (a Product Hunt
  listing, maker and price unknown). No published eval, no structured records.
- **Datasets:** `malaysia-ai/malaysia-hansard` on Hugging Face (about 157,000 rows of Hansard text,
  no licence or date range stated). Used only as a cross-check for the parser, never as the source.
- **Law:** paid research tools for lawyers (Lexis+ AI with Protégé Malaysia, JusType), narrow
  assistants (ChatAboutLaw, AskAILA), two MCP servers that fetch Act text (`my-eli-mcp`,
  `@ansvar/malaysian-law-mcp`) and small RAG repositories with 0 stars.

**The gap:** no tool searches the debates by meaning, joins questions to answers, tracks
ministers' commitments, links the debates to the law, works across both languages, or publishes how
well it works.

## Legal and safety basis

- **Copyright.** Copyright Act 1987, section 3, Malay text (the authoritative one; AGC reprint as at
  30 June 2022): "literary work" "tidak termasuk teks rasmi Kerajaan atau badan berkanun, yang
  bersifat perundangan atau peraturan, atau keputusan kehakiman, atau ucapan politik dan debat
  politik, atau ucapan yang diberikan dalam perjalanan prosiding undang-undang, dan terjemahan
  rasminya". Acts and Hansard debates therefore carry no copyright. Parliament's footer says
  "Copyright Reserved"; phase 0 records why section 3 still applies and the owner signs it off.
- **Defamation.** Verbatim Hansard text is the public record. An AI summary is not, and a summary
  that puts words in an MP's mouth is the largest legal risk in the project. The rules:
  - the parser, never the model, decides who spoke;
  - every summary is shown beside the verbatim text and is labelled as AI-written;
  - every commitment carries a verbatim quote that code checks against the Hansard text, and a
    record whose quote does not match is dropped;
  - every record links the official PDF page;
  - a correction link on every record, with corrections handled within 7 days.
- **Neutrality and sensitive topics.** No scoring of MPs, no stance or sentiment labels on
  people, no rankings. Records describe what was said, never whether it was right. Speech on race,
  religion and royalty appears only as the verbatim record with its citation; summaries of it stay
  factual.
- **Not legal advice.** Every law answer cites its sources, shows the Act's reprint date and the
  not-legal-advice line, and refuses advice on a reader's own case.
- **Personal data.** Release 1 stores no accounts. The paid tier stores customer emails and saved
  topics, which brings in Malaysia's Personal Data Protection Act; its privacy notice is part of
  that phase.
- **Polite downloads.** Cached once, rate-limited, identified by a user agent, within each site's
  `robots.txt` and terms.

## Product

### What the reader can do in release 1

1. **Ask the law.** "Can my employer cut my salary?" gives the relevant sections of the Employment
   Act 1955, quoted and cited.
2. **Ask the debate.** "What did MPs say about the Online Safety Bill?" gives speeches with date,
   speaker, party and page, each with its summary beside the verbatim text.
3. **Find the answer to a question asked in Parliament.** Oral questions and the ministers' answers
   appear as one record: who asked, who answered, the figures given.
4. **Track commitments.** A page of ministers' promises with a date or a number ("by 2027",
   "RM2 billion"), each with its quote, minister, sitting and topic. Filters by ministry and year.
5. **Follow the link.** From a section, open the debates on the bill that made or changed it.
6. **Browse by MP, bill and topic.** One page per MP (seat, party over time, speeches, questions
   asked), one per bill (its debates and the Act it became), one per topic. These pages are
   static, so search engines index them and readers arrive from Google.
7. **Filter.** By date range, Parliament, speaker, party, ministry, topic and Act.
8. **Ask in either language.** Malay or English, with sources in both; the page shows which text is
   the authoritative one.
9. **How it found this.** The novel-rag visualiser panel, adapted to sections and speeches.
10. **Use it from an AI assistant.** An MCP server for Claude Desktop and Claude Code.

### Release 1 scope

- **Laws:** every principal Act on Laws of Malaysia Online (`lom.agc.gov.my`), English and Malay,
  at the reprint date the portal shows: 887 Acts (753 in force, 134 repealed or superseded), 840
  English and 749 Malay PDFs.
- **Debates:** every Dewan Rakyat sitting of the 14th and 15th Parliaments (July 2018 onwards):
  539 sitting days to 2026-10-20 (262 and 277), about 100 born-digital pages each, plus 494 short
  sittings of the Special Chamber (Dewan Khas). The span covers three changes of government, so
  party membership is stored with dates.
- **Updates:** new sittings are added within 2 days of their PDF going up. Parliament posts a draft
  ("BELUM DISEMAK") the day after most sittings and replaces it with a revised version months
  later; the ingest job detects a changed file and re-processes that sitting, and every record
  shows whether its text is a draft.
- **Later:** older Parliaments (text layer confirmed on a 2000 sample; scans before that need OCR),
  Dewan Negara, amendment Acts and point-in-time text, subsidiary legislation, state assemblies,
  attendance.

## Money path

Two tracks, in this order. Neither is built before its gate passes. Escape Velocity runs one paid
avenue at a time; this one opens after release 1 launches.

### Track A: topic alerts and a weekly digest (the main bet)

- **Offer:** a customer saves topics, Acts, bills, ministries or companies. When Parliament
  mentions them, they get an email alert with the quote and link, and a weekly digest written by
  Claude from the week's records.
- **Who pays:** the buyers listed under Who it is for. Abroad, Quorum is about [amount removed] a year
  (a Vendr estimate) and Politico Pro [amount removed]; PolicyMogul has a free tier and quoted
  prices. No Malaysian vendor sells a Hansard alert product.
- **Price hypothesis:** [amount removed] a month per organisation. A guess with no Malaysian price
  evidence; the pilot tests it.
- **Size of the prize:** five customers at [amount removed] is [amount removed] a month, about 5 times the
  [amount removed]-a-month first target of Escape Velocity.
- **Likelihood:** moderate to low. The buyers exist and the gap is real, but the market is small
  (an estimated 50 to 150 organisations), B2B sales need trust and relationships, the alerts must
  arrive fast and reliably, and the government could add alerts to Hansard Digital.
- **Gate:** three organisations agree to a paid pilot (or sign a letter of intent) after seeing the
  public tool. Until then, no accounts, billing or alert sending are built.

### Track B: commercial data licence and API (a by-product)

- **Offer:** free for non-commercial use; a paid licence for companies that use the structured
  records (question-answer pairs, commitments, tags, MP records) or the API. The TheyWorkForYou
  model.
- **Likelihood:** low as income. TheyWorkForYou's commercial API tops out at about [amount removed] a month per
  buyer; Malay AI builders already scrape Hansard free. It costs little to offer once the data
  exists, so it is offered, not pursued.
- **Gate:** one paying request arrives unprompted.

### What release 1 builds now so the paid tier is cheap later

- Stable IDs and permanent links for every sitting, speech, question-answer pair, commitment, MP,
  bill and Act section.
- An incremental ingest job: a new sitting goes through download, parse, enrichment and indexing
  on its own.
- A saved search stored as a query object (topics, entities, filters), even though only the page
  uses it in release 1.
- A fixed tag list (topics, ministries, entity types) that alerts can match against.
- Usage logs: which topics and pages people search, which shows what buyers care about.

### Validation steps (the owner's work, alongside the build)

1. During phases 2 to 5, list 30 named prospects with a contact person (consultancies, chambers,
   corporate affairs teams, newsrooms).
2. At launch, send each one the public tool with a sample weekly digest on their sector.
3. Hold 10 conversations. Ask what they track now, how, at what cost, and what they would pay.
4. Go or no-go for the paid pilot from the gate above.

## Technical plan

| Part | Approach |
|---|---|
| Act download | `parlimen/acts.py`: the installed Chrome reads the portal's list of updated Acts as a visitor sees it (never decrypting its payload), then fetches each English and Malay PDF once, keyed by Act, language and "As At" date |
| Act parsing | PDF to text, then structure: Part, section, subsection, definitions, schedules. Pair the English and Malay versions by section number |
| Hansard download | One PDF per sitting day, its path read from Parliament's archive listing (`parlimen/sittings.py`; file names are irregular, so the path is never built from the date) |
| Hansard parsing | Split into speeches: speaker name and role, time, page; split out the oral questions section ("PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"); detect the language of each paragraph (debates switch between Malay and English) |
| MP data | Members per Parliament with seat, and party membership with start and end dates (party switches and by-elections), from Wikipedia, Sinar Project's GE14 and GE15 data and Parliament's member pages |
| Enrichment | Claude Batch API, one request per speech or question-answer pair, structured output against a fixed schema: summary in English and Malay, topic and entity tags, question-answer join, commitments with a verbatim quote. The model (Haiku 5.5 or Sonnet 5.5) is chosen by the phase 3 pilot |
| Linking | Parliament's bills list gives each bill's number ("D.R.25/2026"), reading dates, minister and passing date, so a bill links to the exact sittings that debated it; the bill links to the Act it became; section cross-references ("subsection 13(2)") resolved inside the law |
| Chunks | One law chunk per section (long sections split at subsections, with the Act and section in the header); one debate chunk per speech or speech part, with sitting, speaker, date and tags in the header |
| Search | novel-rag's pipeline: BM25, Qwen3-Embedding-0.6B (multilingual, Malay measured in phase 5), RRF, neighbour expansion. The reranker is Haiku 5.5 through the Messages API, reading the top 20 fused hits (`parlimen/llm_rerank.py`): Qwen3-Reranker-0.6B takes about 29 s a search on a 2-thread CPU (phase 5). Filters replace the spoiler limit |
| Answers | Claude with `search_result` citations, as novel-rag's chat. Haiku 5.5 for the public demo, a better model locally |
| Front ends | The chat page, static MP, bill and topic pages, the commitments page, an MCP server, a CLI |
| Background jobs | Redis for the rate limit, the answer budget and the answer cache; systemd timers run the nightly ingest and the weekly draft re-check (phase 7 step 4) |

Stack: Python 3.12+, FastAPI, SQLite FTS5, NumPy, PyTorch for the search models, Redis for the counters, systemd timers for the background jobs. Hosting: a CPU
VPS (phase 7), since the daily ingest writes to the data the site reads. Licence: MIT for the code; the
structured records under a non-commercial licence with a paid commercial option (Track B).

### Data model

| Record | Key fields |
|---|---|
| Act, Section | Act number, title (EN, MS), reprint date, section number, text (EN, MS), cross-references |
| Bill | Bill number, title, readings with sitting dates, the Act it became |
| Sitting | Date, Parliament, meeting, chamber, PDF URL, page count, parse status |
| Speech | Sitting, order, speaker (raw text and resolved MP), role, page range, language, verbatim text, summary (EN, MS), tags |
| Member, Party membership | Name forms, seat, Parliament; party with start and end dates |
| Question-answer pair | Question number, asking MP, answering minister, ministry, question text, answer text, figures |
| Commitment | Minister, ministry, sitting, verbatim quote, what is promised, deadline or amount, topic |
| Tag | Fixed list: topics, ministries, entity types (Act, bill, company, place, agency) |
| Saved search | Query text, tags, entities, filters (used by alerts later) |

## Phases

### Phase 0: legal and source check

- [x] Record the section 3 finding and its source in `docs/sources.md` for the owner's sign-off.
- [x] Read the terms of the portal, the repository and Hansard Digital, and find Hansard Digital's
  address, API and export, if any.
- [x] Measure publishing: how many days after a sitting its PDF appears, and whether a draft version is
  replaced by a final one later.
- [x] Confirm the sitting-day count against Parliament's sitting calendar. Resolved differently: the
  count comes from Parliament's own archive listing (539 days), which is the calendar's record.
- [x] Count tokens on 5 sample sitting days with the token-counting API; set the enrichment cost from
  the count.
- [x] The owner signs off the copyright reading.
- [x] The owner decides the source of the Act texts: the portal itself, read in the installed Chrome
  (`docs/sources.md`, Laws of Malaysia Online).
- **Exit:** a written go or no-go for a public demo, the corpus size, and the cost estimate.

### Phase 1: the law corpus

- [x] Downloader with cache and rate limit (`parlimen/acts.py`).
- [x] Download pilot: 10 Acts plus three unusual rows (26, 265, 762), checked with
  `tools/check_acts.py`; every file holds the right Act, language and date.
- [x] Full download: 1,586 of the 1,589 PDFs. The portal's file server fails on three (Act 781
  Malay, Acts 175 and 150 English), and the other language of each is cached.
- [x] Parser to sections (`parlimen/act_text.py`); English and Malay pairing by section number;
  "no Malay text" covers, notices and wrong-language files reported by kind.
- [x] Parser pilot: one section from each of 10 Acts (26, 181, 265, 313, 337, 588, 711, 828, 862,
  880) checked against the page, four of them against the rendered page image.
- [x] OCR for the scanned PDFs of in-force Acts (`parlimen/act_ocr.py`): Claude Haiku reads each
  page, Tesseract checks it, and Claude Sonnet re-reads the hard pages. 52 files, 1,901 of 1,964
  listed sections found. Act 175 is out: Act 815 repealed it.
- **Exit:** every principal Act parsed, with a report of sections that failed to parse; a sample of
  50 sections matches the PDF word for word. Measured 2026-10-22: 66,026 of 66,307 listed sections
  found (`data/act-parse-report.csv`); six samples of 50 text-layer sections
  (`tools/check_act_text.py`, seeds 1 to 6) match poppler's text word for word; 748 of the 753
  in-force Acts have text, 665 of them in both languages.

### Phase 2: the debate corpus

- [x] Downloader and speech splitter (`parlimen/hansard.py`); speaker, role, time and page per
  speech; each oral question's number carried by its answer and follow-up speeches.
- [x] Members per Parliament from the attendance lists (`data/members.csv`), with seat, party and
  Senators; a speaker labelled by name alone takes the seat from the sitting's list or the
  register. Members' dates and party changes are owed.
- [x] Pilot: 5 sitting days from each Parliament and chamber (20 days), checked by hand against
  the PDFs. 6,004 of 6,009 named speeches resolve; 0 date mismatches; 0 failures.
- [x] **Exit:** all 1,033 sitting days (539 Dewan Rakyat, 494 Special Chamber) parsed, with a
  failure report that includes dates that differ between the listing and the PDF; 95 % or more
  of speeches resolve to an MP. Measured 2026-10-22: 359,904 speeches; 319,312 of 319,484 named
  speeches (99.95%) resolve; 0 failures; 1 sitting with no PDF; 10 date-line typos.

### Phase 3: enrichment

- Write the enrichment schema and prompt; structured output; every call logs its usage.
- Model: Haiku 5.5 with adaptive thinking. The quick benchmark (`tools/bench_enrich.py`, 24
  extracts, blind Opus 5.5 audit, measured 2026-10-22) found it as good as Sonnet 5.5 at about a
  tenth of the cost; Haiku without thinking fell short:

  | Arm | Publishable as is | Major defects | Quotes word for word | Full corpus, Batch API |
  |---|---|---|---|---|
  | Haiku 5.5, no thinking | 15 of 24 | 16 | 17 of 24 | about [amount removed] |
  | Haiku 5.5, adaptive thinking | 23 of 24 | 1 | 22 of 22 | about [amount removed] |
  | Sonnet 5.5, no thinking | 22 of 24 | 3 | 26 of 26 | about [amount removed] |

- Pilot: 5 parsed sitting days through Haiku with thinking, the same blind audit, and 20 records
  read by the owner. Speech ids in the schema become an enum of the request's ids, since every
  arm sometimes wrote "S5, S7" or a speaker name in place of one id.
- [x] Pilot (`parlimen/enrich.py pilot`, 5 days, 212 extracts): blind audit 31 of 40
  publishable with the benchmark prompt; a stricter summary instruction (`tools/ab_enrich.py`)
  raised it to 33 of 40 and halved major defects (16 to 8). Claude read 20 records in place of
  the owner: 0 major defects.
- [x] Commitment checks in code: the quote must match the Hansard text; a record without a match
  is dropped and counted.
- [x] Full run on the Batch API (measured 2026-10-22): 29,971 records, 31,668 question-answer
  pairs, 19,866 commitments kept and 89 dropped; [amount removed] with the pilots.
- [x] Sonnet 5.5 checks every kept commitment against its speech (`parlimen/commit_check.py`,
  measured 2026-10-22): 1,397 dropped as not a real promise, 2,519 paraphrases corrected,
  18,469 kept; [amount removed]. On the exit sample it agrees with the hand check on 93 of 100.
- [x] **Exit:** every speech enriched; the question-answer and commitment targets measured on
  hand-checked samples. Measured 2026-10-22 (`tools/exit_samples.py`, checked by Claude in
  place of the owner): 99 of 100 oral questions joined to their answer (target 95%); 92 of 100
  commitments real (target 85%).

### Phase 4: links and index

- [x] Bill-to-Act links (`parlimen/links.py`): 298 of 387 bill headings linked; 46 supply
  bills and 19 non-Acts have no Act by design; 24 unlinked.
- [x] Section cross-references, chunks and index (`parlimen/chunk.py`, `parlimen/index.py`).
- [x] Party on the sitting's date for every MP (`parlimen/parties.py`): 99.27% of speeches with
  a seat get one.
- [x] Search with filters, cross-reference passages and linked debates (`parlimen/search.py`).
- [x] The incremental ingest job (`python -m parlimen.ingest`): one new sitting goes from
  download to index in one command.
- [x] Embeds under the GPU lease: 281,364 chunks in two vector sets (header + text; header +
  note + text). `python -m parlimen.index rebuild` re-embeds only the chunks a fix changes.
- [x] Exit checks (`tools/check_phase4.py`, all pass): the Employment Act, Penal Code and Road
  Transport Act bills, searched by name, return their bill debates; a section's heading searched
  inside its Act brings the sections it names. DR and KK 2026-10-21 ingested in one command
  (421 speeches, 62 extracts, [amount removed]).
- **Exit:** a search for a known Act returns its debates; a search inside an Act follows its
  cross-references; a new sitting ingests without manual steps.

### Phase 5: the eval

- [x] **Generated questions** (`parlimen/evalset.py`): 150 law and 150 debate questions from
  random chunks, each with its answer section or speech; half in Malay, half in English.
- [x] **Language pairs:** 50 questions written in both languages; the gap between them is the
  multilingual score.
- [x] **Hand-written questions** (`data/eval/hand.json`): 30 that a student, journalist or business
  owner would ask, with reference answers, checked by Claude in the owner's place.
- [x] **Filter questions:** 25 that need a date, speaker, party or Parliament filter.
- [x] Arms (`parlimen/evaluate.py`): keyword only, vectors, hybrid, hybrid with the local reranker
  (pools 50, 20, 10), with enrichment notes in the chunk, and hybrid with Haiku 5.5 reranking
  (pools 20, 50). The Malay-specific embedder arm was not needed: the language gap is 0 points.
- [x] Latency on a 2-thread CPU (`evaluate latency`) and answer quality graded blind by Opus 5.5
  (`parlimen/judge.py`).
- [x] **Exit:** the targets table, measured and written to `results/`. Five of six targets pass;
  the owner accepted Hansard recall under target and closed the phase (2026-10-23).

Results (measured 2026-10-23; `results/eval-2026-10-23.md`, `results/answers-2026-10-23.md`,
`results/answers-2026-10-23-effort-high.md`).
The chosen setup is hybrid search with Haiku 5.5 reranking the top 20 hits:

| Target | Result | |
|---|---|---|
| Law recall@10, 0.85 or more | 0.907 | pass |
| Hansard recall@10, 0.80 or more | 0.727 (best of any arm 0.760) | fail |
| Language gap under 5 points | 0 points | pass |
| Search latency, 95th percentile, under 3 s | 2.83 s on the CPU, embedder not held to 2 threads | narrow pass |
| Answers correct, 65% or more | 77% at answer effort high (medium: 72%; BM25 only: 54%) | pass |
| Every claim backed, 80% or more | 82% at answer effort high (medium: 78%; BM25 only: 87%) | pass |

- The enrichment notes in the chunk lower recall under the reranker, so the index searches
  header and text only. The local Qwen3 reranker takes about 29 s a search on 2 CPU threads.
- Hansard misses: most questions name no date, and the top hits are the same topic in another
  sitting.
- The answer prompt tells Haiku to answer only what is asked and to write only claims a cited
  sentence states; each debate quote carries its speaker's label, and the judge sees each cited
  passage's header. Code then drops every answer sentence no citation reaches
  (`answer.keep_cited`; 35 sentences in 22 of 30 reranked answers): that removes claims from the
  model's memory, and some correct summary lines with them (correct 78% before the drop, 72%
  after; backed 67% before, 78% after). The answers that stayed unbacked misstated a cited
  sentence (s. 32(2) read as "or" where the Act says "and"; a Deputy Speaker called a Deputy
  Minister) or led with the wrong Act, faults a code check cannot see.
- Haiku answers at effort high (`answer.EFFORT`): 77% correct and 82% backed, against 72% and
  78% at medium, for 9.9 s against 7.2 s per answer (search included) and [amount removed] against
  [amount removed]. Thirteen of 30 questions changed grade between the two runs, in both directions,
  so part of the gain is judge noise on a set of 30.

### Phase 6: the pages and the MCP server

- [x] The site (`parlimen/web/`, FastAPI and Jinja2, server-rendered, page data from
  `data/site.db` built by `parlimen/records.py`): the ask page with filters; Act pages with a
  section anchor each; sitting and debate pages with each speech verbatim beside the AI summary;
  question-answer cards; the commitments page; MP, bill and topic pages; links to the official
  PDF pages; the AI label, the correction link and the not-legal-advice line; Malay and English
  interface text. Each question is answered on its own, with no memory of earlier questions.
- [x] MCP server (`parlimen/mcp_server.py`, registered in `.mcp.json`): `search_law`,
  `search_debates`, `read_section`, `read_sitting`, `list_commitments`.
- [x] A sample weekly digest (`parlimen/digest.py`): energy, water and climate, 19 to 22 October
  2026, 7 items and 8 commitments to watch, [amount removed].
- [x] Exit check (`tools/check_phase6.py`, 4 of 4 pass in English and Malay): a reader clicks from
  the Acts search to a section, to its bill debate, from the questions page to a deputy finance
  minister's answer, and from the commitments page to the speech that holds the quote.
- **Exit:** a reader finds a section, its debate, a minister's answer and a commitment without the
  CLI.

### Phase 7: public demo and launch

Nothing in this phase goes public until the owner says so; the owner's refinement passes come
first. The owner confirmed the plan on the review page (`docs/launch-page.html`,
https://claude.ai/artifact/A54eghUEJ1ucrYFh81QvYz, db `verdicts`): the host, the [amount removed] daily
budget, the limit of 20 questions an hour, the ingest on the host, a launch at the first 2027
meeting, public code at launch, the working name until the trial, and the anonymous question log.

1. **Refinement passes (owner, then Claude).** The owner reads the local site and sends notes;
   Claude fixes them and reshoots the pages (`tools/site_shots.py`). The site's files stay on the
   D: hard disk (owner's choice), so each restart warms for about 2.5 minutes.
2. **Gaps before launch (Claude).**
   - ~~Draft flag: every sitting and record shows when its text is the unrevised draft ("BELUM
     DISEMAK"), read from the PDF.~~
   - ~~Revised sittings: the ingest re-checks draft sittings each week and re-processes one whose
     PDF changed (about [amount removed] a sitting).~~ Its weekly systemd timer is step 4.
   - ~~Rate limit per visitor (20 questions an hour) and a daily answer budget ([amount removed]), both counted
     in Redis (step 4). Past the budget, the ask page shows the found passages without a written
     answer, and says so.~~
   - ~~An anonymous question log (question, filters, cost; no IP address), for which topics people
     ask about. The About page states what is stored, including the optional contact on the
     correction form.~~
   - ~~`sitemap.xml`, `robots.txt`, page titles and descriptions, share previews, so MP, bill and
     topic pages reach search engines.~~
   - ~~The Sepang seat's two MP pages checked against the record.~~
   - The site reloads its data after an ingest: the nightly job restarts the site service as its
     last step (step 4). ~~While the index loads after a restart, the Ask page answers "still
     loading, ask again in a minute" (HTTP 503, Retry-After 60); record pages serve as usual.~~
     The owner chose a restart over a swap with no downtime: a swap holds two copies of the
     vectors (about 1.2 GB more) on an 8 GB host. Revisit only if the warm-up on the VPS is long.
3. **Host: a small VPS, 4 vCPU, 8 GB RAM (Hetzner CX33; CPX32 if the CX33 is sold out).** The site needs about 4 GB of data
   (only the "h" vectors), about 3.5 GB of RAM, and no GPU. A VPS at about [amount removed] a month
   (Hetzner, after its June 2026 price rise) keeps the warm process up all day. Cloud Run with one
   warm instance costs about [amount removed] a month idle; with none, every first visitor waits through a
   cold load, and the daily ingest would have to rebuild and redeploy the image, since a Cloud Run
container keeps no files. HTTPS through Caddy, the site and Redis as systemd services, the
   timers of step 4, a health check and an uptime monitor. A deploy pilot checks RAM, answer
   time, the warm-up time after a restart and that the host can reach parlimen.gov.my.
4. **Redis and systemd timers on the host.** The site runs as one uvicorn process, since each
   process loads the 3.5 GB index. The owner's choice: Redis for the counters and no task queue,
   since a daily job and a weekly job need a timer, not a queue.
   - Redis runs on the VPS, bound to localhost, with a memory limit, and the site reads it at
     `PARLIMEN_REDIS_URL`. It holds the rate limit and the daily budget (`parlimen/web/limits.py`,
     built), so both survive the nightly restart. Still to build: an answer cache keyed by the
     question and its filters, so a repeated question costs nothing.
   - A nightly timer during Parliament's meetings runs the ingest of step 5, then
     `python -m parlimen.records build`, then `systemctl restart` of the site. A later step runs
     only when the one before it succeeds, so a failed run leaves the site as it was. The ingest
     resumes where it stopped, so the next night's run finishes a failed one.
   - A weekly timer runs `python -m parlimen.drafts recheck`, then the same rebuild and restart
     when a sitting changed.
   - The jobs load Qwen3-Embedding-0.6B beside the site's 3.5 GB. The deploy pilot (step 3)
     measures peak RAM with the site, Redis and a job up. The two timers must not overlap.
   - Local development on Windows: the in-process `fakeredis` stands in when
     `PARLIMEN_REDIS_URL` is unset.
   - Phase 8 alert emails fit a timer after the nightly ingest. Add a task queue only if alerts
     must go out at once for each user. No alert code exists before the Track A gate (CLAUDE.md
     rule 10).
5. **Ingest on the host.** The nightly job of step 4 during Parliament's meetings: fetch new
   sittings, enrich them (about [amount removed] a sitting day, so about [amount removed] a 37-day meeting), embed on
   the CPU, rebuild the page database, restart the site. A failed run leaves the site as it was
   and logs why.
6. **Launch materials.** README with the eval results table and a GIF of the ask page; the
   public repository (code only; `data/` stays out); a write-up for the personal site, LinkedIn
   and dev.to on structured extraction at corpus scale.
7. **Launch and outreach (owner).** At the first Parliament meeting of 2027. The current meeting
   ends 8 December 2026; the 15th Parliament dissolves by December 2027 at the latest, so the general
   election brings the largest interest in what MPs said. Outreach: Sinar Project, r/malaysia,
   Lowyat forum, university law and politics societies, civic tech meetups, journalists who cover
   Parliament, and the 30 prospects.

- **Exit:** the demo is public, answers within the budget, and ingests new sittings on its own.

### Phase 8: paid pilot (only after the Track A gate passes)

- Accounts, saved searches, alert emails (a timer job after the nightly ingest, phase 7 step 4), the weekly digest, a privacy notice, invoicing by hand
  for the first customers.
- Sized and planned when the gate passes, from what the pilot customers ask for.

### After launch

In the order users ask: older Parliaments, Dewan Negara, attendance, point-in-time law (amendments
by date), subsidiary legislation, state assemblies (Selangor first), written answers if Parliament
publishes them.

## What the owner does

1. Sign off the phase 0 legal finding before anything is public.
2. No hand review of pilot records or test questions: Claude reviews them in the owner's place.
3. Find a law-student reviewer for the hand-written questions, if one is available.
4. Build the list of 30 prospects during phases 2 to 5.
5. Approve the demo's monthly budget.
6. Run the outreach and the 10 buyer conversations in phase 7.

## Costs

Claude prices per million tokens, input and output (claude-api skill, cached 2026-10-06): Haiku
5.5 [amount removed]; Sonnet 5.5 [amount removed]; Opus 5.5 [amount removed]. The Batch API halves

Corpus, counted in phase 0 (`docs/sources.md`): Malay runs at about 1.9 characters per token, so
a full sitting day is 160,000 to 210,000 tokens and the 539 days hold about 92 million. The 494
Special Chamber days add about 8.5 million, for about 100 million in all. Enrichment output is
estimated at 27 million tokens.

| Item | Expected |
|---|---|
| Enrichment, Haiku 5.5 with adaptive thinking on the Batch API (the chosen model) | about [amount removed]; thinking adds output tokens (0.62 output tokens per input token in the benchmark) |
| Enrichment, Sonnet 5.5 on the Batch API (not used) | about [amount removed] |
| Re-processing a revised sitting | about [amount removed] |
| Phase 3 pilot | under [amount removed] |
| Phase 5 eval | about [amount removed] |
| New sittings each month | under [amount removed] on either model |
| Demo rerank, Haiku 5.5 (about 9,000 tokens in and 50 out per search, measured in phase 5) | about [amount removed] per search; 1,000 searches a day is about [amount removed] a month |
| Demo hosting | under [amount removed] a month |

## Risks

| Risk | Plan |
|---|---|
| An AI summary misquotes an MP | Parser decides the speaker; summaries shown beside verbatim text and labelled; commitment quotes checked by code; correction link |
| The project reads as partisan | No scoring or stance labels on people; records describe what was said; the same treatment for every party |
| Section 3 reads differently in context | Phase 0 sign-off before any public step; the private build goes on either way |
| The government adds AI search or alerts to Hansard Digital | The paid value is the structured history (question-answer pairs, commitments, Act links) and the digest, not search alone; Track A gate before any paid build |
| No organisation pays | Release 1 still stands as portfolio work; the gate stops paid work before it costs anything |
| A source blocks crawling | Cache everything once; slow, identified downloads; ask Parliament for bulk access if needed |
| PDF layouts vary between years | Pilots per Parliament; failure reports instead of silent drops |
| Qwen3 is weak on Malay | Measured in phase 5: the language gap is 0 points with the Haiku reranker; misses follow the source text's language (a Malay question about a section held only in English) |
| The reranker is slow on a CPU container | Measured in phase 5: the local reranker misses 3 seconds at every pool size, so Haiku 5.5 reranks through the API (95th percentile 2.8 s, a narrow pass). If the container misses it, a pool of 10 or a faster first stage |
| The rerank call fails or the API is down | The search keeps the fused order and still answers; failures are counted |
| A wrong legal answer harms someone | Citations on every claim, "not legal advice", refusal on personal cases, quotes shown beside answers |
| Old consolidated text shown as current | Every law answer shows its reprint date; point-in-time text comes after launch |
