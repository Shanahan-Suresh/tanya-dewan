# parlimen-search: project guide

Hybrid RAG over Malaysia's principal Acts and the Dewan Rakyat Hansard, with its Special
Chamber (14th and 15th Parliaments), in Malay and English, with filters by date, Parliament, speaker, party, ministry,
topic and Act. Claude Batch enrichment turns the debates into structured records: question-answer
pairs, tags, summaries and ministers' commitments. `ROADMAP.md` holds the plan; work through its
phases in order. The pipeline starts as a copy of novel-rag (`D:\Projects\personal\novel-rag`);
read that project's `CLAUDE.md` and `README.md` before changing search, eval or chat code.

## Hard rules

1. **Nothing goes public before the phase 0 legal finding** (`docs/sources.md`) and the owner's
   sign-off. Until then, downloaded texts and everything built from them stay in the git-ignored
   `data/`.
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
6. **Every Claude call logs its usage.**
7. **The GPU is shared on this machine.** Long GPU jobs go through the forge-tools GPU lease, as in
   novel-rag (`tools\gpu_run.py` there).
8. **The repository stays private** until the owner says it can go public.
9. **The parser decides who spoke, never the model.** Summaries appear beside the verbatim text with
   an AI label, and a commitment whose quote does not match the Hansard text is dropped.
10. **No paid-tier code (accounts, billing, alert sending) before the Track A gate** in `ROADMAP.md`
    (Money path) passes.
