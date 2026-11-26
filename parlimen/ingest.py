"""Bring new sittings into the search index with no manual step.

A new sitting is one on Parliament's listing that data/hansard-report.csv does not hold yet. For
each, in order:

1. fetch its PDF (cached once) and parse it, with the registers in data/members.csv;
2. append its speeches to data/speeches.jsonl, its report row to data/hansard-report.csv and its
   extracts to data/enrich/units.jsonl;
3. enrich each extract with Haiku on the Messages API and check its commitments with Sonnet,
   appending the raw answers, the checks and the finished records as the bulk jobs do;
4. link a new bill heading to its Act in data/index/bill_links.csv;
5. chunk the extracts, append the chunks to index.db, and embed the new rows for every vector
   set on disk ("h" before "hn", so "hn" copies the rows with no note).

Each new sitting also gets its draft flag in data/drafts.csv (parlimen/drafts.py). Steps 3 to 5
run on every extract whose sitting index.db does not hold yet (`index_pending`), so a run that
stops part way resumes where it stopped; the weekly re-check of draft sittings uses the same steps
for a revised sitting. An extract whose enrichment fails is indexed without its note
and listed in the run's summary; `python -m parlimen.enrich submit` sends it again.

Run:  python -m parlimen.ingest [--dates ISO ...] [--no-refresh] [--dry-run]
"""

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import anthropic

from . import chunk, commit_check, config, drafts, enrich, fetch, hansard, index, links, sittings
from .sittings import Sitting

Call = Callable[[dict, str], dict]  # (request params, usage-log job) -> enrich.call's answer


def new_sittings(listing: list[Sitting], dates: list[str] | None = None) -> list[Sitting]:
    seen = set()
    if hansard.REPORT_OUT.exists():
        with open(hansard.REPORT_OUT, encoding="utf-8") as f:
            seen = {(r["chamber"], r["date"]) for r in csv.DictReader(f)}
    return [s for s in listing if (s.chamber, s.date) not in seen and (not dates or s.date in dates)]


