"""Which sittings are the unrevised draft, and the weekly re-check that brings in a revised text.

Parliament publishes a Dewan Rakyat sitting first as a draft: page 1 of the PDF opens "Naskhah
belum disemak" (text not yet revised). The revised text later replaces the PDF at the same URL, and
some drafts are never revised (DR 2019-11-06 is still a draft). The Special Chamber's PDFs never
print the line, so no Special Chamber sitting is flagged.

`data/drafts.csv` holds one row per sitting with a cached PDF: chamber, date, draft (1 or 0), the
sha1 of the cached PDF, the date of the last check, and `redo_from` while a revised sitting is
being processed again (the line count of data/enrich/raw.jsonl when it started: only answers after
that line count for the sitting's extracts).

- `scan` reads page 1 of every cached sitting PDF and writes the file afresh.
- `recheck` downloads the PDF of each draft sitting again (one request at a time, as fetch.py
  does). Bytes that match the cache only update the check date. Changed bytes replace the cache,
  and the sitting is processed again: parse, put its speeches, extracts and report row in place,
  drop its old records, retire its chunks in index.db, then enrich, check, chunk and embed as an
  ingest does. A run that stops resumes from `redo_from`. Rebuild data/site.db after it
  (`python -m parlimen.records build`) and restart the site.

By default only drafts from the last RECHECK_DAYS are fetched; `--all` fetches every draft.

Run:  python -m parlimen.drafts scan
      python -m parlimen.drafts recheck [--all] [--dry-run]
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from . import config, enrich, fetch, hansard, index, sittings
from .sittings import Sitting

OUT = config.DATA / "drafts.csv"
FIELDS = ["chamber", "date", "draft", "sha1", "checked", "redo_from"]
MARK = re.compile(r"belum\s+disemak", re.I)
RECHECK_DAYS = 365


def is_draft(pdf: bytes | Path) -> bool:
    """True when page 1 of the PDF carries "Naskhah belum disemak"."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf if isinstance(pdf, Path) else bytes(pdf))
    try:
        if len(doc) == 0:
            return False
        page = doc[0]
        text = page.get_textpage().get_text_range()
        page.close()
        return bool(MARK.search(text))
    finally:
        doc.close()


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def read(path: Path | None = None) -> dict[tuple[str, str], dict]:
    path = path or OUT
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["chamber"], r["date"]): r for r in csv.DictReader(f)}


def write(rows: dict[tuple[str, str], dict], path: Path | None = None) -> None:
    path = path or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f, "") for f in FIELDS})
    tmp.replace(path)


def row_for(s: Sitting, data: bytes, checked: str) -> dict:
    return {"chamber": s.chamber, "date": s.date, "draft": "1" if is_draft(data) else "0", "sha1": sha1(data),
            "checked": checked, "redo_from": ""}


def record(new: list[Sitting], today: str | None = None, path: Path | None = None) -> None:
    """Add the draft flag of each sitting whose PDF is cached (an ingest calls this for new sittings)."""
    cached = [(s, p) for s in new if (p := fetch.cache_path(s.url)).suffix == ".pdf" and p.exists()]
    if not cached:
        return
    rows = read(path)
    today = today or date.today().isoformat()
    for s, p in cached:
        rows[(s.chamber, s.date)] = row_for(s, p.read_bytes(), today)
    write(rows, path)


def scan(listing: list[Sitting], today: str | None = None, path: Path | None = None) -> dict[str, int]:
    rows: dict[tuple[str, str], dict] = {}
    old = read(path)
    today = today or date.today().isoformat()
    for s in listing:
        p = fetch.cache_path(s.url)
        if p.suffix != ".pdf" or not p.exists():
            continue
        r = row_for(s, p.read_bytes(), today)
        r["redo_from"] = old.get((s.chamber, s.date), {}).get("redo_from", "")
        rows[(s.chamber, s.date)] = r
    write(rows, path)
    return {"sittings": len(rows), "drafts": sum(r["draft"] == "1" for r in rows.values())}


# ---------- processing a revised sitting again ----------

