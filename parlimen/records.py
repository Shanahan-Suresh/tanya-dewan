"""The page database: every record the site and the MCP server show, in one SQLite file.

`data/site.db` is built from the files the pipeline writes and holds no model output that the
pipeline did not already check:
- `acts`, `sections`: each Act's titles, reprint date, official PDFs and its sections in order;
- `sittings`, `units`, `speeches`: each sitting (with `draft` = 1 while Parliament's PDF is the
  unrevised draft, from `data/drafts.csv`), its agenda extracts (with the AI summaries and
  topics) and the verbatim speeches with speaker, seat, party on the day, page and time;
- `qa`, `commitments`: the question-answer pairs and the checked commitments, each with the office
  of the minister who spoke (`office`, read from the speech label, or from the same person's label
  on the nearest sitting when the label names no office) and its ministry;
- `members`, `member_seats`, `member_parties`: one MP per name key (`hansard._norm_name`), the seat
  in each Parliament and the party spells of that seat (`data/parties.csv`);
- `bills`: each bill heading's bill and the Act it made or changed (`data/index/bill_links.csv`).

Ids are stable: an Act section is (act, lang, number), an extract is its unit id
("DR-2024-03-05-012"), a speech is (unit, seq), a pair is "<unit>-q<n>", a commitment
"<unit>-c<n>", an MP the slug of the name key, a bill the slug of its title, a topic its slug.

Run:  python -m parlimen.records build    (about two minutes; rerun after an ingest)
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
import threading
import time
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from . import config, drafts, enrich, hansard, links, parties

SITE_DB = config.DATA / "site.db"
PAGE_SIZE = 50
# Joins the agenda heading into a page of commitments or question-answer pairs.
BUSINESS = "SELECT x.*, u.business FROM ({q}) x JOIN units u ON u.id = x.unit ORDER BY x.date DESC, x.id"
OFFICE_DAYS = 400  # an office seen on another sitting holds for a commitment this close in time
# One MP whose two name keys share a seat but not their words (checked against the seat's record).
SAME_PERSON = {"mohd najib abd razak": "mohd najib abdul razak", "p prabakaran": "prabakaran m parameswaran",
               "r sivarasa": "sivarasa rasiah", "wong kah who": "wong kah woh"}
# One MP under a new name: the record and the page use the name she goes by now. Sepang's MP is
# "Raj Munni Sabu @ Aiman Athirah" in the 2022 election results (data/raw/wikipedia); Hansard
# labels her Raj Munni to March 2025 and Aiman Athirah from then, in the same deputy minister post.
RENAMED = {"raj munni sabu": "aiman athirah sabu"}

SCHEMA = """
CREATE TABLE acts (number TEXT PRIMARY KEY, title_bi TEXT, title_bm TEXT, status TEXT, as_at TEXT,
                   pdf_bi TEXT, pdf_bm TEXT, langs TEXT);
CREATE TABLE sections (act TEXT, lang TEXT, number TEXT, ord INTEGER, heading TEXT, part TEXT,
                       part_title TEXT, chapter TEXT, chapter_title TEXT, text TEXT, notes TEXT,
                       page_start INTEGER, page_end INTEGER, source TEXT, PRIMARY KEY (act, lang, number));
CREATE TABLE sittings (chamber TEXT, date TEXT, parliament INTEGER, term TEXT, meeting TEXT, pdf TEXT,
                       draft INTEGER, PRIMARY KEY (chamber, date));
CREATE TABLE units (id TEXT PRIMARY KEY, chamber TEXT, date TEXT, parliament INTEGER, ord INTEGER,
                    business TEXT, summary_en TEXT, summary_ms TEXT, topics TEXT, entities TEXT,
                    bill TEXT, act TEXT, speeches INTEGER, page_start INTEGER);
CREATE INDEX units_sitting ON units (chamber, date, ord);
CREATE INDEX units_bill ON units (bill);
CREATE INDEX units_act ON units (act);
CREATE TABLE unit_topics (unit TEXT, topic TEXT, name TEXT, date TEXT);
CREATE INDEX unit_topics_topic ON unit_topics (topic, date, unit);
CREATE TABLE speeches (unit TEXT, seq INTEGER, label TEXT, name TEXT, seat TEXT, role TEXT, senator INTEGER,
                       party TEXT, member TEXT, page_start INTEGER, page_end INTEGER, time TEXT,
                       question_no TEXT, text TEXT, chars INTEGER, PRIMARY KEY (unit, seq));
