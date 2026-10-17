# parlimen-search: project guide

Hybrid RAG over Malaysia's principal Acts and the Hansard debates, in Malay and English, with
filters by date, chamber, speaker, party and Act. `ROADMAP.md` holds the plan; work through its
phases in order. The pipeline starts as a copy of novel-rag (`D:\Projects\personal\novel-rag`);
read that project's `CLAUDE.md` and `README.md` before changing search, eval or chat code.

## Hard rules

1. **Nothing goes public before the phase 0 legal finding** (`docs/sources.md`) and the owner's
   sign-off. Until then, downloaded texts and everything built from them stay in the git-ignored
   `data/`.
2. **Crawl politely:** cache every file once, rate-limit, send an identifying user agent, follow
   each site's `robots.txt` and terms. Never re-download what the cache holds.
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
