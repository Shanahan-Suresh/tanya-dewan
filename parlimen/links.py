"""Links between the law and the debates.

Bill to Act. A bill's debate sits under an agenda heading such as "RANG UNDANG-UNDANG KERJA
(PINDAAN) 2022 Bacaan Kali Yang Kedua dan Ketiga". The bill's name, less "(PINDAAN)" (amendment)
or "(PEMANSUHAN)" (repeal) and its year, is the name of the Act it changes ("AKTA KERJA 1955"); a
new Act keeps the bill's name and year ("CUKAI JUALAN 2018" became "AKTA CUKAI JUALAN 2018").
Supply bills (PERBEKALAN) pass no principal Act and stay unlinked.

Cross-references. A section that names another section of its own Act ("subsection 13(2)",
"seksyen 60A") links to it; a reference followed by another Act's name ("section 5 of the
Contracts Act 1950") does not.

Run:  python -m parlimen.links   ->  data/index/bill_links.csv (one row per agenda heading with
                                     its Act, or none) and a match report
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass

from . import config

ACTS_CSV = config.DATA / "acts.csv"
OUT = config.INDEX / "bill_links.csv"

_HEAD = re.compile(r"^(?:RANG UNDANG-UNDANG\s+)+", re.I)
_STAGE = re.compile(r"\s+(?:Bacaan\b|Jawatankuasa\b|Usul\b|DAN USUL\b|dan\s+Usul\b).*$", re.I)
_CHANGE = re.compile(r"\((PINDAAN(?: NO\.? ?\d+)?|PEMANSUHAN|PINDAAN DAN PEMANSUHAN)\)", re.I)
_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\s*$")


@dataclass
class Bill:
    heading: str   # the agenda heading as the record gives it
    title: str     # the bill's name: "KERJA (PINDAAN) 2022"
    base: str      # the name to look for among the Acts: "KERJA"
    year: str
    change: str    # "amend", "repeal" or "new"


def bill(heading: str) -> Bill | None:
    """The bill an agenda heading debates, or None when the heading is not a bill's."""
    if not _HEAD.match(heading or ""):
        return None
    title = _HEAD.sub("", heading.strip())
    title = re.sub(r"^DIBAWA KE DALAM MESYUARAT\s+", "", title, flags=re.I)  # bills brought in
    title = _STAGE.sub("", _HEAD.sub("", title)).strip(" .")
    title = re.sub(r"^AKTA\s+", "", title, flags=re.I)  # "RANG UNDANG-UNDANG AKTA ANTIBERITA ..."
    title = re.sub(r"\(PINDAAN\s+(\d{4})\)", r"(PINDAAN) \1", title, flags=re.I)  # "(PINDAAN 2022)"
    m = _CHANGE.search(title)
    change = "new" if not m else ("repeal" if "PEMANSUHAN" in m.group(1).upper() else "amend")
    y = _YEAR.search(title)
    base = _CHANGE.sub("", title)
    base = re.sub(r"\(NO\.?\s*\d+\)", "", base, flags=re.I)  # "(NO. 2)": the year's second bill
    base = _YEAR.sub("", base.strip()).strip(" ,")
    return Bill(heading, title, _name(base), y.group(1) if y else "", change)


def _name(text: str) -> str:
    """A name to compare: upper case, letters and digits only, so "PENCETAKANTEKS" meets
    "PENCETAKAN TEKS" and "MALAYSIA(PEMBUBARAN)" meets "MALAYSIA (PEMBUBARAN)"."""
    return re.sub(r"[^A-Z0-9]", "", text.upper().replace("’", "'"))


def _act_key(title: str) -> tuple[str, str]:
    """(name, year) of a Malay Act title: "*AKTA KERJA 1955" -> ("AKTAKERJA" less AKTA, "1955")."""
    t = re.sub(r"\s*\((?:Disemak|Revised)[^)]*\)\s*$", "", title.strip(" *"), flags=re.I)
    t = re.sub(r"^AKTA\s+", "", t, flags=re.I)
    y = _YEAR.search(t)
    return _name(_YEAR.sub("", t).strip(" ,")), (y.group(1) if y else "")