def replace_rows(path: Path, keep: Callable[[dict], bool], new_rows: list[dict]) -> None:
    """Rewrite a JSONL file with the rows `keep` rejects swapped for `new_rows`, at the first one's
    place (at the end when no row was rejected)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    placed = False
    with open(path, encoding="utf-8") as src, open(tmp, "w", encoding="utf-8") as out:
        for line in src:
            if keep(json.loads(line)):
                out.write(line)
            elif not placed:
                out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new_rows)
                placed = True
        if not placed:
            out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new_rows)
    tmp.replace(path)


def _replace_report(rep: hansard.Report) -> None:
    with open(hansard.REPORT_OUT, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    new = hansard.report_row(rep)
    out = [rows[0]] + [new if r[:2] == new[:2] else r for r in rows[1:]]
    if new not in out:
        out.append(new)
    tmp = hansard.REPORT_OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(out)
    tmp.replace(hansard.REPORT_OUT)


def _raw_lines() -> int:
    if not enrich.RAW.exists():
        return 0
    with open(enrich.RAW, "rb") as f:
        return sum(1 for _ in f)


def replace_sitting(s: Sitting, parse: Callable[[Sitting], tuple], root: Path = config.INDEX) -> int:
    """Put a revised sitting's parse in place of the old one and take its old records and chunks out
    of use. Returns the raw-answer line count from which its extracts count as enriched."""
    speeches, rep = parse(s)
    rows = [asdict(sp) for sp in speeches]
    key = (s.chamber, s.date)

    def other(r: dict) -> bool:
        return (r["chamber"], r["date"]) != key

    redo_from = _raw_lines()
    replace_rows(hansard.SPEECHES_OUT, other, rows)
    replace_rows(enrich.UNITS, other, enrich.make_units(rows) if rows else [])
    _replace_report(rep)
    prefix = f"{s.chamber}-{s.date}-"
    if enrich.ENRICHED.exists():
        replace_rows(enrich.ENRICHED, lambda r: not r["unit"].startswith(prefix), [])
    index.retire(s.chamber, s.date, index.db_path(root))
    print(f"{s.chamber} {s.date}: revised text parsed, {rep.speeches} speeches {rep.note}", flush=True)
    return redo_from


def fresh_from(rows: dict[tuple[str, str], dict]) -> dict[str, int]:
    """For each extract of a sitting being processed again: the raw-answer line its answer must come after."""
    marks = {f"{c}-{d}-": int(r["redo_from"]) for (c, d), r in rows.items() if r.get("redo_from")}
    if not marks:
        return {}
    out = {}
    for u in enrich._read(enrich.UNITS):
        m = marks.get(u["id"][:-3])
        if m is not None:
            out[u["id"]] = m
    return out


def recheck(listing: list[Sitting], download: Callable[[str], bytes] | None = None,
            process: Callable[[dict[str, int]], str] | None = None, parse: Callable[[Sitting], tuple] | None = None,
            today: str | None = None, days: int | None = RECHECK_DAYS, dry_run: bool = False,
            root: Path = config.INDEX, path: Path | None = None) -> str:
    """Fetch each draft sitting's PDF again; process the ones whose bytes changed."""
    rows = read(path)
    today = today or date.today().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=days)).isoformat() if days else ""
    by_key = {(s.chamber, s.date): s for s in listing}
    due = [by_key[k] for k, r in sorted(rows.items())
           if r["draft"] == "1" and k in by_key and k[1] >= since and not r.get("redo_from")]
    if dry_run:
        return f"{len(due)} draft sittings to fetch again: " + ", ".join(f"{s.chamber} {s.date}" for s in due)
    if download is None:
        download = lambda url: fetch.client().get(url).raise_for_status().content  # noqa: E731
    if parse is None:
        registers = hansard.read_registers()
        parse = lambda s: hansard.parse_one(s, registers)  # noqa: E731
    revised, failed = [], []
    for s in due:
        k = (s.chamber, s.date)
        try:
            fetch._wait_turn(urlsplit(s.url).netloc)
            data = download(s.url)
        except Exception as e:  # a file the site cannot serve today is checked next week
            failed.append(f"{s.chamber} {s.date} ({str(e)[:80]})")
            continue
        if sha1(data) == rows[k]["sha1"]:
            rows[k]["checked"] = today
            continue
        p = fetch.cache_path(s.url)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(p)
        rows[k] = row_for(s, data, today)
        rows[k]["redo_from"] = str(replace_sitting(s, parse, root))
        write(rows, path)  # the mark is on disk before any paid step
        revised.append(f"{s.chamber} {s.date}" + ("" if rows[k]["draft"] == "1" else " (now revised)"))
    write(rows, path)
    summary = (f"{len(due)} draft sittings fetched again: {len(revised)} changed"
               + (f" ({', '.join(revised)})" if revised else "")
               + (f"; {len(failed)} failed: {', '.join(failed)}" if failed else ""))
    pending = fresh_from(rows)
    if pending:
        if process is None:
            from . import ingest
            process = lambda fresh: ingest.index_pending(root=root, fresh_from=fresh)  # noqa: E731
        summary += "; " + process(pending)
        for r in rows.values():
            r["redo_from"] = ""
        write(rows, path)
    return summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    rc = sub.add_parser("recheck")
    rc.add_argument("--all", action="store_true", help=f"every draft, not only the last {RECHECK_DAYS} days")
    rc.add_argument("--dry-run", action="store_true", help="list the drafts to fetch and stop")
    a = ap.parse_args()
    listing = sittings.read_csv()
    if a.cmd == "scan":
        print(scan(listing))
    else:
        print(recheck(listing, days=None if a.all else RECHECK_DAYS, dry_run=a.dry_run))


if __name__ == "__main__":
    main()