CREATE INDEX speeches_member ON speeches (member, chars, unit, seq);
CREATE TABLE qa (id TEXT PRIMARY KEY, unit TEXT, chamber TEXT, date TEXT, parliament INTEGER,
                 asker TEXT, asker_seat TEXT, asker_member TEXT, asker_seq INTEGER,
                 answerer TEXT, answerer_seat TEXT, answerer_member TEXT, answerer_seq INTEGER,
                 office TEXT, ministry TEXT, question TEXT, answer TEXT, figures TEXT, topics TEXT);
CREATE INDEX qa_date ON qa (date);
CREATE INDEX qa_asker ON qa (asker_member);
CREATE INDEX qa_unit ON qa (unit);
CREATE TABLE commitments (id TEXT PRIMARY KEY, unit TEXT, chamber TEXT, date TEXT, parliament INTEGER,
                          speaker TEXT, seat TEXT, member TEXT, seq INTEGER, office TEXT, office_inferred INTEGER,
                          ministry TEXT, quote TEXT, promise TEXT, deadline TEXT, amount TEXT, kind TEXT,
                          topics TEXT);
CREATE INDEX commitments_date ON commitments (date);
CREATE INDEX commitments_member ON commitments (member);
CREATE INDEX commitments_unit ON commitments (unit);
CREATE TABLE members (slug TEXT PRIMARY KEY, name_key TEXT, name TEXT);
CREATE TABLE member_seats (member TEXT, parliament INTEGER, seat TEXT, code TEXT);
CREATE TABLE member_parties (member TEXT, parliament INTEGER, seat TEXT, party TEXT, date_from TEXT, date_to TEXT);
CREATE TABLE bills (slug TEXT PRIMARY KEY, title TEXT, change TEXT, year TEXT, act TEXT, act_title_bi TEXT,
                    act_title_bm TEXT);