def acts() -> list[dict]:
    return list(csv.DictReader(open(ACTS_CSV, encoding="utf-8")))


def match(b: Bill, by_name: dict[str, list[dict]]) -> dict | None:
    """The Act a bill changes or becomes: the one Act with the bill's name; for a new Act, the one
    with its year too."""
    found = by_name.get(b.base, [])
    if b.change == "new":
        found = [a for a in found if _act_key(a["title_bm"])[1] == b.year] or found
    if len(found) == 1:
        return found[0]
    in_force = [a for a in found if a["status"] == "in force"]
    return in_force[0] if len(in_force) == 1 else None


# ---------- cross-references ----------

_XREF = re.compile(r"\b(?:sub)?(?:sections?|seksyen)\s+(\d+[A-Z]{0,3})\b", re.I)
# What follows a reference to another law: "(2) of the Contracts Act 1950", "Akta Kontrak 1950",
# "of the Penal Code". "of this Act" and "Akta ini" are the section's own Act.
_OTHER_LAW = re.compile(r"\s*(?:\([^)]{1,6}\)\s*)*(?:,?\s*(?:of|in|under|dalam|di bawah)\s+(?:the\s+)?)?"
                        r"(?!this\b|ini\b)(?:[A-Z][\w'’()-]*\s+){0,10}?(?:Act|Akta|Code|Kanun|Ordinance|Ordinan|Enactment|Enakmen)\b(?!\s+ini\b)")


def xrefs(text: str, own: str) -> list[str]:
    """Section numbers of the same Act that a section's text names, in order, without its own."""
    out: list[str] = []
    for m in _XREF.finditer(text):
        n = m.group(1).upper()
        tail = _OTHER_LAW.match(text, m.end())
        if tail and not re.search(r"\b(?:this|ini)\b", tail.group(0)):
            continue
        if n != own.upper() and n not in out:
            out.append(n)
    return out


# ---------- command ----------

FIELDS = ["heading", "title", "base", "year", "change", "act", "act_title_bi", "act_title_bm", "result"]


def acts_by_name() -> dict[str, list[dict]]:
    by_name: dict[str, list[dict]] = {}
    for a in acts():
        by_name.setdefault(_act_key(a["title_bm"])[0], []).append(a)
    return by_name


def link(heading: str, by_name: dict[str, list[dict]]) -> dict | None:
    """A bill_links.csv row for an agenda heading, or None when the heading is not a bill's."""
    b = bill(heading)
    if b is None:
        return None
    a = match(b, by_name)
    kind = ("linked" if a else "supply" if b.base.startswith(("PERBEKALAN", "KUMPULANWANG"))
            else "not an act" if b.base.startswith(("PERLEMBAGAAN", "PERLEMBAGAN", "ORDINAN", "KAEDAH"))
            else "unlinked")
    return {"heading": heading, "title": b.title, "base": b.base, "year": b.year, "change": b.change,
            "act": a["number"] if a else "", "act_title_bi": a["title_bi"] if a else "",
            "act_title_bm": a["title_bm"] if a else "", "result": kind}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    by_name = acts_by_name()
    headings: Counter = Counter()
    for line in open(config.DATA / "enrich" / "units.jsonl", encoding="utf-8"):
        start = line.find('"topic": "')
        if start < 0:
            continue
        u = json.loads(line)
        if u["topic"]:
            headings[u["topic"]] += 1
    rows, kinds = [], Counter()
    for h in sorted(headings):
        row = link(h, by_name)
        if row is None:
            continue
        kinds[row["result"]] += 1
        rows.append(row)
    config.INDEX.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} bill headings: {dict(kinds)} -> {OUT}")


if __name__ == "__main__":
    main()
