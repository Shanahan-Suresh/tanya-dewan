"""MCP server: search and read Malaysia's Acts and the Dewan Rakyat Hansard, over stdio.

Tools: search_law and search_debates (the chosen search: BM25, vectors, fusion, Haiku reranking),
read_section and read_sitting (the records, no model), list_commitments (the checked commitments).
The searcher is built on the first search; its embedder unloads after PARLIMEN_IDLE_MINUTES
without a search and reloads on the next. stdout carries the MCP messages, so logs go to stderr.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
import threading
import time
from typing import Callable

from mcp.server.mcpserver import MCPServer

from .records import Records, reflow, slug, who
from .search import Filters

log = logging.getLogger("parlimen.mcp_server")

IDLE_SECONDS = float(os.environ.get("PARLIMEN_IDLE_MINUTES", "10")) * 60
CHECK_SECONDS = 30
SPEECH_CHARS = 4000     # one speech is cut here in read_sitting, with a note of its full length
SITTING_CHARS = 60000   # read_sitting stops adding speeches past this

server = MCPServer(name="tanya-dewan", instructions=(
    "Searches Malaysia's principal Acts (English and Malay, at the reprint date shown) and the Dewan Rakyat "
    "Hansard of the 14th and 15th Parliaments (July 2018 onwards, with the Special Chamber). Use search_law "
    "for what an Act says, search_debates for what MPs and ministers said, read_section and read_sitting to "
    "read a hit in full, and list_commitments for ministers' promises. Speeches are verbatim, mostly Malay; "
    "lines marked (AI) were written by a model and are less reliable than the verbatim text. Cite the Act "
    "and section, or the chamber, date and speaker. This is the published record, not legal advice."
))

_lock = threading.Lock()
_searcher = None
_records: Records | None = None
_last_used = 0.0
_unloaded = False


def _share(s):
    """Reopen the index connection so the SDK's worker threads may use it; `_lock` keeps one tool at a time."""
    s.con.close()
    s.con = sqlite3.connect(s.root / "index.db", check_same_thread=False)
    s.con.row_factory = sqlite3.Row
    return s


def set_searcher(s, records: Records | None = None) -> None:
    """Install a searcher (and records) without warming them (for tests)."""
    global _searcher, _records, _last_used, _unloaded
    with _lock:
        _searcher = _share(s)
        if records is not None:
            _records = records
        _last_used = time.monotonic()
        _unloaded = False


def _recs() -> Records:
    global _records
    if _records is None:
        _records = Records()
    return _records


def _search(work: Callable) -> str:
    global _searcher, _last_used, _unloaded
    with _lock:
        try:
            if _searcher is None:
                from .search import Searcher
                _searcher = _share(Searcher())
            return work(_searcher)
        finally:
            _last_used = time.monotonic()
            _unloaded = False


def unload_if_idle(now: float) -> bool:
    global _unloaded
    with _lock:
        if _searcher is None or _unloaded or now - _last_used < IDLE_SECONDS:
            return False
        unload = getattr(_searcher.embedder, "unload", None)
        if unload is not None:
            unload()
        _unloaded = True
        log.info("idle: embedder unloaded")
        return True


def _watch_idle() -> None:
    while True:
        time.sleep(CHECK_SECONDS)
        try:
            unload_if_idle(time.monotonic())
        except Exception:
            log.exception("idle check failed")


def _passages(trace, k: int) -> str:
    if not trace.passages:
        return "No passages found."
    out = []
    for n, p in enumerate(trace.passages[:k], start=1):
        head = f"[{n}] {p.cite}" + (f" ({p.via})" if p.via else "")
        out.append(f"{head}\n{p.header}\n{p.text}")
    return "\n\n".join(out)


@server.tool()
def search_law(question: str, act: str | None = None, lang: str | None = None, k: int = 8) -> str:
    """Search the Acts by meaning and by keywords, rerank, and return the k best sections.

    `act` keeps one Act by number ("265" is the Employment Act 1955). `lang` is "BI" (English) or "BM"
    (Malay); leave it out for both. `k` is 1 to 15. A section's cross-references come after the hits.
    Each hit names the Act, section, language and reprint date.
    """
    if lang not in (None, "", "BI", "BM"):
        return 'Error: lang must be "BI" or "BM".'
    f = Filters(kind="law", act=act or None, lang=lang or None)
    k = max(1, min(15, k))
    return _search(lambda s: _passages(s.search(question, f, top_k=k), k + 3))


@server.tool()
def search_debates(question: str, date_from: str | None = None, date_to: str | None = None,
                   parliament: int | None = None, chamber: str | None = None, speaker: str | None = None,
                   party: str | None = None, topic: str | None = None, act: str | None = None, k: int = 8) -> str:
    """Search the Hansard by meaning and by keywords, rerank, and return the k best passages.

    Dates are ISO ("2024-03-01"), inclusive. `parliament` is 14 or 15. `chamber` is "DR" (Dewan Rakyat)
    or "KK" (the Special Chamber). `speaker` matches part of a name; `party` is a party code ("DAP",
    "UMNO", "PAS") on the sitting's date. `topic` is one of the fixed topics ("health", "labour and
    jobs"). `act` keeps the debates on bills for that Act number. Each passage names the chamber, date
    and extract id (for read_sitting) and opens with its speakers.
    """
    if chamber not in (None, "", "DR", "KK"):
        return 'Error: chamber must be "DR" or "KK".'
    f = Filters(kind="debate", act=act or None, date_from=date_from or None, date_to=date_to or None,
                parliament=parliament or None, chamber=chamber or None, speaker=speaker or None,
                party=party or None, topic=topic or None)
    k = max(1, min(15, k))
    return _search(lambda s: _passages(s.search(question, f, top_k=k), k))


