# Tanya Dewan (repo tanya-dewan, package parlimen): project guide

Hybrid RAG over Malaysia's principal Acts and the Dewan Rakyat Hansard, with its Special
Chamber (14th and 15th Parliaments), in Malay and English, with filters by date, Parliament, speaker, party, ministry,
topic and Act. Claude Batch enrichment turns the debates into structured records: question-answer
pairs, tags, summaries and ministers' commitments. It is a public portfolio project with a free
static demo on GitHub Pages; there is no paid tier. `ROADMAP.md` holds the plan and the eval
targets; `PROGRESS.md` holds the current state.

The search, eval and chat pipeline began as a copy of the author's private novel-rag project. On the
author's machine, read that project's `CLAUDE.md` and `README.md` before changing search, eval or
chat code.

## Hard rules

1. **Publish extracted text only.** The legal finding in `docs/sources.md` is signed off: Acts and
   Hansard debates carry no copyright as text. The official PDFs and page images are never
   republished; every page links the official PDF. Downloaded texts and everything built from them
   stay in the git-ignored `data/`, except the recorded demo answers in `docs/demo/answers/`.
2. **Crawl politely:** cache every file once, rate-limit, send an identifying user agent, follow
   each site's `robots.txt` and terms. Never re-download what the cache holds, except the weekly
   re-check of draft sittings (`parlimen/drafts.py`), which fetches each draft PDF of the last year
   once a week.
3. **Not legal advice.** Every answer cites its sources, shows the Act's reprint date or the
   sitting date, and carries the not-legal-advice line. The answer path refuses advice on a
   reader's own case.
4. **Pilot before every bulk job:** 10 Acts or 5 sitting days, checked by hand against the PDFs,
   before a full crawl or parse; one small batch before any bulk Claude job, with the real cost
   read from the usage log.
5. **A technique stays only if the eval says so,** against targets fixed before the run
   (`ROADMAP.md`, Goals).
6. **Every Claude call logs its usage** (`data/api-usage.jsonl`).
7. **The GPU is shared on the author's machine.** Long GPU jobs there go through the forge-tools
   GPU lease (`tools/gpu_run.py`, with `FORGE_TOOLS` set); elsewhere, run them directly.
8. **The repository is public.** Never commit an API key, anything under `data/`, or a personal
   absolute path. The key comes from `ANTHROPIC_API_KEY` or `~/.claude/anthropic-api-key.txt`
   (`config.api_key()`).
9. **The parser decides who spoke, never the model.** Summaries appear beside the verbatim text with
   an AI label, and a commitment whose quote does not match the Hansard text is dropped.
10. **One full site per machine.** A full site holds about 2.7 GB of memory; `hold_single_site()`
    refuses a second one. Stop a site by its PID (`data/site.pid`) and check that it is gone.