def parse_new(new: list[Sitting], parse: Callable[[Sitting], tuple]) -> list[hansard.Report]:
    """Steps 1 and 2: each sitting's speeches, report row and extracts, appended in step."""
    reports = []
    for s in new:
        speeches, rep = parse(s)
        rows = [asdict(sp) for sp in speeches]
        enrich._append(hansard.SPEECHES_OUT, rows)
        enrich._append(enrich.UNITS, enrich.make_units(rows) if rows else [])
        new_file = not hansard.REPORT_OUT.exists()
        with open(hansard.REPORT_OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(hansard.REPORT_FIELDS)
            w.writerow(hansard.report_row(rep))
        reports.append(rep)
        print(f"{s.chamber} {s.date}: {rep.speeches} speeches {rep.note}", flush=True)
    return reports


def default_parse(s: Sitting, registers) -> tuple:
    if not s.pdf_path.lower().endswith(".pdf"):
        return hansard.parse_one(s, registers, "no PDF in the listing")
    try:
        fetch.get(s.url)
    except Exception as e:  # one file the site cannot serve is a finding, not a stop
        return hansard.parse_one(s, registers, f"download failed: {str(e)[:150]}")
    return hansard.parse_one(s, registers)


def pending_units(root: Path = config.INDEX) -> list[dict]:
    """Extracts whose sitting index.db does not hold yet."""
    con = index.connect(index.db_path(root))
    indexed = {f"{c}-{d}" for c, d in con.execute("SELECT DISTINCT chamber, date FROM chunks WHERE kind = 'debate'")}
    con.close()
    out = []
    for line in open(enrich.UNITS, encoding="utf-8"):
        uid = line[8:line.index('"', 8)]  # '{"id": "DR-2024-03-12-001", ...'
        if uid[:-4] not in indexed:
            out.append(json.loads(line))
    return out


def enrich_units(units: list[dict], call: Call, workers: int = 6,
                 fresh_from: dict[str, int] | None = None) -> dict[str, dict]:
    """Step 3: each extract's finished record, its commitments checked. A revised sitting's
    extracts (`fresh_from`) are asked again even when an older answer exists."""
    done = enrich._done(fresh_from)

    def ask(params: dict, job: str) -> dict:
        try:
            return call(params, job)
        except anthropic.APIError as e:
            return {"error": str(e)[:300], "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}

    def one(u: dict) -> None:
        out = ask(enrich.request(u), "ingest-enrich")
        enrich._append(enrich.RAW, [{"unit": u["id"], "endpoint": "messages", "prompt": enrich.PROMPT_VERSION, **out}])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, [u for u in units if u["id"] not in done]))
    done = enrich._done(fresh_from)
    first = {u["id"]: enrich.finish(u, done[u["id"]]["result"]) for u in units if u["id"] in done}

    checked = enrich._checks()
    todo = []
    for u in units:
        if u["id"] in first:
            its = [it for it in commit_check.items(u, first[u["id"]]) if it["key"] not in checked]
            if its:
                todo.append((u, its))

    def check(job: tuple[dict, list[dict]]) -> None:
        u, its = job
        out = ask(commit_check.request(u, its), "ingest-commit-check")
        enrich._append(enrich.CHECKS, commit_check.rows(u["id"], its, out, "messages"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(check, todo))
    checks = enrich._checks()
    records = {u["id"]: enrich.finish(u, done[u["id"]]["result"], checks) for u in units if u["id"] in done}
    have = set()
    if enrich.ENRICHED.exists():
        have = {uid for line in open(enrich.ENRICHED, encoding="utf-8")
                if (uid := line[10:line.index('"', 10)]) in records}  # '{"unit": "DR-...'
    enrich._append(enrich.ENRICHED, [r for uid, r in records.items() if uid not in have])
    return records


def link_bills(units: list[dict], by_name: dict[str, list[dict]]) -> dict[str, dict]:
    """Step 4: the bill links of every heading, new headings appended to bill_links.csv."""
    rows = list(csv.DictReader(open(links.OUT, encoding="utf-8"))) if links.OUT.exists() else []
    known = {r["heading"] for r in rows}
    new = []
    for h in sorted({u["topic"] for u in units if u["topic"]} - known):
        row = links.link(h, by_name)
        if row:
            new.append(row)
    if new:
        exists = links.OUT.exists()
        links.OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(links.OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=links.FIELDS)
            if not exists:
                w.writeheader()
            w.writerows(new)
    return {r["heading"]: r for r in rows + new if r["act"]}


def index_units(units: list[dict], records: dict[str, dict], bills: dict[str, dict], party, count,
                root: Path = config.INDEX, embedder=None) -> tuple[int, int]:
    """Step 5: chunk, append and embed; returns the new id range."""
    enriched = {uid: {"summary_en": r["summary_en"], "topics": r["topics"]} for uid, r in records.items()}
    start, end = index.append(chunk.debate_chunks(units, enriched, party, bills, count), index.db_path(root))
    sets = sorted((d.name.split("-")[1:] for d in root.glob("vectors-*-*") if d.is_dir()),
                  key=lambda sv: (sv[0], sv[1] != "h"))
    for size, variant in sets:
        index.embed(size, variant, root, embedder=embedder)
    return start, end


def index_pending(call: Call | None = None, party=None, count=None, by_name=None, root: Path = config.INDEX,
                  embedder=None, fresh_from: dict[str, int] | None = None) -> str:
    """Steps 3 to 5 for every extract whose sitting index.db does not hold yet."""
    units = pending_units(root)
    if not units:
        return "nothing to index"
    if call is None:
        client = enrich._client()
        call = lambda params, job: enrich.call(client, params, job)  # noqa: E731
    records = enrich_units(units, call, fresh_from=fresh_from)
    bills = link_bills(units, by_name if by_name is not None else links.acts_by_name())
    if party is None:
        from . import parties
        party = parties.lookup()
    start, end = index_units(units, records, bills, party, count or chunk.qwen_counter(), root, embedder)
    failed = [u["id"] for u in units if u["id"] not in records]
    return (f"{len(units)} extracts, {len(records)} enriched; chunks {start} to {end - 1} indexed"
            + (f"; no record yet for {', '.join(failed)}" if failed else ""))


def ingest(listing: list[Sitting], dates: list[str] | None = None, parse=None, call: Call | None = None,
           party=None, count=None, by_name=None, root: Path = config.INDEX, embedder=None,
           dry_run: bool = False, drafts_path: Path | None = None) -> str:
    new = new_sittings(listing, dates)
    if dry_run:
        return f"{len(new)} new sittings: " + ", ".join(f"{s.chamber} {s.date}" for s in new)
    if parse is None:
        registers = hansard.read_registers()
        parse = lambda s: default_parse(s, registers)  # noqa: E731
    reports = parse_new(new, parse)
    drafts.record(new, path=drafts_path)
    if not pending_units(root):
        return f"{len(new)} new sittings, nothing to index"
    done = index_pending(call, party, count, by_name, root, embedder)
    return f"{len(new)} new sittings ({sum(r.speeches for r in reports)} speeches); {done}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dates", nargs="+", metavar="ISO")
    ap.add_argument("--no-refresh", action="store_true", help="use data/sittings.csv as it is")
    ap.add_argument("--dry-run", action="store_true", help="list the new sittings and stop")
    a = ap.parse_args()
    if a.no_refresh:
        listing = sittings.read_csv()
    else:
        listing = sittings.list_sittings()
        sittings.write_csv(listing)
    print(ingest(listing, a.dates, dry_run=a.dry_run))


if __name__ == "__main__":
    main()