@server.tool()
def read_section(act: str, section: str, lang: str = "BI") -> str:
    """Return one Act section in full, with its Part, heading, reprint date and editorial notes.

    `act` is the Act number, `section` its number ("60A"), `lang` "BI" (English) or "BM" (Malay).
    """
    r = _recs()
    a = r.act(act)
    if not a:
        return f"No Act {act} in the record."
    s = r.section(act, section, lang)
    if not s:
        have = ", ".join(x["number"] for x in r.sections(act, lang)[:400])
        return f"Act {act} has no section {section} in {lang}. Sections: {have or 'none in this language'}."
    title = a["title_bi"] if lang == "BI" else a["title_bm"]
    head = f"{title} (Act {act}), section {s['number']}: {s['heading']} ({lang}, as at {a['as_at']})"
    part = f"{s['part']} {s['part_title']}".strip()
    notes = f"\n\nEditorial notes:\n{reflow(s['notes'])}" if s["notes"] else ""
    return f"{head}\n{part}\n\n{reflow(s['text'])}{notes}\n\nThis is the published text, not legal advice."


@server.tool()
def read_sitting(chamber: str, date: str, extract: str | None = None) -> str:
    """List a sitting's agenda items with their AI summaries, or read one item's speeches verbatim.

    `chamber` is "DR" or "KK", `date` ISO. Without `extract` the tool lists the items with their ids
    ("DR-2024-03-05-012"); with an id it returns that item's speeches, each with speaker, party, page and
    time, then its question-answer pairs and commitments.
    """
    r = _recs()
    s = r.sitting(chamber, date)
    if not s:
        return f"No {chamber} sitting on {date} in the record (14th and 15th Parliaments)."
    if not extract:
        units = r.sitting_units(chamber, date)
        lines = [f"{chamber} {date}, Parliament {s['parliament']}, {s['meeting']}. PDF: {s['pdf']}"]
        for u in units:
            lines.append(f"\n{u['id']}: {u['business'] or '(no heading)'} ({u['speeches']} speeches)")
            if u["summary_en"]:
                lines.append(f"  Summary (AI): {u['summary_en']}")
        return "\n".join(lines)
    u = r.unit(extract)
    if not u or u["chamber"] != chamber or u["date"] != date:
        return f"No extract {extract} in the {chamber} sitting of {date}."
    lines = [f"{extract}: {u['business']}", f"Summary (AI): {u['summary_en']}" if u["summary_en"] else ""]
    used = 0
    for sp in r.speeches(extract):
        text = reflow(sp["text"])
        if len(text) > SPEECH_CHARS:
            text = text[:SPEECH_CHARS] + f" [... cut; {len(text)} characters in all]"
        if used + len(text) > SITTING_CHARS:
            lines.append("\n[Further speeches left out: the extract is long. Search inside it with search_debates.]")
            break
        used += len(text)
        who = sp["label"] + (f" ({sp['party']})" if sp["party"] else "")
        lines.append(f"\n{who}, page {sp['page_start']}{', ' + sp['time'] if sp['time'] else ''}:\n{text}")
    for q in r.unit_qa(extract):
        lines.append(f"\nQuestion (AI) by {q['asker']}: {q['question']}\nAnswer (AI) by {q['answerer']}: {q['answer']}")
    for c in r.unit_commitments(extract):
        lines.append(f"\nCommitment by {c['speaker']}: \"{c['quote']}\" (AI: {c['promise']})")
    return "\n".join(x for x in lines if x)


@server.tool()
def list_commitments(query: str | None = None, ministry: str | None = None, topic: str | None = None,
                     year: str | None = None, parliament: int | None = None, limit: int = 20) -> str:
    """List ministers' commitments made in the House, newest first.

    `query` matches words of the promise, the quote, the speaker or the office. `ministry` is a ministry
    name as the Hansard prints it ("Kewangan", "Kesihatan", "Jabatan Perdana Menteri"). `topic` is one
    of the fixed topics, `year` four digits, `parliament` 14 or 15. Each quote is verbatim and checked
    against the Hansard text; the promise line is AI-written.
    """
    r = _recs()
    res = r.commitments(q=query or "", ministry=ministry or "", topic=slug(topic) if topic else "",
                        year=year or "", parliament=str(parliament or ""), size=max(1, min(100, limit)))
    if not res.rows:
        return "No commitments match."
    out = [f"{res.total} commitments match; the newest {len(res.rows)}:"]
    for c in res.rows:
        extra = "; ".join(x for x in (c["deadline"] and f"by {c['deadline']}", c["amount"] and f"amount {c['amount']}") if x)
        out.append(f"\n{c['date']} {c['chamber']} {c['unit']}: {who(c['speaker'], c['office'])}\n"
                   f"  \"{c['quote']}\"\n  Promise (AI): {c['promise']}{' (' + extra + ')' if extra else ''}"
                   f"{' [routine step]' if c['kind'] == 'routine' else ''}")
    return "\n".join(out)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    threading.Thread(target=_watch_idle, name="parlimen-idle", daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