CREATE TABLE bill_headings (heading TEXT PRIMARY KEY, bill TEXT);
CREATE VIRTUAL TABLE fts_commitments USING fts5(promise, quote, speaker, office, content='commitments',
                                                tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE fts_qa USING fts5(question, answer, asker, answerer, office, content='qa',
                                       tokenize='unicode61 remove_diacritics 2');
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def tidy(text: str) -> str:
    """The parser's text with the PDF's undecodable apostrophes put back ("Dato�" -> "Dato'")."""
    return re.sub(r"(?<=\w)�(?=\w|\s|$)", "’", text or "").replace("�", "")


REPEAT = re.compile(r"^(.{4,}?) \1\b")


def heading(text: str | None) -> str:
    """An agenda heading with the section header the parser joins to it said once: "RANG
    UNDANG-UNDANG RANG UNDANG-UNDANG PEKERJA GIG 2025" -> "RANG UNDANG-UNDANG PEKERJA GIG 2025"."""
    return REPEAT.sub(r"\1", text or "")


MARKER = re.compile(r"\s*(\(\w{1,5}\)|\d+[A-Za-z]*\.\s|[-–—•] )")
HOLD = (":", ";", "—", ".", "?", "!", '"', "”")


def reflow(text: str | None) -> str:
    """Join the PDF's wrapped lines so the text wraps to the reader's width. A break stays before a
    clause marker ("(a)", "(1)", "60A. ") and after a line ending a sentence or clause (":", ";",
    "—", "."); a blank line stays a paragraph break. A word split with a hyphen at the line end
    joins whole."""
    out: list[str] = []
    for line in (text or "").split("\n"):
        line = line.rstrip()
        prev = out[-1] if out else ""
        if not out or not line or not prev or prev.endswith(HOLD) or MARKER.match(line):
            out.append(line)
        elif prev.endswith("-") and prev[-2:-1].isalpha() and line[:1].islower():
            out[-1] = prev + line.lstrip()
        else:
            out[-1] = prev + " " + line.lstrip()
    return "\n".join(out)


def who(label: str, office: str | None) -> str:
    """A speaker's label with their office after it, unless the label already names the office."""
    return f"{label}, {office}" if office and office not in label else label


def name_key(name: str) -> str:
    """A person's name key (`hansard._norm_name`), read after `tidy` so "Dato�" drops like "Dato'"."""
    return hansard._norm_name(tidy(name))


def is_office(role: str) -> bool:
    return bool(re.match(r"(Timbalan\s+)?(Perdana\s+)?Menteri\b", role or ""))


def ministry(office: str) -> str:
    """The ministry an office belongs to: "Timbalan Menteri Kewangan II" -> "Kewangan";
    "Menteri di Jabatan Perdana Menteri (Undang-undang)" -> "Jabatan Perdana Menteri";
    "Perdana Menteri dan Menteri Kewangan" -> "Perdana Menteri"."""
    if not office:
        return ""
    if re.match(r"(Timbalan\s+)?Perdana\s+Menteri\b", office):
        return "Perdana Menteri"
    m = re.sub(r"^(Timbalan\s+)?Menteri\s+", "", office)
    m = re.sub(r"\s*\(.*$", "", m)
    m = re.sub(r"^di\s+", "", m)
    m = re.sub(r"\s+(I|II|III|1|2)$", "", m)
    return m.strip(" ,")


def pdf_url(path: str) -> str:
    return config.PARLIAMENT_SITE + quote(path) if path else ""


def _read_jsonl(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Sources:
    """The pipeline's files; tests point them at small copies."""
    acts: Path = config.DATA / "acts.csv"
    sections: Path = config.DATA / "act_sections.jsonl"
    sittings: Path = config.DATA / "sittings.csv"
    speeches: Path = hansard.SPEECHES_OUT
    units: Path = enrich.UNITS
    enriched: Path = enrich.ENRICHED
    members: Path = hansard.MEMBERS_OUT
    parties: Path = parties.OUT
    bills: Path = links.OUT
    drafts: Path = drafts.OUT


class Offices:
    """Each person's ministerial offices by date, from the speech labels that name one."""

    def __init__(self) -> None:
        self.seen: dict[str, list[tuple[str, str]]] = {}

    def add(self, key: str, date: str, role: str) -> None:
        if key and is_office(role):
            self.seen.setdefault(key, []).append((date, role))

    def done(self) -> None:
        for v in self.seen.values():
            v.sort()

    def at(self, key: str, date: str, role: str) -> tuple[str, bool]:
        """(office, inferred): the label's own office, else the nearest one within OFFICE_DAYS."""
        if is_office(role):
            return role, False
        seen = self.seen.get(key)
        if not seen:
            return "", False
        i = bisect_left(seen, (date, ""))
        near = [seen[j] for j in (i - 1, i) if 0 <= j < len(seen)]
        best = min(near, key=lambda s: abs(_days(s[0]) - _days(date)))
        return (best[1], True) if abs(_days(best[0]) - _days(date)) <= OFFICE_DAYS else ("", False)


def _days(iso: str) -> int:
    return int(time.mktime(time.strptime(iso, "%Y-%m-%d")) // 86400)


class Members:
    """Which MP a speech is: its name key when the Parliament's register holds it, else the one
    register entry for its seat."""

    def __init__(self, rows: list[dict]) -> None:
        self.keys: dict[int, set[str]] = {}
        self.by_seat: dict[tuple[int, str], list[str]] = {}
        self.seat_of: dict[tuple[int, str], str] = {}
        for r in rows:
            if r["senator"] == "1" or not r["seat"]:
                continue
            p = int(r["parliament"])
            self.keys.setdefault(p, set()).add(r["name_key"])
            self.by_seat.setdefault((p, r["seat"].lower()), []).append(r["name_key"])
            self.seat_of[(p, r["name_key"])] = r["seat"]

    def of(self, parliament: int, name: str, seat: str, senator: bool) -> str:
        if senator:
            return ""
        key = name_key(name)
        if key in self.keys.get(parliament, ()):
            return key
        found = self.by_seat.get((parliament, (seat or "").lower()), [])
        return found[0] if len(found) == 1 else ""


def build(src: Sources | None = None, path: Path = SITE_DB, log=print) -> dict:
    """Write a fresh site.db; returns the row counts."""
    src = src or Sources()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    # A scratch file replaced only on success: no journal, no syncs, and a cache that holds the
    # indexes, so the member updates do not thrash the disk.
    con.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -1048576;"
                      " PRAGMA temp_store = MEMORY;")
    con.executescript(SCHEMA)
    t0 = time.time()

    # The law.
    acts = _csv(src.acts)
    langs: dict[str, set[str]] = {}
    order: dict[tuple[str, str], int] = {}
    for s in _read_jsonl(src.sections):
        k = (s["act"], s["lang"])
        order[k] = order.get(k, 0) + 1
        langs.setdefault(s["act"], set()).add(s["lang"])
        con.execute("INSERT OR IGNORE INTO sections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s["act"], s["lang"], s["number"], order[k], s["heading"], s["part"], s["part_title"],
                     s["chapter"], s["chapter_title"], s["text"], s["notes"], s["page_start"], s["page_end"],
                     s["source"]))
    for a in acts:
        con.execute("INSERT OR IGNORE INTO acts VALUES (?,?,?,?,?,?,?,?)",
                    (a["number"], a["title_bi"], a["title_bm"], a["status"], a["as_at"], a["pdf_bi"], a["pdf_bm"],
                     ",".join(sorted(langs.get(a["number"], ())))))
    log(f"law: {len(acts)} Acts, {sum(order.values())} sections ({time.time() - t0:.0f} s)")

    # Sittings, bills, members.
    draft = {k for k, r in drafts.read(src.drafts).items() if r["draft"] == "1"}
    for r in _csv(src.sittings):
        con.execute("INSERT OR IGNORE INTO sittings VALUES (?,?,?,?,?,?,?)",
                    (r["chamber"], r["date"], int(r["parliament"]), r["term"], r["meeting"], pdf_url(r["pdf_path"]),
                     int((r["chamber"], r["date"]) in draft)))
    heading_bill: dict[str, tuple[str, str]] = {}
    for r in _csv(src.bills):
        b = slug(r["title"])
        heading_bill[r["heading"]] = (b, r["act"])
        con.execute("INSERT OR IGNORE INTO bills VALUES (?,?,?,?,?,?,?)",
                    (b, r["title"], r["change"], r["year"], r["act"], r["act_title_bi"], r["act_title_bm"]))
        con.execute("INSERT OR IGNORE INTO bill_headings VALUES (?,?)", (r["heading"], b))
    member_rows = _csv(src.members)
    members = Members(member_rows)
    party = parties.lookup(src.parties)

    # Pass 1 over the speeches: pages, times and question numbers, and every office a label names.
    where: dict[tuple[str, str, int], tuple] = {}
    offices = Offices()
    for s in _read_jsonl(src.speeches):
        where[(s["chamber"], s["date"], s["seq"])] = (s["page_start"], s["page_end"], s["time"], s["question_no"])
        offices.add(name_key(s["name"]), s["date"], s["role"])
    offices.done()
    log(f"speeches read: {len(where)} ({time.time() - t0:.0f} s)")

    # Pass 2: extracts with their speeches and records.
    enriched = {r["unit"]: r for r in _read_jsonl(src.enriched)}
    names: dict[str, dict[str, int]] = {}
    counts = {"units": 0, "speeches": 0, "qa": 0, "commitments": 0}
    for u in _read_jsonl(src.units):
        rec = enriched.get(u["id"], {})
        p = u["parliament"]
        seq_member: dict[int, str] = {}
        first_page = None
        for s in u["speeches"]:
            pg = where.get((u["chamber"], u["date"], s["seq"]), (0, 0, "", ""))
            first_page = first_page or pg[0]
            m = members.of(p, s["name"], s["seat"], s["senator"])
            seq_member[s["seq"]] = m
            if m:
                names.setdefault(m, {})
                n = tidy(s["name"])
                names[m][n] = names[m].get(n, 0) + 1
            pty = party(p, s["seat"], u["date"]) if s["seat"] and not s["senator"] else ""
            text = tidy(s["text"])
            con.execute("INSERT OR IGNORE INTO speeches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (u["id"], s["seq"], tidy(s["label"]), tidy(s["name"]), s["seat"], s["role"],
                         int(bool(s["senator"])), pty, m, pg[0], pg[1], pg[2], pg[3], text, len(text)))
            counts["speeches"] += 1
        bill, act = heading_bill.get(u["topic"] or "", ("", ""))
        topics = rec.get("topics", [])
        con.execute("INSERT INTO units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (u["id"], u["chamber"], u["date"], p, int(u["id"].rsplit("-", 1)[1]), heading(u["topic"]),
                     tidy(rec.get("summary_en", "")), tidy(rec.get("summary_ms", "")), json.dumps(topics),
                     json.dumps(rec.get("entities", []), ensure_ascii=False), bill, act, len(u["speeches"]),
                     first_page or 0))
        con.executemany("INSERT INTO unit_topics VALUES (?,?,?,?)", [(u["id"], slug(t), t, u["date"]) for t in topics])
        counts["units"] += 1
        for n, q in enumerate(rec.get("qa_pairs", []), start=1):
            qb, ab = q["question_by"], q["answer_by"]
            office, _ = offices.at(name_key(ab["name"]), u["date"], ab["role"])
            con.execute("INSERT INTO qa VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{u['id']}-q{n}", u["id"], u["chamber"], u["date"], p, tidy(qb["label"]), qb["seat"],
                         seq_member.get(qb["seq"], ""), qb["seq"], tidy(ab["label"]), ab["seat"],
                         seq_member.get(ab["seq"], ""), ab["seq"], office, ministry(office), q["question"],
                         q["answer"], json.dumps(q.get("figures", []), ensure_ascii=False), json.dumps(topics)))
            counts["qa"] += 1
        for n, c in enumerate(rec.get("commitments", []), start=1):
            sp = c["speaker"]
            office, inferred = offices.at(name_key(sp["name"]), u["date"], sp["role"])
            con.execute("INSERT INTO commitments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{u['id']}-c{n}", u["id"], u["chamber"], u["date"], p, tidy(sp["label"]), sp["seat"],
                         seq_member.get(sp["seq"], ""), sp["seq"], office, int(inferred), ministry(office),
                         tidy(c["quote"]), c["promise"], c.get("deadline", ""), c.get("amount", ""),
                         c.get("check", ""), json.dumps(topics)))
            counts["commitments"] += 1
        if counts["units"] % 5000 == 0:
            con.commit()
            log(f"{counts['units']} extracts ({time.time() - t0:.0f} s)")

    # MPs: the name each is most often printed with, the seats, and the party spells of each seat.
    seats: dict[tuple[str, int], str] = {}
    for r in member_rows:
        if r["senator"] != "1" and r["seat"] and r["name_key"] in names:
            seats[(r["name_key"], int(r["parliament"]))] = r["seat"]
    # One person under two name keys (the attendance lists print both "Hannah Yeoh" and "Hannah Yeoh
    # Tseow Suan" for Segambut): the same seat, one key's words inside the other's. The key with more
    # speeches names the MP.
    alias: dict[str, str] = {}
    by_seat: dict[str, set[str]] = {}
    for (k, p), seat in seats.items():
        by_seat.setdefault(parties._seat_key(seat), set()).add(k)
    spoken = {k: sum(f.values()) for k, f in names.items()}
    alias.update({a: b for a, b in {**SAME_PERSON, **RENAMED}.items() if a in names and b in names})
    for keys in by_seat.values():
        for a in keys:
            for b in keys:
                if a != b and len(a.split()) >= 2 and set(a.split()) < set(b.split()):
                    lo, hi = sorted((a, b), key=lambda k: (spoken[k], k))
                    alias[lo] = hi

    def final(k: str) -> str:
        while k in alias:
            k = alias[k]
        return k

    alias = {a: final(a) for a in alias}
    for a, b in alias.items():
        for n, c in names.pop(a).items():
            names[b][n] = names[b].get(n, 0) + c
        con.execute("UPDATE speeches SET member = ? WHERE member = ?", (b, a))
        for t, col in (("qa", "asker_member"), ("qa", "answerer_member"), ("commitments", "member")):
            con.execute(f"UPDATE {t} SET {col} = ? WHERE {col} = ?", (b, a))
    spells = _csv(src.parties)
    for key, forms in names.items():
        s = slug(key)
        if key in RENAMED.values():  # the most used form of the new name, not of the old one
            forms = {n: c for n, c in forms.items() if name_key(n) == key} or forms
        con.execute("INSERT OR IGNORE INTO members VALUES (?,?,?)", (s, key, max(forms, key=forms.get)))
        done: set[int] = set()
        for (k, p), seat in seats.items():
            if alias.get(k, k) != key or p in done:
                continue
            done.add(p)
            rows = [r for r in spells if int(r["parliament"]) == p and parties._seat_key(r["seat"]) == parties._seat_key(seat)]
            code = rows[0]["code"] if rows else ""
            con.execute("INSERT INTO member_seats VALUES (?,?,?,?)", (s, p, seat, code))
            words = set(key.split())
            mine = [r for r in rows if len(words & set(name_key(r["member"]).split())) >= 2] or (
                rows if len({r["member"] for r in rows}) == 1 else [])
            con.executemany("INSERT INTO member_parties VALUES (?,?,?,?,?,?)",
                            [(s, p, seat, r["party"], r["from"], r["to"]) for r in mine])
    con.execute("UPDATE speeches SET member = REPLACE(member, ' ', '-') WHERE member != ''")
    for t, col in (("qa", "asker_member"), ("qa", "answerer_member"), ("commitments", "member")):
        con.execute(f"UPDATE {t} SET {col} = REPLACE({col}, ' ', '-') WHERE {col} != ''")
    con.execute("INSERT INTO fts_commitments(fts_commitments) VALUES ('rebuild')")
    con.execute("INSERT INTO fts_qa(fts_qa) VALUES ('rebuild')")
    counts["members"] = len(names)
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in counts.items()] +
                    [("built", json.dumps(time.strftime("%Y-%m-%d %H:%M:%S")))])
    con.commit()
    # The tables went in interleaved; VACUUM lays each one out in one run of pages, so a cold read
    # does not seek across the whole file.
    con.execute("ANALYZE")
    con.execute("VACUUM")
    con.close()
    tmp.replace(path)
    log(f"site.db: {counts} ({time.time() - t0:.0f} s)")
    return counts


