"""Consolidated Act texts from the Laws of Malaysia portal (lom.agc.gov.my), fetched in Chrome.

The portal's list of updated Acts (`principal.php?type=updated`) loads its rows as an encrypted
listing that only the portal's own script reads. This module never decrypts it: it drives the
installed Chrome, lets the page draw its table, and reads the rows a visitor sees. Each row gives
the Act number, the English and Malay titles, the date the text is consolidated to ("As At"),
and one PDF link per language. The PDFs are fetched through the same browser session, one at a
time, and cached once per Act, language and consolidation date.

Run: python -m parlimen.acts [--limit N]
"""

import argparse
import csv
import hashlib
import html
import json
import re
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from . import config

_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DATE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
_TAG = re.compile(r"<[^>]+>")

LISTING = config.ACTS / "listing.json"  # raw rows as drawn by the portal


# Label after a title link -> (language, status). Repealed and replaced Acts carry a note in
# place of the date.
_LABELS = (
    ("As At", "BI", "in force"),
    ("Sebagaimana Pada", "BM", "in force"),
    ("(Repealed by", "BI", "repealed"),
    ("(Dimansuhkan oleh", "BM", "repealed"),
    ("(Superseded by", "BI", "superseded"),
    ("(Diganti oleh", "BM", "superseded"),
)


@dataclass
class Act:
    number: str        # Act number as listed, e.g. "886" or "NO. 26 OF 1963"
    title_bi: str
    title_bm: str
    status: str        # "in force", "repealed" or "superseded"
    note: str          # the portal's note on a repealed Act, e.g. "Repealed by Act 805"
    as_at: str         # ISO date the consolidated text is current to; "" for a repealed Act
    pdf_bi: str        # absolute processFile.php link, or "" when the row has none
    pdf_bm: str
    kind_bi: str       # "printed" (a reprint) or "online" (a reprint published online only)
    kind_bm: str

    def pdf_path(self, lang: str) -> Path:
        folder = re.sub(r"[^A-Za-z0-9]+", "-", self.number).strip("-")
        return config.ACTS / folder / f"{lang}-{self.as_at or self.status}.pdf"


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", fragment)).split())


def parse_row(cells: list[str]) -> Act:
    """Build an Act from the inner HTML of one table row's three cells.

    Cell 1 holds the title links, one English and one Malay, in either order. Each is followed
    by a label (see _LABELS) that names its language. An unlabelled title takes the language
    the other title does not have: these rows list an English text only. A row that lists two
    versions of one language keeps the later one. Cell 2 holds the PDF links; each link's icon
    names the language and kind (pdf-en-printed, pdf-ms-online, ...). A link with no icon is
    skipped. Any other break from this pattern raises, so the listing is never read by guesswork.
    """
    number = _text(cells[0])
    found = []  # (language or None, title, status, date, note)
    for part in cells[1].split("<br>"):
        link = _LINK.search(part)
        if not link:
            continue
        label = _text(part[link.end():])
        match = next((x for x in _LABELS if label.startswith(x[0])), None)
        if match is None and label:
            raise ValueError(f"Act {number}: unknown title label {label!r}")
        lang, status = (match[1], match[2]) if match else (None, "")
        m = _DATE.search(label) if status == "in force" else None
        date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
        note = label.strip("()") if status in ("repealed", "superseded") else ""
        found.append([lang, _text(link.group(2)), status, date, note])

    # Titles come in pairs (English and Malay of one version), so an unlabelled title takes
    # the language its partner does not have.
    for i, f in enumerate(found):
        if f[0] is None:
            partner = found[i ^ 1] if (i ^ 1) < len(found) else None
            if partner is None or partner[0] is None:
                raise ValueError(f"Act {number}: cannot tell the language of {f[1]!r}")
            f[0] = "BM" if partner[0] == "BI" else "BI"
    best = {}
    for f in found:
        if f[0] not in best or f[3] > best[f[0]][3]:
            best[f[0]] = f
    labelled = [f for f in best.values() if f[2]]
    status = labelled[0][2] if labelled else "in force"
    as_at = max((f[3] for f in best.values()), default="")
    notes = [best[lang][4] for lang in ("BI", "BM") if lang in best and best[lang][4]]
    note = notes[0] if notes else ""

    pdf = {"BI": ("", ""), "BM": ("", "")}
    for href, inner in _LINK.findall(cells[2]):
        icon = re.search(r"pdf-(en|ms)-(printed|online)\.png", inner)
        if icon is None:
            if "<img" in inner:
                raise ValueError(f"Act {number}: unknown PDF icon in {inner[:120]!r}")
            continue
        lang = "BI" if icon.group(1) == "en" else "BM"
        if pdf[lang][0] and pdf[lang][1] == "online":
            continue  # a row with two texts in one language: the online reprint is the later one
        pdf[lang] = (config.LOM_SITE + "/" + html.unescape(href).lstrip("/"), icon.group(2))
    return Act(
        number,
        best.get("BI", [None, ""])[1],
        best.get("BM", [None, ""])[1],
        status, note, as_at,
        pdf["BI"][0], pdf["BM"][0], pdf["BI"][1], pdf["BM"][1],
    )


