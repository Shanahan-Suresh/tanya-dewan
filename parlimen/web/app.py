"""The site: the ask page (search plus a cited answer), and server-rendered record pages for Acts,
sittings, agenda items, question-answer pairs, commitments, MPs, bills and topics.

Record pages read `data/site.db` (parlimen/records.py) and need no model. The ask page runs the
chosen search (parlimen/search.py, Haiku reranking) and the answer step (parlimen/answer.py). A
Searcher's SQLite connection may only be used on the thread that opened it, so the searcher is
built on one worker thread and every search runs there; Claude calls run on the request's thread.
At start the server loads the index, the vectors and the embedder in the background (`_Engine`):
the embedder runs on the CPU, so the shared GPU is never held. A question asked before the load
ends gets HTTP 503 and a message to ask again in a minute; record pages serve meanwhile.

Questions are limited per visitor an hour, and the day's Claude spend has a budget (`limits.py`);
past the budget the ask page shows the passages found, with no rerank and no written answer. Each
question that runs is logged to data/questions.jsonl with its filters, cost and time, and no IP
address.

Interface text follows the `hl` cookie (en or ms); record text shows as the source prints it.
`robots.txt` and `sitemap.xml` (an index of one sitemap per kind of page, and per year of
sittings) take their absolute URLs from PARLIMEN_SITE_URL, else from the request.
Run:  python -m parlimen.web [--port 8780]
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response,
                               StreamingResponse)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from .. import answer as answer_mod
from .. import config
from ..records import SITE_DB, Records, build_empty, reflow, slug
from . import present
from .i18n import LANGS, t
from .limits import Limits

HERE = Path(__file__).resolve().parent
CORRECTIONS = config.DATA / "corrections.jsonl"
QUESTIONS = config.DATA / "questions.jsonl"
SITE_URL = os.environ.get("PARLIMEN_SITE_URL", "").rstrip("/")
IDLE_MINUTES = 10
DEVICE = os.environ.get("PARLIMEN_SITE_DEVICE", "cpu")
EXAMPLES = {
    "en": ["Can my employer cut my salary?", "What did MPs say about the Online Safety Bill?",
           "How many hours a week may an employee work?", "What was said about the price of rice?"],
    "ms": ["Bolehkah majikan memotong gaji saya?", "Apa kata menteri tentang subsidi diesel?",
           "Apakah hukuman memandu dalam keadaan mabuk?", "Bilakah gaji minimum dinaikkan?"],
}
MALAY = frozenset("adakah apa apakah bagaimana berapa bila bilakah boleh bolehkah dalam dan dengan di ialah ini "
                  "itu kenapa kepada mengapa saya siapa tentang untuk yang menteri kerajaan akta".split())
PARTIES = ("AMANAH", "BERSATU", "DAP", "GPS", "MCA", "MIC", "MUDA", "PAS", "PBB", "PKR", "UMNO", "WARISAN")


def question_lang(question: str) -> str:
    words = re.findall(r"[^\W\d_]+", question.lower())
    malay = sum(w in MALAY for w in words)
    return "ms" if words and malay >= max(1, len(words) // 6) else "en"


class AskRequest(BaseModel):
    question: str = ""
    kind: str = ""
    act: str = ""
    lang: str = ""
    date_from: str = ""
    date_to: str = ""
    parliament: str = ""
    chamber: str = ""
    speaker: str = ""
    party: str = ""
    topic: str = ""


class _Engine:
    """Holds the Searcher, built on first use, and runs every search on one worker thread.

    The site embeds only questions (about 90 ms each on this CPU), so the embedder runs on the CPU
    by default and stays loaded: it holds no GPU, and no reader waits for a model load from the
    hard disk. With PARLIMEN_SITE_DEVICE=cuda it runs on the GPU and unloads after IDLE_MINUTES.
    """

    def __init__(self, searcher=None, device: str = DEVICE) -> None:
        self.searcher = searcher
        self.device = device
        self.last_used = time.monotonic()
        self.unloaded = False
        self.warmed = searcher is not None  # a given Searcher is ready; one built here waits for warm()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parlimen-search")

    def _built(self):
        if self.searcher is None:
            from ..models import Embedder
            from ..search import Searcher
            self.searcher = Searcher(embedder=Embedder(config.EMBEDDER, device=self.device))
        return self.searcher

    def run(self, fn: Callable):
        def work():
            try:
                return fn(self._built())
            finally:
                self.last_used = time.monotonic()
                self.unloaded = False
        return self._worker.submit(work).result()

    def warm(self) -> None:
        """Load the index, the vectors and (on the CPU) the embedder in the background. The venv, the
        model and the index sit on this machine's hard disk, where a cold first search takes minutes.
        A GPU embedder is left for the first question, so an idle site holds no GPU."""
        def work():
            s = self._built()
            _ = s.vectors
            from ..search import Filters
            s.bm25("warm up", Filters())
            if self.device == "cpu":
                s.embedder.query("warm up")
            self.warmed = True
        self._worker.submit(work)

    def unload_if_idle(self, now: float) -> bool:
        def work():
            if (self.device == "cpu" or self.searcher is None or self.unloaded
                    or now - self.last_used < IDLE_MINUTES * 60):
                return False
            unload = getattr(self.searcher.embedder, "unload", None)
            if unload is not None:
                unload()
            self.unloaded = True
            return True
        return self._worker.submit(work).result()


def law_url(act: str, lang: str, section: str = "") -> str:
    return f"/law/{quote(act)}/{lang}" + (f"#s-{slug(section)}" if section else "")


def debate_url(unit: str, seq: int | None = None) -> str:
    return f"/debate/{unit}" + (f"#seq-{seq}" if seq else "")


def pdf_page(url: str, page: int | None) -> str:
    return f"{url}#page={page}" if url and page else url


def play(saved: dict, events: queue.Queue, pace: float = 1.0) -> None:
    """Replay a saved answer as the stream would send it: each search stage starts and ends, then
    the answer grows line by line, then the whole body."""
    done = saved["done"]
    for st in done["stages"]:
        events.put(("stage", {"name": st["name"], "hits": None, "ms": None}))
        time.sleep(min(st["ms"], 1500) / 1000 * pace)
        events.put(("stage", st))
    events.put(("stage", {"name": "answer", "hits": None, "ms": None}))
    lines = done["answer"].split("\n")
    for i in range(1, len(lines)):
        if lines[i - 1].strip():
            time.sleep(0.45 * pace)
            events.put(("text", {"text": "\n".join(lines[:i]).strip()}))
    events.put(("done", done))


def create_app(records: Records | None = None, searcher=None, answer_fn: Callable | None = None,
               corrections: Path = CORRECTIONS, limits: Limits | None = None, question_log: Path = QUESTIONS,
               site_url: str = SITE_URL, replay: Path | None = None, demo: dict | None = None) -> FastAPI:
    """`replay` names a JSON file holding one saved /api/ask body under "answer" (as
    docs/design/data.json does): the ask routes then serve it with no model and no spend, for
    design work and screenshots. `demo` renders the pages for the static demo
    (tools/static_demo.py): {"repo", "recorded", "answers": [{"q", "lang", "file"}]} adds the demo
    bar, plays the recorded answers on the ask page and serves /not-in-demo."""
    app = FastAPI(title=config.SITE_NAME, docs_url=None, redoc_url=None)
    replay = {"done": json.loads(replay.read_text(encoding="utf-8"))["answer"]} if replay else None
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["loads"] = json.loads
    env.filters["reflow"] = reflow
    env.filters.update(tcase=present.tcase, unstar=present.unstar, unnum=present.unnum, cap=present.cap,
                       stage=present.stage)

    @pass_context
    def hdate(ctx, iso):
        return present.hdate(iso, ctx.get("lang", "en"))

    env.filters["hdate"] = hdate
    env.globals.update(law_url=law_url, debate_url=debate_url, pdf_page=pdf_page, slug=slug,
                       site_name=config.SITE_NAME, examples=EXAMPLES,
                       # the answer's own closing line; the page shows it once, in the answer foot
                       advice_lines=[answer_mod.NOT_ADVICE, answer_mod.NOT_ADVICE_MS], demo=demo)
    engine = _Engine(searcher)
    app.state.engine = engine
    limits = limits or Limits()
    app.state.limits = limits
    write_lock = threading.Lock()
    holder: dict = {"records": records}

    def rec() -> Records:
        if holder["records"] is None:
            holder["records"] = Records()
        return holder["records"]

    if answer_fn is None:
        from ..answer import ask

        def answer_fn(question, passages, lang, on_text=None):
            return ask(question, passages, lang, job="site-answer", on_text=on_text)

    def hl(request: Request) -> str:
        v = request.cookies.get("hl", "en")
        return v if v in LANGS else "en"

    def base_url(request: Request) -> str:
        return site_url or str(request.base_url).rstrip("/")

    def page(request: Request, template: str, status: int = 200, **ctx) -> HTMLResponse:
        lang = hl(request)
        args = dict(request.query_params)

        def with_page(n: int) -> str:
            return "?" + urlencode({**args, "page": n})

        tpl = env.get_template(template)
        values = dict(lang=lang, t=lambda k, **kw: t(k, lang).format(**kw) if kw else t(k, lang),
                      path=request.url.path,
                      full_path=str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""),
                      args=args, with_page=with_page, base_url=base_url(request), **ctx)
        # htmx asks for a filtered or paged list with the HX-Request header: send only the page's
        # `results` block, which it swaps in place; a plain request gets the whole page.
        if request.headers.get("HX-Request") and "results" in tpl.blocks:
            html = "".join(tpl.blocks["results"](tpl.new_context(values)))
        else:
            html = tpl.render(**values)
        return HTMLResponse(html, status, headers={"Vary": "HX-Request"})

    def missing(request: Request) -> HTMLResponse:
        return page(request, "missing.html", 404)

    @app.exception_handler(StarletteHTTPException)
    async def not_found_page(request: Request, exc: StarletteHTTPException):
        # An unknown address gets the site's own 404 page; the JSON API and static files keep theirs.
        if exc.status_code == 404 and not request.url.path.startswith(("/api/", "/static/")):
            return missing(request)
        return JSONResponse({"detail": exc.detail}, exc.status_code, headers=getattr(exc, "headers", None))

    def num(v: str, default: int = 1) -> int:
        try:
            return max(1, int(v))
        except (TypeError, ValueError):
            return default

    # ---------- language ----------

    @app.get("/hl/{lang}")
    def set_lang(lang: str, next: str = "/"):
        resp = RedirectResponse(next if next.startswith("/") else "/", 303)
        if lang in LANGS:
            resp.set_cookie("hl", lang, max_age=365 * 86400, samesite="lax")
        return resp

    # ---------- ask ----------

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        r = rec()
        return page(request, "home.html", topics=r.topics(), parties=PARTIES, meta=r.meta(),
                    sittings=r.sittings(limit=6), commitments=r.commitments(kind="promise", size=6).rows,
                    topic_trend=r.topic_trend(6), q=request.query_params.get("q", "")[:500])

    def run_question(request: Request, body: AskRequest, on_stage: Callable | None = None,
                     on_text: Callable | None = None) -> tuple[int, dict, dict]:
        """One question, start to end: checks, limits, search, answer, links, question log.
        Returns (HTTP status, body, headers). `on_stage` and `on_text` feed the streamed page."""
        from ..search import Filters

        q = body.question.strip()
        if not q:
            return 400, {"error": "empty question"}, {}
        if len(q) > 500:
            return 400, {"error": "question too long (500 characters at most)"}, {}
        if not engine.warmed:  # after the nightly restart the index loads for a few minutes
            return 503, {"error": t("warming", hl(request))}, {"Retry-After": "60"}
        if not limits.take(request.client.host if request.client else ""):
            return 429, {"error": t("limit_hour", hl(request)).format(n=limits.hourly)}, {}
        budget = limits.budget_left()
        f = Filters(kind=body.kind or None, act=body.act.strip() or None, lang=body.lang or None,
                    date_from=body.date_from or None, date_to=body.date_to or None,
                    parliament=int(body.parliament) if body.parliament.isdigit() else None,
                    chamber=body.chamber or None, speaker=body.speaker.strip() or None,
                    party=body.party or None, topic=body.topic or None)
        t0 = time.perf_counter()

        def search(s):
            before = getattr(s.reranker, "usd", 0.0)
            # Past the day's budget nothing calls Claude: the fused order stands and no answer is written.
            kw = {"on_stage": on_stage} if on_stage else {}
            trace = s.search(q, f, **kw) if budget else s.search(q, f, mode="hybrid", **kw)
            seqs = [s.row(p.ids[0]).seq_first for p in trace.passages]
            return trace, seqs, getattr(s.reranker, "usd", 0.0) - before

        trace, seqs, rerank_usd = engine.run(search)
        search_ms = (time.perf_counter() - t0) * 1000
        lang = question_lang(q)
        if on_stage:
            on_stage("answer", None)
        if not budget:
            ans = None
        elif on_text:
            ans = answer_fn(q, trace.passages, lang, on_text=on_text)
        else:
            ans = answer_fn(q, trace.passages, lang)
        usd = rerank_usd + (ans.usd if ans else 0.0)
        limits.spend(usd)
        r = rec()
        acts: dict[str, dict | None] = {}
        sittings: dict[tuple, dict | None] = {}
        units: dict[str, dict | None] = {}
        page_lang = hl(request)
        passages = []
        for p, seq in zip(trace.passages, seqs):
            if p.kind == "law":
                a = acts.setdefault(p.act, r.act(p.act))
                sec = r.section(p.act, p.section, p.lang)
                pdf = (a or {}).get("pdf_bi" if p.lang == "BI" else "pdf_bm", "")
                url, pdf = law_url(p.act, p.lang, p.section), pdf_page(pdf, (sec or {}).get("page_start"))
            else:
                s = sittings.setdefault((p.chamber, p.date), r.sitting(p.chamber, p.date))
                sp = r.speech(p.unit, seq)
                url, pdf = debate_url(p.unit, seq), pdf_page((s or {}).get("pdf", ""), (sp or {}).get("page_start"))
            draft = p.kind != "law" and bool((s or {}).get("draft"))
            if p.kind == "law":
                act_title = present.tcase((a or {}).get("title_bi" if p.lang == "BI" else "title_bm", "")) or f"Act {p.act}"
                title = f"{act_title}, {t('section', page_lang).lower()} {p.section}"
                meta = f"{t('as_at', page_lang)} {present.hdate(p.date, page_lang)}"
            else:
                unit = units.setdefault(p.unit, r.unit(p.unit))
                title = present.tcase((unit or {}).get("title", "")) or p.unit
                meta = f"{'Dewan Rakyat' if p.chamber == 'DR' else t('chamber_KK', page_lang)} · {present.hdate(p.date, page_lang)}"
            passages.append({"cite": p.cite, "title": title, "meta": meta, "header": p.header, "text": p.text,
                             "kind": p.kind, "url": url, "pdf": pdf, "via": p.via, "score": round(p.score, 4),
                             "draft": draft})
        sources = [{"n": s.n, "cite": s.cite, "quotes": s.quotes,
                    "title": passages[s.index]["title"] if 0 <= s.index < len(passages) else s.cite,
                    "meta": passages[s.index]["meta"] if 0 <= s.index < len(passages) else "",
                    "url": passages[s.index]["url"] if 0 <= s.index < len(passages) else "",
                    "pdf": passages[s.index]["pdf"] if 0 <= s.index < len(passages) else "",
                    "draft": passages[s.index]["draft"] if 0 <= s.index < len(passages) else False}
                   for s in (ans.sources if ans else [])]
        stages = [{"name": st.name, "hits": len(st.hits), "ms": round(st.ms)} for st in trace.stages]
        total_ms = round((time.perf_counter() - t0) * 1000)
        with write_lock:
            question_log.parent.mkdir(parents=True, exist_ok=True)
            with open(question_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "question": q,
                                     "lang": lang, "filters": trace.filters.describe(), "answered": ans is not None,
                                     "usd": round(usd, 5), "ms": total_ms}, ensure_ascii=False) + "\n")
        return 200, {"question": q, "lang": lang, "filters": trace.filters.describe(),
                     "answer": ans.text if ans else "", "budget_out": ans is None, "sources": sources,
                     "passages": passages, "stages": stages, "usd": round(usd, 5), "search_ms": round(search_ms),
                     "total_ms": total_ms}, {}

    @app.post("/api/ask")
    def api_ask(request: Request, body: AskRequest):
        if replay is not None:
            return replay["done"]
        status, payload, headers = run_question(request, body)
        return payload if status == 200 else JSONResponse(payload, status, headers=headers)

    @app.post("/api/ask/stream")
    def api_ask_stream(request: Request, body: AskRequest):
        """The same answer as /api/ask, as server-sent events: `stage` (a search stage starts, with no
        hits yet, or ends, with its hits and time), `text` (the cited answer so far), then `done`
        (the /api/ask body) or `error` (its message and HTTP status)."""
        events: queue.Queue = queue.Queue()

        def stage(name, st):
            events.put(("stage", {"name": name, "hits": len(st.hits) if st else None,
                                  "ms": round(st.ms) if st else None}))

        def work():
            try:
                if replay is not None:
                    play(replay, events)
                    return
                status, payload, _ = run_question(request, body, on_stage=stage,
                                                  on_text=lambda text: events.put(("text", {"text": text})))
                events.put(("done", payload) if status == 200 else ("error", {**payload, "status": status}))
            except Exception as e:  # noqa: BLE001 - the reader gets a message instead of a hung page
                events.put(("error", {"error": f"The answer failed: {type(e).__name__}.", "status": 500}))
            finally:
                events.put(None)

        threading.Thread(target=work, daemon=True).start()

        def sse():
            while (item := events.get()) is not None:
                name, data = item
                yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    # ---------- the law ----------

    @app.get("/law", response_class=HTMLResponse)
    def acts(request: Request, q: str = ""):
        rows = rec().acts()
        if q:
            words = q.lower().split()
            rows = [a for a in rows if all(w in f"{a['number']} {a['title_bi']} {a['title_bm']}".lower() for w in words)]
        return page(request, "acts.html", acts=rows, q=q)

    @app.get("/law/{act}")
    def act_default(act: str):
        a = rec().act(act)
        if not a:
            return RedirectResponse("/law", 303)
        return RedirectResponse(law_url(act, "BI" if "BI" in a["langs"] else "BM"), 303)

    @app.get("/law/{act}/{lang}", response_class=HTMLResponse)
    def act_text(request: Request, act: str, lang: str):
        r = rec()
        a = r.act(act)
        if not a or lang not in ("BI", "BM"):
            return missing(request)
        sections = r.sections(act, lang)
        if not sections:
            return missing(request)
        return page(request, "act.html", act=a, lang_code=lang, sections=sections,
                    other=[x for x in a["langs"].split(",") if x and x != lang],
                    pdf=a["pdf_bi"] if lang == "BI" else a["pdf_bm"], debates=r.act_debates(act))

    # ---------- the debates ----------

    @app.get("/hansard", response_class=HTMLResponse)
    def sittings(request: Request, parliament: str = "15"):
        p = int(parliament) if parliament in ("14", "15") else 15
        rows = rec().sittings(p)
        meetings: dict[str, list] = {}
        for s in rows:
            meetings.setdefault(s["meeting"], []).append(s)
        return page(request, "sittings.html", meetings=meetings, parliament=p)

    @app.get("/hansard/{chamber}/{date}", response_class=HTMLResponse)
    def sitting(request: Request, chamber: str, date: str):
        r = rec()
        s = r.sitting(chamber, date)
        if not s:
            return missing(request)
        return page(request, "sitting.html", sitting=s, units=r.sitting_units(chamber, date))

    @app.get("/debate/{unit_id}", response_class=HTMLResponse)
    def debate(request: Request, unit_id: str):
        r = rec()
        u = r.unit(unit_id)
        if not u:
            return missing(request)
        prev, nxt = r.neighbours(u)
        bill = r.bill(u["bill"]) if u["bill"] else None
        return page(request, "debate.html", unit=u, sitting=r.sitting(u["chamber"], u["date"]),
                    speeches=r.speeches(unit_id), qa=r.unit_qa(unit_id), commitments=r.unit_commitments(unit_id),
                    prev=prev, next=nxt, bill=bill, act=r.act(u["act"]) if u["act"] else None)

    # ---------- records with filters ----------

    def _filters(request: Request) -> dict:
        a = request.query_params
        return {k: a.get(k, "") for k in ("q", "year", "ministry", "topic", "parliament")}

    def _options(r: Records, table: str) -> dict:
        return {"years": [(y, y) for y in r.years()],
                "ministries": [(x["ministry"], x["ministry"]) for x in r.ministries(table)],
                "topics": [(x["topic"], x["name"]) for x in r.topics()]}

    @app.get("/commitments", response_class=HTMLResponse)
    def commitments(request: Request, kind: str = ""):
        r = rec()
        f = _filters(request)
        if kind not in ("", "promise", "routine"):
            kind = ""
        res = r.commitments(**f, kind=kind, page=num(request.query_params.get("page", "1")))
        return page(request, "commitments.html", res=res, f=f, kind=kind, opts=_options(r, "commitments"))

    @app.get("/questions", response_class=HTMLResponse)
    def questions(request: Request):
        r = rec()
        f = _filters(request)
        res = r.questions(**f, page=num(request.query_params.get("page", "1")))
        return page(request, "questions.html", res=res, f=f, opts=_options(r, "qa"))

    # ---------- MPs, bills, topics ----------

    @app.get("/mp", response_class=HTMLResponse)
    def members(request: Request, parliament: str = "15", q: str = ""):
        p = int(parliament) if parliament in ("14", "15") else 15
        q = q.strip()[:80]
        rows = rec().members(p)
        if q:
            needle = q.casefold()
            rows = [m for m in rows if needle in f"{m['code']} {m['seat']} {m['name']}".casefold()]
        return page(request, "members.html", members=rows, parliament=p, q=q)

    @app.get("/mp/{member}", response_class=HTMLResponse)
    def member(request: Request, member: str):
        r = rec()
        m = r.member(member)
        if not m:
            return missing(request)
        n = num(request.query_params.get("page", "1"))
        return page(request, "member.html", m=m, units=r.member_units(member, n), parliament_now=r.parliament_now(),
                    asked=r.questions(member=member, size=20).rows,
                    answered=r.member_answers(member, 10),
                    made=r.commitments(member=member, size=20).rows,
                    counts=r.member_counts(member), activity=r.member_activity(member),
                    top_topics=r.member_topics(member, 8), offices=r.member_offices(member))

    @app.get("/bills", response_class=HTMLResponse)
    def bills(request: Request):
        return page(request, "bills.html", bills=rec().bills())

    @app.get("/bill/{bill}", response_class=HTMLResponse)
    def bill(request: Request, bill: str):
        r = rec()
        b = r.bill(bill)
        if not b:
            return missing(request)
        return page(request, "bill.html", bill=b, act=r.act(b["act"]) if b["act"] else None)

    @app.get("/topics", response_class=HTMLResponse)
    def topics(request: Request):
        return page(request, "topics.html", topics=rec().topics())

    @app.get("/topic/{topic}", response_class=HTMLResponse)
    def topic(request: Request, topic: str):
        r = rec()
        names = {slug(x["topic"]): x for x in r.topics()}
        if topic not in names:
            return missing(request)
        n = num(request.query_params.get("page", "1"))
        return page(request, "topic.html", topic=topic, topic_name=names[topic]["name"], units=r.topic_units(topic, n),
                    commitments=r.commitments(topic=topic, size=10).rows)

    # ---------- corrections and about ----------

    @app.get("/correction", response_class=HTMLResponse)
    def correction_form(request: Request, record: str = "", back: str = ""):
        return page(request, "correction.html", record=record, back=back if back.startswith("/") else "", sent=False)

    @app.post("/correction", response_class=HTMLResponse)
    def correction_send(request: Request, record: str = Form(""), back: str = Form(""), text: str = Form(""),
                        contact: str = Form("")):
        text = text.strip()[:4000]
        if text:
            corrections.parent.mkdir(parents=True, exist_ok=True)
            with open(corrections, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "record": record[:200],
                                    "page": back[:300], "text": text, "contact": contact.strip()[:200]},
                                   ensure_ascii=False) + "\n")
        return page(request, "correction.html", record=record, back=back if back.startswith("/") else "",
                    sent=bool(text))

    if demo:
        @app.get("/not-in-demo", response_class=HTMLResponse)
        def not_in_demo(request: Request):
            return page(request, "demo_missing.html")

    @app.get("/about", response_class=HTMLResponse)
    def about(request: Request):
        return page(request, "about.html", meta=rec().meta(), limits=limits)

    # ---------- search engines ----------

    def xml(body: str) -> Response:
        return Response('<?xml version="1.0" encoding="UTF-8"?>\n' + body, media_type="application/xml")

    def urlset(request: Request, paths: list[str]) -> Response:
        base = base_url(request)
        locs = "".join(f"<url><loc>{escape(base + p)}</loc></url>\n" for p in paths)
        return xml(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{locs}</urlset>\n')

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(HERE / "static" / "favicon.ico", media_type="image/x-icon",
                            headers={"Cache-Control": "public, max-age=604800"})

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(request: Request):
        return ("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /hl/\nDisallow: /correction\n"
                f"Disallow: /*?q=\n\nSitemap: {base_url(request)}/sitemap.xml\n")

    @app.get("/sitemap.xml")
    def sitemap_index(request: Request):
        base = base_url(request)
        names = ["pages", "law", "mps", "bills", "topics"] + [f"hansard-{y}" for y in rec().sitting_years()]
        maps = "".join(f"<sitemap><loc>{escape(base)}/sitemap-{n}.xml</loc></sitemap>\n" for n in names)
        return xml(f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{maps}</sitemapindex>\n')

    @app.get("/sitemap-{name}.xml")
    def sitemap(request: Request, name: str):
        r = rec()
        if name == "pages":
            paths = ["/", "/law", "/hansard", "/hansard?parliament=14", "/questions", "/commitments", "/mp",
                     "/mp?parliament=14", "/bills", "/topics", "/about"]
        elif name == "law":
            paths = [law_url(a["number"], lang) for a in r.acts() for lang in a["langs"].split(",") if lang]
        elif name == "mps":
            paths = [f"/mp/{quote(m)}" for m in r.member_slugs()]
        elif name == "bills":
            paths = [f"/bill/{quote(b['slug'])}" for b in r.bills()]
        elif name == "topics":
            paths = [f"/topic/{slug(x['topic'])}" for x in r.topics()]
        elif name.startswith("hansard-") and name[8:] in r.sitting_years():
            year = name[8:]
            paths = [f"/hansard/{s['chamber']}/{s['date']}" for s in r.sittings() if s["date"].startswith(year)]
            paths += [debate_url(u) for u in r.unit_ids(year)]
        else:
            return missing(request)
        return urlset(request, paths)

    @app.get("/api/health")
    def health():
        return {"ok": True, "searcher": engine.searcher is not None, "warmed": engine.warmed}

    return app


def _watch_idle(engine: _Engine) -> None:
    while True:
        time.sleep(30)
        try:
            engine.unload_if_idle(time.monotonic())
        except Exception:  # noqa: BLE001 - the watcher must outlive one failed check
            pass


LOCK = config.DATA / "site.lock"


def hold_single_site(lock: Path = LOCK):
    """Refuse to start a second full site on this machine; returns the open lock file to keep.

    A full site holds the search model and vectors (about 2.5 GB), so two copies starve the PC.
    The operating system drops the lock when the process ends, however it ends, so a crash
    leaves nothing to clean up. The holder's PID sits beside it for the error message.
    """
    lock.parent.mkdir(parents=True, exist_ok=True)
    pid_file = lock.with_suffix(".pid")
    f = open(lock, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        try:
            holder = pid_file.read_text(encoding="utf-8").strip()
        except OSError:
            holder = "unknown"
        raise SystemExit(f"A full site is already running (PID {holder}). Stop that process first, "
                         "or start this one with --replay, which loads no model.") from None
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    return f


def main() -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description="Tanya Dewan site")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--replay", type=Path, help="serve this saved answer on the ask page, with no model or spend "
                                                "(for design work; docs/design/data.json holds one)")
    a = ap.parse_args()
    _lock = None if a.replay else hold_single_site()  # noqa: F841 - kept open for the life of the site
    records = None
    if a.replay and not SITE_DB.exists():            # a fresh clone: the pages show empty lists
        import tempfile

        records = Records(build_empty(Path(tempfile.mkdtemp()) / "site.db"))
        print("no data/site.db: the pages are empty; build the data to fill them", flush=True)
    app = create_app(replay=a.replay, records=records)
    if not a.replay:
        app.state.engine.warm()
    threading.Thread(target=_watch_idle, args=(app.state.engine,), daemon=True).start()
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