# ---------- reading ----------

def fts_query(text: str) -> str:
    """Every word of `text`, each quoted, AND-ed: FTS5 syntax in a reader's words cannot leak in."""
    return " ".join(f'"{w}"' for w in re.findall(r"[^\W_]+", text.lower()))


@dataclass
class Page:
    rows: list[dict]
    total: int
    page: int
    size: int = PAGE_SIZE

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size))


def build_empty(path: Path) -> Path:
    """An empty page database with zero counts, so a fresh clone can run `--replay` with no data."""
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO meta VALUES (?, ?)",
                    [(k, "0") for k in ("units", "speeches", "qa", "commitments", "members")] +
                    [("built", json.dumps("no data"))])
    con.commit()
    con.close()
    return path


class Records:
    """Read access to site.db, one connection per thread (FastAPI runs sync routes on a pool)."""

    def __init__(self, path: Path = SITE_DB) -> None:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run python -m parlimen.records build")
        self.path = path
        self._local = threading.local()
        self._lists: dict[str, list] = {}  # topics, years and ministries: fixed for the life of a build

    def _listed(self, key: str, sql: str) -> list:
        if key not in self._lists:
            self._lists[key] = self._all(sql)
        return self._lists[key]

    @property
    def con(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

    def _all(self, sql: str, args=()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, args)]

    def _one(self, sql: str, args=()) -> dict | None:
        r = self.con.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _page(self, sql: str, args: list, page: int, size: int = PAGE_SIZE, order: str = "",
              wrap: str = "{q}") -> Page:
        """One page of `sql`'s rows. The count and the page read `sql` alone; `wrap` joins in the
        units' fields for the page's rows only, so a cold read touches 50 units, not all of them."""
        total = self.con.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
        page = max(1, page)
        rows = self._all(wrap.format(q=f"{sql} {order} LIMIT ? OFFSET ?"), [*args, size, (page - 1) * size])
        return Page(rows, total, page, size)

    def meta(self) -> dict:
        return {r["key"]: json.loads(r["value"]) for r in self._all("SELECT * FROM meta")}

    # The law.
    def acts(self, status: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM acts WHERE langs != ''", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        return self._all(sql + " ORDER BY CAST(number AS INTEGER), number", args)

    def act(self, number: str) -> dict | None:
        return self._one("SELECT * FROM acts WHERE number = ?", (number,))

    def sections(self, act: str, lang: str) -> list[dict]:
        return self._all("SELECT * FROM sections WHERE act = ? AND lang = ? ORDER BY ord", (act, lang))

    def section(self, act: str, number: str, lang: str = "BI") -> dict | None:
        return self._one("SELECT * FROM sections WHERE act = ? AND lang = ? AND number = ?", (act, lang, number))

    def act_debates(self, act: str) -> list[dict]:
        """The extracts that debated a bill for this Act, oldest first."""
        return self._all("SELECT u.*, b.title AS bill_title FROM units u JOIN bills b ON b.slug = u.bill "
                         "WHERE u.act = ? ORDER BY u.date, u.ord", (act,))

    # The debates.
    def sittings(self, parliament: int | None = None, limit: int = -1) -> list[dict]:
        sql = ("SELECT s.*, (SELECT COUNT(*) FROM units u WHERE u.chamber = s.chamber AND u.date = s.date) AS units "
               "FROM sittings s")
        args = []
        if parliament:
            sql += " WHERE s.parliament = ?"
            args.append(parliament)
        return self._all(sql + " ORDER BY s.date DESC, s.chamber LIMIT ?", [*args, limit])

    def sitting(self, chamber: str, date: str) -> dict | None:
        return self._one("SELECT * FROM sittings WHERE chamber = ? AND date = ?", (chamber, date))

    def sitting_units(self, chamber: str, date: str) -> list[dict]:
        return self._all("SELECT * FROM units WHERE chamber = ? AND date = ? ORDER BY ord", (chamber, date))

    def unit(self, unit_id: str) -> dict | None:
        return self._one("SELECT * FROM units WHERE id = ?", (unit_id,))

    def speeches(self, unit_id: str) -> list[dict]:
        return self._all("SELECT * FROM speeches WHERE unit = ? ORDER BY seq", (unit_id,))

    def unit_qa(self, unit_id: str) -> list[dict]:
        return self._all("SELECT * FROM qa WHERE unit = ? ORDER BY rowid", (unit_id,))

    def unit_commitments(self, unit_id: str) -> list[dict]:
        return self._all("SELECT * FROM commitments WHERE unit = ? ORDER BY rowid", (unit_id,))

    def neighbours(self, unit: dict) -> tuple[dict | None, dict | None]:
        prev = self._one("SELECT id, business FROM units WHERE chamber = ? AND date = ? AND ord < ? ORDER BY ord DESC LIMIT 1",
                         (unit["chamber"], unit["date"], unit["ord"]))
        nxt = self._one("SELECT id, business FROM units WHERE chamber = ? AND date = ? AND ord > ? ORDER BY ord LIMIT 1",
                        (unit["chamber"], unit["date"], unit["ord"]))
        return prev, nxt

    # Records with filters.
    @staticmethod
    def _filters(t: str, q: str, year: str, ministry_: str, topic: str, parliament: str, member: str,
                 member_col: str) -> tuple[str, list]:
        where, args = [], []
        if q:
            fts = "fts_commitments" if t == "commitments" else "fts_qa"
            where.append(f"{t}.rowid IN (SELECT rowid FROM {fts} WHERE {fts} MATCH ?)")
            args.append(fts_query(q))
        if year:
            where.append(f"{t}.date LIKE ?")
            args.append(f"{year}-%")
        if ministry_:
            where.append(f"{t}.ministry = ?")
            args.append(ministry_)
        if topic:
            where.append(f"{t}.unit IN (SELECT unit FROM unit_topics WHERE topic = ?)")
            args.append(topic)
        if parliament:
            where.append(f"{t}.parliament = ?")
            args.append(int(parliament))
        if member:
            where.append(f"{t}.{member_col} = ?")
            args.append(member)
        return (" WHERE " + " AND ".join(where)) if where else "", args

    def commitments(self, q: str = "", year: str = "", ministry: str = "", topic: str = "", parliament: str = "",
                    member: str = "", kind: str = "", page: int = 1, size: int = PAGE_SIZE) -> Page:
        where, args = self._filters("commitments", q, year, ministry, topic, parliament, member, "member")
        if kind:
            where += (" AND " if where else " WHERE ") + "commitments.kind = ?"
            args.append(kind)
        return self._page("SELECT * FROM commitments" + where, args, page, size,
                          "ORDER BY commitments.date DESC, commitments.id", BUSINESS)

    def questions(self, q: str = "", year: str = "", ministry: str = "", topic: str = "", parliament: str = "",
                  member: str = "", page: int = 1, size: int = PAGE_SIZE) -> Page:
        where, args = self._filters("qa", q, year, ministry, topic, parliament, member, "asker_member")
        return self._page("SELECT * FROM qa" + where, args, page, size, "ORDER BY qa.date DESC, qa.id", BUSINESS)

    def ministries(self, table: str = "commitments") -> list[dict]:
        return self._listed(f"ministries-{table}", f"SELECT ministry, COUNT(*) AS n FROM {table} WHERE ministry != '' "
                                                   "GROUP BY ministry ORDER BY ministry")

    def parliament_now(self) -> int:
        return self._listed("parliament", "SELECT MAX(parliament) AS p FROM sittings")[0]["p"]

    def years(self) -> list[str]:
        return [r["y"] for r in self._listed("years", "SELECT DISTINCT substr(date, 1, 4) AS y FROM units ORDER BY y DESC")]

    # MPs, bills, topics.
    def members(self, parliament: int | None = None) -> list[dict]:
        sql = ("SELECT m.slug, m.name, s.parliament, s.seat, s.code FROM members m "
               "JOIN member_seats s ON s.member = m.slug")
        args = []
        if parliament:
            sql += " WHERE s.parliament = ?"
            args.append(parliament)
        return self._all(sql + " ORDER BY s.parliament DESC, s.code, s.seat", args)

    def member(self, s: str) -> dict | None:
        m = self._one("SELECT * FROM members WHERE slug = ?", (s,))
        if m:
            m["seats"] = self._all("SELECT * FROM member_seats WHERE member = ? ORDER BY parliament", (s,))
            m["parties"] = self._all("SELECT * FROM member_parties WHERE member = ? ORDER BY parliament, date_from", (s,))
        return m

    def member_units(self, s: str, page: int = 1, size: int = PAGE_SIZE) -> Page:
        sql = "SELECT unit, MIN(seq) AS seq FROM speeches WHERE member = ? AND chars >= 200 GROUP BY unit"
        # A unit id is "<chamber>-<date>-<order>", so its tail sorts by date, then agenda order.
        return self._page(sql, [s], page, size, "ORDER BY substr(unit, 4) DESC, unit",
                          "SELECT u.*, x.seq FROM ({q}) x JOIN units u ON u.id = x.unit "
                          "ORDER BY substr(x.unit, 4) DESC, x.unit")

    def member_counts(self, s: str) -> dict:
        one = lambda sql: self.con.execute(sql, (s,)).fetchone()[0]  # noqa: E731
        return {"items": one("SELECT COUNT(DISTINCT unit) FROM speeches WHERE member = ? AND chars >= 200"),
                "answered": one("SELECT COUNT(*) FROM qa WHERE answerer_member = ?"),
                "asked": one("SELECT COUNT(*) FROM qa WHERE asker_member = ?"),
                "commitments": one("SELECT COUNT(*) FROM commitments WHERE member = ?")}

    def member_activity(self, s: str) -> list[dict]:
        """Agenda items the MP spoke in (200 characters or more), by month: [{month: "2023-03", items}]."""
        return self._all("SELECT substr(u.date, 1, 7) AS month, COUNT(DISTINCT u.id) AS items FROM speeches x "
                         "JOIN units u ON u.id = x.unit WHERE x.member = ? AND x.chars >= 200 "
                         "GROUP BY month ORDER BY month", (s,))

    def member_topics(self, s: str, limit: int = 8) -> list[dict]:
        return self._all("SELECT topic, MIN(name) AS name, COUNT(DISTINCT unit) AS n FROM unit_topics WHERE unit IN "
                         "(SELECT DISTINCT unit FROM speeches WHERE member = ? AND chars >= 200) "
                         "GROUP BY topic ORDER BY n DESC, topic LIMIT ?", (s, limit))

    def member_offices(self, s: str) -> list[dict]:
        """Offices the MP spoke from when making commitments, with the first and last date seen."""
        return self._all("SELECT office, MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n FROM commitments "
                         "WHERE member = ? AND office != '' GROUP BY office ORDER BY first", (s,))

    def member_answers(self, s: str, size: int = 10) -> list[dict]:
        return self._all("SELECT * FROM qa WHERE answerer_member = ? ORDER BY date DESC, id LIMIT ?", (s, size))

    def topic_trend(self, top: int = 6) -> list[dict]:
        """Agenda items a year for the `top` biggest topics: [{topic, name, year, n}]."""
        return self._listed(f"topic_trend_{top}",
                            "SELECT topic, MIN(name) AS name, substr(date, 1, 4) AS year, COUNT(*) AS n "
                            "FROM unit_topics WHERE topic IN (SELECT topic FROM unit_topics GROUP BY topic "
                            f"ORDER BY COUNT(*) DESC LIMIT {int(top)}) GROUP BY topic, year ORDER BY topic, year")

    def bills(self) -> list[dict]:
        return self._all("SELECT b.*, MIN(u.date) AS first, MAX(u.date) AS last, COUNT(u.id) AS units FROM bills b "
                         "JOIN units u ON u.bill = b.slug GROUP BY b.slug ORDER BY last DESC")

    def bill(self, s: str) -> dict | None:
        b = self._one("SELECT * FROM bills WHERE slug = ?", (s,))
        if b:
            b["units"] = self._all("SELECT * FROM units WHERE bill = ? ORDER BY date, ord", (s,))
        return b

    def topics(self) -> list[dict]:
        return self._listed("topics", "SELECT topic, MIN(name) AS name, COUNT(*) AS n FROM unit_topics "
                                      "GROUP BY topic ORDER BY topic")

    def topic_units(self, topic: str, page: int = 1, size: int = PAGE_SIZE) -> Page:
        return self._page("SELECT unit, date FROM unit_topics WHERE topic = ?", [topic], page, size,
                          "ORDER BY date DESC, unit", "SELECT u.* FROM ({q}) x JOIN units u ON u.id = x.unit "
                          "ORDER BY x.date DESC, x.unit")

    def units_between(self, date_from: str, date_to: str, topics: list[str] | None = None) -> list[dict]:
        sql, args = "SELECT * FROM units WHERE date >= ? AND date <= ?", [date_from, date_to]
        if topics:
            sql += f" AND id IN (SELECT unit FROM unit_topics WHERE topic IN ({','.join('?' * len(topics))}))"
            args += topics
        return self._all(sql + " ORDER BY date, chamber, ord", args)

    def unit_ids(self, year: str) -> list[str]:
        return [r["id"] for r in self._all("SELECT id FROM units WHERE substr(date, 1, 4) = ? ORDER BY id", (year,))]

    def sitting_years(self) -> list[str]:
        return [r["y"] for r in self._listed("sitting_years", "SELECT DISTINCT substr(date, 1, 4) AS y FROM sittings "
                                                              "ORDER BY y")]

    def member_slugs(self) -> list[str]:
        return [r["slug"] for r in self._all("SELECT slug FROM members ORDER BY slug")]

    def speech(self, unit_id: str, seq: int) -> dict | None:
        return self._one("SELECT * FROM speeches WHERE unit = ? AND seq = ?", (unit_id, seq))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("stats")
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    else:
        print(Records().meta())


if __name__ == "__main__":
    main()
