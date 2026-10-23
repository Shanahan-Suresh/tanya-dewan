"""The list of Dewan Rakyat sitting days, read from Parliament's own Hansard archive.

Two chambers keep a Hansard: the Dewan Rakyat itself ("DR") and its Special Chamber, the Dewan
Khas ("KK"). Each archive page is a tree: Parliament > term (Penggal) > meeting (Mesyuarat) >
sitting day. Each level loads as XML from `<archive>&ajx=1&id=<node id>`. The meeting in progress is
not in the tree yet; it is listed on the plain Hansard page instead. File names do not always
follow DR-ddmmyyyy.pdf (DR-06102026..pdf exists), so the PDF path is taken from the listing,
never built from the date.
"""

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, fields
from datetime import date

from . import config, fetch

MALAY_MONTHS = {
    "jan": 1, "januari": 1, "feb": 2, "februari": 2, "mac": 3, "apr": 4, "april": 4,
    "mei": 5, "jun": 6, "jul": 7, "julai": 7, "ogos": 8, "ogo": 8, "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "nov": 11, "november": 11, "dis": 12, "disember": 12,
}

_LOAD_RESULT = re.compile(r"loadResult\('([^']+)'")
_FILE_DATE = re.compile(r"DR-(\d{2})(\d{2})(\d{4})")
_TEXT_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


@dataclass
class Sitting:
    date: str          # ISO date
    chamber: str       # "DR" (Dewan Rakyat) or "KK" (Dewan Khas, the Special Chamber)
    parliament: int
    term: str          # e.g. "Penggal Kelima"
    meeting: str       # e.g. "Mesyuarat Kedua (22/06/2026 - 16/07/2026)"
    pdf_path: str      # path on parlimen.gov.my, as listed
    source: str        # "archive" or "current"

    @property
    def url(self) -> str:
        return config.PARLIAMENT_SITE + self.pdf_path


def parse_date(text: str, pdf_path: str) -> date:
    """The sitting date, from the listed text ("22 Jun 2026") or else the file name."""
    m = _TEXT_DATE.search(text)
    if m and m.group(2).lower() in MALAY_MONTHS:
        return date(int(m.group(3)), MALAY_MONTHS[m.group(2).lower()], int(m.group(1)))
    m = _FILE_DATE.search(pdf_path)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    raise ValueError(f"no date in {text!r} or {pdf_path!r}")


def parse_tree(xml_bytes: bytes) -> list[dict]:
    """The child items of one tree node: id, text, whether it has children, its link."""
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("item"):
        url = ""
        for ud in item.findall("userdata"):
            if ud.get("name") == "myurl":
                url = (ud.text or "").strip()
        m = _LOAD_RESULT.search(url)
        items.append({
            "id": item.get("id"),
            "text": item.get("text", ""),
            "has_children": item.get("child") == "1",
            "pdf_path": m.group(1) if m else "",
        })
    return items


def parse_current(html: str) -> tuple[str, list[tuple[str, str]]]:
    """The meeting in progress on the plain Hansard page: its title and (date text, pdf path)."""
    title = ""
    m = re.search(r'boxMesyuaratTextA"><strong>([^<]+)</strong>', html)
    if m:
        title = m.group(1).strip()
    days = re.findall(r"loadResult\('([^']+)','[^']*'\);\">([^<]+)</a>", html)
    return title, [(text.strip(), path) for path, text in days]


def _node(chamber: str, node_id: str) -> list[dict]:
    return parse_tree(fetch.get(f"{config.HANSARD_TREES[chamber]}&ajx=1&id={node_id}", refresh=True))


def walk_archive(chamber: str, parliament: int) -> list[Sitting]:
    out = []
    for term in _node(chamber, f"0_{parliament}"):
        for meeting in _node(chamber, term["id"]):
            for day in _node(chamber, meeting["id"]):
                if not day["pdf_path"]:
                    continue
                out.append(Sitting(
                    date=parse_date(day["text"], day["pdf_path"]).isoformat(), chamber=chamber,
                    parliament=parliament, term=term["text"], meeting=meeting["text"],
                    pdf_path=day["pdf_path"], source="archive",
                ))
    return out


_ORDINAL = {"Keempat Belas": 14, "Kelima Belas": 15, "Keenam Belas": 16}


def current_meeting(chamber: str) -> list[Sitting]:
    page = config.HANSARD_TREES[chamber].replace("&arkib=yes", "")
    title, days = parse_current(fetch.get(page, refresh=True).decode("utf-8", "replace"))
    parliament = next((n for word, n in _ORDINAL.items() if f"Parlimen {word}" in title), 0)
    term = re.search(r"(Penggal \w+)", title)
    return [
        Sitting(date=parse_date(text, path).isoformat(), chamber=chamber, parliament=parliament,
                term=term.group(1) if term else "", meeting=title, pdf_path=path, source="current")
        for text, path in days
    ]


def list_sittings() -> list[Sitting]:
    rows: dict[str, Sitting] = {}
    for chamber in config.HANSARD_TREES:
        for p in config.PARLIAMENTS:
            for s in walk_archive(chamber, p):
                rows.setdefault(s.pdf_path, s)
        for s in current_meeting(chamber):
            rows.setdefault(s.pdf_path, s)
    return sorted(rows.values(), key=lambda s: (s.date, s.chamber, s.pdf_path))


def write_csv(rows: list[Sitting], path=None) -> None:
    path = path or config.DATA / "sittings.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[x.name for x in fields(Sitting)])
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def read_csv(path=None) -> list[Sitting]:
    path = path or config.DATA / "sittings.csv"
    with open(path, encoding="utf-8") as f:
        return [Sitting(**{**r, "parliament": int(r["parliament"])}) for r in csv.DictReader(f)]


if __name__ == "__main__":
    rows = list_sittings()
    write_csv(rows)
    counts = {c: sum(r.chamber == c for r in rows) for c in config.HANSARD_TREES}
    print(f"{len(rows)} sitting days {counts} written to {config.DATA / 'sittings.csv'}")