def _draw(page, action) -> None:
    """Run a table action and wait until the page has fetched and drawn the new rows.

    The table is server-side: every page change is one request to the portal, so the
    pause between list pages is the same as between PDFs.
    """
    with page.expect_response(lambda r: "json-updated" in r.url, timeout=120_000):
        action()
    page.wait_for_function(
        "() => !document.querySelector('#data-updated_processing')"
        " || getComputedStyle(document.querySelector('#data-updated_processing')).display === 'none'",
        timeout=60_000,
    )
    time.sleep(config.ACT_INTERVAL_S)


def fetch_listing(page) -> list[list[str]]:
    """Read every row of the updated-Acts table as the page draws it, 100 rows per page.

    Returns each row as the inner HTML of its cells and saves them to LISTING, so the parser
    can be changed and re-run without asking the portal again.
    """
    page.goto(config.LOM_UPDATED, wait_until="networkidle", timeout=120_000)
    page.wait_for_selector("#data-updated tbody tr", timeout=60_000)
    _draw(page, lambda: page.select_option("select[name=data-updated_length] >> nth=0", "100"))
    info = page.evaluate("() => $('#data-updated').DataTable().page.info()")
    rows: list[list[str]] = []
    for n in range(info["pages"]):
        if n:
            _draw(page, lambda: page.evaluate(f"() => $('#data-updated').DataTable().page({n}).draw('page')"))
        rows.extend(page.eval_on_selector_all(
            "#data-updated tbody tr",
            "trs => trs.map(tr => Array.from(tr.cells).map(td => td.innerHTML))",
        ))
    rows = [cells for cells in rows if len(cells) >= 3]
    numbers = {_text(cells[0]) for cells in rows}
    if len(rows) != info["recordsTotal"] or len(numbers) != len(rows):
        raise RuntimeError(
            f"read {len(rows)} rows ({len(numbers)} distinct), the table reports {info['recordsTotal']}"
        )
    config.ACTS.mkdir(parents=True, exist_ok=True)
    LISTING.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def write_csv(acts: list[Act], path=None) -> None:
    path = path or config.DATA / "acts.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[x.name for x in fields(Act)])
        w.writeheader()
        w.writerows(asdict(a) for a in acts)


def download(context, acts: list[Act], log_path=None) -> dict[str, int]:
    """Fetch each Act's PDFs not yet cached, one at a time, ACT_INTERVAL_S apart."""
    log_path = log_path or config.ACTS / "downloads.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"cached": 0, "fetched": 0, "missing": 0, "failed": 0}
    last = 0.0
    with open(log_path, "a", encoding="utf-8") as log:
        for act in acts:
            for lang, url in (("BI", act.pdf_bi), ("BM", act.pdf_bm)):
                path = act.pdf_path(lang)
                if not url:
                    counts["missing"] += 1
                    continue
                if path.exists():
                    counts["cached"] += 1
                    continue
                gap = time.monotonic() - last
                if gap < config.ACT_INTERVAL_S:
                    time.sleep(config.ACT_INTERVAL_S - gap)
                last = time.monotonic()
                entry = {"act": act.number, "lang": lang, "as_at": act.as_at,
                         "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                try:
                    r = context.request.get(url, timeout=180_000)
                    body = r.body()
                    ok = r.status == 200 and body[:5] == b"%PDF-"
                    entry.update(status=r.status, bytes=len(body))
                except Exception as e:  # network errors are logged and retried on the next run
                    ok, body = False, b""
                    entry.update(error=str(e)[:200])
                if ok:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".part")
                    tmp.write_bytes(body)
                    tmp.replace(path)
                    entry["sha256"] = hashlib.sha256(body).hexdigest()
                    counts["fetched"] += 1
                else:
                    counts["failed"] += 1
                log.write(json.dumps(entry) + "\n")
                log.flush()
    return counts


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, help="download only the first N Acts of the listing")
    ap.add_argument("--refresh-listing", action="store_true", help="read the listing from the portal again")
    ap.add_argument("--parse-only", action="store_true", help="parse the cached listing, download nothing")
    ap.add_argument("--only", nargs="+", metavar="NUMBER", help="download only these Act numbers")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()
        if args.refresh_listing or not LISTING.exists():
            rows = fetch_listing(context.new_page())
        else:
            rows = json.loads(LISTING.read_text(encoding="utf-8"))
        acts = [parse_row(cells) for cells in rows]
        write_csv(acts)
        print(f"{len(acts)} Acts listed, written to data/acts.csv")
        if not args.parse_only:
            chosen = [a for a in acts if a.number in args.only] if args.only else acts
            chosen = chosen[: args.limit] if args.limit else chosen
            print(json.dumps(download(context, chosen)))
        browser.close()


if __name__ == "__main__":
    main()
