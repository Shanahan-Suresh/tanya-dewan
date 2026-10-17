# parlimen-search: roadmap

Ask Malaysian law and Malaysia's Parliament in plain Malay or English. One search covers two
sources:

- **The law:** what an Act says, cited to the Act and section.
- **The debate:** what MPs said about it in Parliament, cited to the sitting, the date, the speaker
  and the page of the Hansard (the official record of debates).

The two are linked: an Act points to the debates on its bill, so "why was this section added?"
finds the minister's speech that explained it.

It reuses the hybrid RAG pipeline of novel-rag (`D:\Projects\personal\novel-rag`): keyword and
vector search, fusion, a reranker, cited answers and the eval method.

## Goals

- **Useful:** a law student, journalist, researcher or small business finds the rule and the
  reason for it in one place, in either language, with sources they can check.
- **Career:** the strongest public proof for AI product engineer roles in Malaysia and Singapore:
  legal text structure, two languages, date and speaker filters, and published eval numbers.
- **Visible:** a public tool that local press, civic tech groups and universities can point to.

Targets for the launch build, fixed before the first measurement:

| Measure | Target |
|---|---|
| Recall@10, law questions (answer section in the top 10) | 0.85 or more |
| Recall@10, Hansard questions (answer page in the top 10) | 0.80 or more |
| Language gap: the same question asked in Malay and in English | under 5 points of recall@10 |
| Answer correctness on hand-written questions (blind judge) | 65 % or more |
| Answers whose every claim is backed by a quoted source | 80 % or more |
| Public demo cost | under [amount removed] a month at the daily cap |

## Who it is for

Law and politics students, journalists, NGO and policy researchers (Sinar Project's audience),
small business owners with a compliance question, and voters who want to know what their MP said.

## What exists already

Searched 2026-10-18 (GitHub, web).

- **Paid legal research for lawyers:** Lexis+ AI with Protégé Malaysia (2025), JusType. Narrow
  assistants: ChatAboutLaw (strata law), AskAILA (labour law).
- **Open lookups of principal Acts:** two MCP servers (`my-eli-mcp`, `@ansvar/malaysian-law-mcp`)
  fetch Act text for AI assistants; small RAG repositories (`araara243/malaysian-law`,
  `Malaysian-Laws-Chatbot`, both 0 stars).
- **Hansard:** Parliament's new Hansard Digital (launched June 2026 by GovTech Malaysia) has
  keyword search from 1959, in Malay and English. Parliament's repository
  (`repositori.parlimen.gov.my`) holds one PDF per sitting day. `isaacebi/Hansard-Malaysia` (0
  stars, 2022) is the only Hansard project found on GitHub. No AI search over the debates exists.
- **Singapore** built this for its own Parliament: Pair Search, by GovTech Singapore's Open
  Government Products. That proves the demand.

The gap: no tool searches the debates by meaning, links them to the law, works across both
languages, or publishes how well it works.

## Legal basis

- Malaysia's Copyright Act 1987, section 3, defines "literary work" to exclude official texts of
  the Government or statutory bodies of a legislative or regulatory nature, judicial decisions,
  political speeches and political debates, and their official translations. Read from the
  Wikimedia Commons summary of the Act as amended up to Act A1645; phase 0 confirms the wording
  against the Act's own text.
- If that holds, Acts and Hansard debates carry no copyright, and both the index and a public demo
  can quote them. Parliament's repository page says "all rights reserved"; phase 0 records why
  section 3 still applies, or narrows the demo.
- Not legal advice: every answer says so, cites its sources and links the official PDF. The answer
  model refuses to give advice on a reader's own case.
- Downloads are polite: cached, rate-limited, identified by a user agent, and within each site's
  `robots.txt`.

## Product

### What the reader can do

1. **Ask the law.** "Can my employer cut my salary?" gives the relevant sections of the Employment
   Act 1955, quoted and cited.
2. **Ask the debate.** "What did MPs say about the Online Safety Bill?" gives speeches with date,
   speaker, party and page.
3. **Follow the link.** From a section, open the debates on the bill that made or changed it.
4. **Filter.** By date range, chamber (Dewan Rakyat, Dewan Negara), speaker, party, Act.
5. **Ask in either language.** Malay or English, with sources in both; the page shows which text
   is the authoritative one.
6. **How it found this.** The novel-rag visualiser panel, adapted to sections and speeches.

### First release scope

- **Laws:** every principal Act on Laws of Malaysia Online (`lom.agc.gov.my`, run by the Attorney
  General's Chambers), English and Malay, at the reprint date the portal shows.
- **Debates:** Dewan Rakyat sittings of the 15th Parliament (from December 2022), which are born
  digital and need no OCR.
- **Later:** older Parliaments (scanned PDFs need OCR), Dewan Negara, amendment Acts and
  point-in-time text, subsidiary legislation, state enactments, written answers.

## Technical plan

| Part | Approach |
|---|---|
| Act download | Crawl the portal's Act pages for the English and Malay PDFs and the reprint date; cache every file with its source URL |
| Act parsing | PDF to text, then structure: Part, section, subsection, definitions, schedules. Pair the English and Malay versions by section number |
| Hansard download | One PDF per sitting day from the repository, or Hansard Digital if it offers structured text (phase 0 checks) |
| Hansard parsing | Split into speeches: speaker name and role, time, page; detect the language of each paragraph (debates switch between Malay and English) |
| MP data | Party and seat per MP per Parliament, from Parliament's member pages or Sinar Project's open data |
| Linking | Bill numbers (such as "D.R. 12/2023") found in the Hansard, matched to each Act's enactment details; section cross-references ("subsection 13(2)") resolved inside the law |
| Chunks | One law chunk per section (long sections split at subsections, with the Act and section in the header); one debate chunk per speech or speech part, with sitting, speaker and date in the header |
| Search | novel-rag's pipeline: BM25, Qwen3-Embedding-0.6B (multilingual, Malay measured in phase 4), RRF, Qwen3-Reranker-0.6B, neighbour expansion. Filters replace the spoiler limit |
| Answers | Claude with `search_result` citations, as novel-rag's chat. Haiku for the public demo, Opus locally |
| Front ends | The chat page, an MCP server for Claude Desktop and Claude Code, a CLI |

Stack: Python 3.12+, FastAPI, SQLite FTS5, NumPy, PyTorch for the search models. Hosting: a CPU
container (Cloud Run, where the owner already runs SiteMedic). Licence: MIT for the code.

## Phases

Effort is in working sessions like the one that built novel-rag's chat.

### Phase 0: legal and source check (0.5 session)

- Confirm the section 3 wording from the Act's official text; record the finding and its source
  in `docs/sources.md`.
- Read the terms and `robots.txt` of the portal, the repository and Hansard Digital.
- Probe each source: formats, page structure, download limits, whether Hansard Digital has
  structured text or an API.
- Count the corpus: Acts, pages, sitting days, words. Estimate notes and embedding cost from
  novel-rag's measured rates ([amount removed] per million tokens for notes; about 8 chunks per second to
  embed on the RTX 5070 Ti).
- **Exit:** a written go or no-go for a public demo, and the corpus size and cost estimate.

### Phase 1: the law corpus (1 to 1.5 sessions)

- Downloader with cache and rate limit; parser to sections; English and Malay pairing.
- Pilot first: 10 Acts end to end, checked by hand against the PDFs, before the full crawl.
- **Exit:** every principal Act parsed, with a report of sections that failed to parse; a sample of
  50 sections matches the PDF word for word.

### Phase 2: the debate corpus (1.5 to 2 sessions)

- Downloader and speech splitter; speaker, role, time and page per speech; MP party data.
- Pilot first: 5 sitting days checked by hand.
- **Exit:** every 15th Parliament sitting day parsed; speaker names resolve to MPs for 95 % or more
  of speeches.

### Phase 3: links and index (1 session)

- Bill-to-Act links, section cross-references, chunks, index, context notes (pilot first), embeds
  under the GPU lease.
- **Exit:** a search for a known Act returns its debates; a search inside an Act follows its
  cross-references.

### Phase 4: the eval (1 to 1.5 sessions)

- **Generated questions:** 150 law and 150 debate questions from random chunks, each with its
  answer section or page; half in Malay, half in English.
- **Language pairs:** 50 questions written in both languages; the gap between them is the
  multilingual score.
- **Hand-written questions:** 30 that a student, journalist or business owner would ask. The owner
  checks them; a law-student friend reviews them if one is available.
- **Filter questions:** 25 that need a date, speaker or party filter.
- Arms: keyword only, hybrid with rerank, with notes, and with a Malay-specific embedder if Qwen3
  falls short on Malay.
- **Exit:** the targets table above, measured and written to `results/`. A technique stays only if
  the eval says so.

### Phase 5: the page and the MCP server (1 session)

- Chat with filters, a section viewer with anchors, speech cards with date, speaker and party,
  links to the official PDFs, the "not legal advice" line, Malay and English interface text.
- MCP server: `search_law`, `search_debates`, `read_section`, `read_sitting`.
- **Exit:** a reader finds a section and its debate without the CLI.

### Phase 6: public demo and launch (1 session, then the owner)

- Cloud Run deployment, rate limit per visitor, daily answer budget, Haiku answers.
- README with the results table and a GIF; a short write-up for the personal site and LinkedIn.
- Outreach, by the owner: Sinar Project, r/malaysia, Lowyat forum, university law and politics
  societies, civic tech meetups, journalists who cover Parliament.
- **Exit:** the demo is public and answers within the budget.

### After launch

In the order users ask: older Parliaments with OCR, Dewan Negara, point-in-time law (amendments by
date), subsidiary legislation, state assemblies (Selangor first), written parliamentary answers,
and alerts when a new sitting mentions a followed Act.

## What the owner does

1. Sign off the phase 0 legal finding before anything is public.
2. Check the 30 hand-written questions in phase 4 (about 45 minutes), and find a law-student
   reviewer if possible.
3. Approve the demo's monthly budget.
4. Run the outreach in phase 6.

## Costs

| Item | Expected |
|---|---|
| Context notes on the corpus | measured in phase 0; roughly [amount removed] if the corpus is 15 to 40 million tokens |
| Phase 4 eval | about [amount removed] |
| Demo hosting and answers | under [amount removed] a month with the daily cap |

## Risks

| Risk | Plan |
|---|---|
| Section 3 reads differently from the summary | Phase 0 checks the Act's text before any public step; the private build goes on either way |
| A source blocks crawling | Cache everything once; slow, identified downloads; ask Parliament or the Attorney General's Chambers for bulk access if needed |
| PDF layouts vary between years | Pilots per source; failure reports instead of silent drops |
| Qwen3 is weak on Malay | Measured in phase 4; test a Malay-trained embedder as an extra arm |
| A wrong legal answer harms someone | Citations on every claim, "not legal advice", refusal on personal cases, quotes shown beside answers |
| Old consolidated text shown as current | Every law answer shows its reprint date; point-in-time text comes after launch |
