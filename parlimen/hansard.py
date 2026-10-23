"""Split each sitting's Hansard PDF into speeches: who spoke, when, on which page, and what.

The parser decides who spoke, never a model. A speech opens with a speaker label in bold at the
start of a line, closed by a colon: "Tuan Yang di-Pertua:", "Tuan Chan Foong Hin [Kota
Kinabalu]:", "Timbalan Menteri Kesihatan I [Dato' Dr. Haji Noor Azmi bin Ghazali]:". A long
label wraps, so a wholly bold line above a label joins it while a bracket is open or the label
starts with one. An oral question opens with its number in bold: "1. Tuan ... [Igan] minta
Menteri Kesihatan menyatakan ..."; the answer and the follow-up speeches keep its number until
the next question or heading. Wholly bold lines that are not labels are headings (the business
in hand: "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN", a bill's name), less notes in
brackets; a bold block after a line ending in ":" is a table header in the speech. A time mark
"■1010", or the clerk's note "2.49 ptg." on a line of its own, gives the clock time of the
text after it. Running heads ("DR.23.03.2022 1", "4 DR 7.10.2022") go.

The attendance list on the front pages ("12. YB. Dato' Sri Mustapa bin Mohamed (Jeli)") tells a
seat from a name inside a label's brackets, and gives the seat of a speaker labelled by name
alone. Where a sitting has no list (the Special Chamber, the first sitting of a Parliament), the
Parliament's register does the same: every cached Dewan Rakyat list merged. The sitting's date
is read from the first debate page and checked against the listing.

Writes data/speeches.jsonl (one record per speech), data/hansard-report.csv (one row per
sitting) and data/members.csv (the registers). Run: python -m parlimen.hansard [--chamber DR|KK]
[--dates ISO ...] [--pilot]
"""

import argparse
import csv
import ctypes
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date

from . import config, fetch
from .sittings import MALAY_MONTHS, Sitting, read_csv

SPEECHES_OUT = config.DATA / "speeches.jsonl"
REPORT_OUT = config.DATA / "hansard-report.csv"
MEMBERS_OUT = config.DATA / "members.csv"

_BODY_START = re.compile(r"dimulakan pada pukul|Mesyuarat bermula|Majlis dimulakan", re.I)
_DATE_LINE = re.compile(r"^(Isnin|Selasa|Rabu|Khamis|Jumaat|Sabtu|Ahad),?\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.I)
_RUNNING_HEAD = re.compile(r"^(\S+\s+)?(DR|KKDR|KK|DK)[.\s]\s*\d{1,2}\.\d{1,2}\.\d{4}(\s+\S+)?$")  # "DR.23.03.2022 1", "4 DR 7.10.2022"
_TIME = re.compile(r"■\s*(\d{4})")
_CLOCK = re.compile(r"(?:^|\s)(\d{1,2})\.(\d{2})\s*(pg|tgh|ptg|mlm)\.?$", re.I)  # the clerk's "2.49 ptg." note
_TABLE_ROW = re.compile(r"\d[\d,.]*\s+\d[\d,.]*$")  # a bold total in a table: "JUMLAH KESELURUHAN 897 124"
# Notes in brackets ("[Sesi ... tamat]", "[Tuan X mempengerusikan Mesyuarat]"), also when only one end is in the heading.
_HEADING_NOTE = re.compile(r"\[[^\]]*\]|^[^\[]*\]|\[[^\]]*$|_{3,}")


def _clock(m: re.Match) -> str:
    """A "2.49 ptg." note as "1449": tengah hari runs 12 to 1, petang and malam are after noon."""
    h, suffix = int(m.group(1)), m.group(3).lower()
    if (suffix in ("ptg", "mlm") and h < 12) or (suffix == "tgh" and h < 11):
        h += 12
    return f"{h:02d}{m.group(2)}"
_QUESTION = re.compile(r"^(\d+)\.\s+(.+?)\s*:?$")
_PERSON = re.compile(r"\b(bin|binti|a/l|a/p|anak|ak|Dato|Datuk|Datin|Tan Sri|Tun|Tuan|Puan|Cik|Dr|Haji|Hajah|"
                     r"Ir|Ts|Senator|Tengku|Syed|Sharifah|Wan|Nik|Raja|Toh Puan)\b", re.I)
_HONORIFIC = re.compile(r"\b(YAB|YB|YM|YBhg|YAM|Yang Amat Berhormat|Yang Berhormat|Tun|Tan Sri|Puan Sri|Toh Puan|"
                        r"Dato'? Seri Utama|Dato'? Sri|Dato'? Seri|Datuk Seri Panglima|Datuk Seri|Datuk Wira|"
                        r"Dato'? Indera|Datuk|Dato'?|Datin Paduka|Datin|Dr|Ir|Ts|Haji|Hajah|Hj|Tuan|Puan|Cik|"
                        r"Senator|Profesor|Prof)\b\.?", re.I)


@dataclass
class Line:
    page: int
    text: str
    lead: str        # the bold characters the line opens with
    italic: bool     # the whole line is in italic type


@dataclass
class Speech:
    chamber: str
    date: str
    parliament: int
    seq: int
    page_start: int
    page_end: int
    time: str            # "1010" from the last time mark before the speech, "" before the first
    topic: str           # the last heading above the speech
    question_no: str     # an oral question's number
    label: str           # the speaker label as printed, without its colon
    role: str            # "Tuan Yang di-Pertua", "Timbalan Menteri Kesihatan I", ...
    name: str
    seat: str            # the constituency, from the label or the attendance list
    senator: bool        # a Senator (a minister from the Dewan Negara), who holds no seat
    text: str


@dataclass
class Report:
    chamber: str
    date: str
    pages: int = 0
    date_in_pdf: str = ""
    speeches: int = 0
    named: int = 0            # speeches by a named person (not the chair or "Seorang Ahli")
    resolved: int = 0         # of those, how many resolve to a seat or a Senator
    attendees: int = 0
    body_chars: int = 0
    orphan_chars: int = 0     # debate text before the first label
    no_seat: list[str] = field(default_factory=list)
    note: str = ""


def _norm_name(s: str) -> str:
    """A person's name without honorifics, "bin" and the like, punctuation or case, so that the
    label "Dato' Mohd Rashid Hasnon" matches the attendance list's "Dato' Mohd Rashid bin Hasnon"."""
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\b[A-Z](?:\.[A-Z])+\.?(?=\s|$|,)", " ", s)  # honours such as D.S.P.N.
    s = _HONORIFIC.sub(" ", s)
    s = re.sub(r"\b(bin|binti|a/l|a/p|anak|ak|@)\b", " ", s, flags=re.I)
    words = re.sub(r"[^a-z0-9]+", " ", s.lower()).split()
    return " ".join(_SPELLINGS.get(w, w) for w in words)


# A name spelt one way in labels and another in the attendance list.
_SPELLINGS = {"muhyiddin": "mahiaddin"}


_ROLE_START = re.compile(r"^(Yang di-Pertua|Tuan Yang di-Pertua|Timbalan|Menteri|Perdana Menteri|Ketua|Setiausaha)", re.I)


@dataclass
class Member:
    seat: str      # "" for a Senator
    party: str     # where the list gives it (2018)
    senator: bool


_SEAT_END = re.compile(r"[(\[]([^()\[\]]+)[)\]]\s*(?:[–-]\s*(.*))?$")


def attendance(lines: list[Line]) -> dict[str, Member]:
    """Members on the front pages' lists, present or absent, and the Senators who attend.

    Forms: "12. YB. Dato' Sri Mustapa bin Mohamed (Jeli)" (2022); "2. Perdana Menteri dan Menteri
    Kewangan, Dato' Seri Anwar bin Ibrahim (Tambun)" (2026, wrapping over lines); "2. “ Tuan
    Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai] – PKR" (2018, ditto marks and the party);
    "2. Menteri Pelaburan, Perdagangan dan Industri, Senator Datuk Seri Utama Tengku Zafrul ...".
    """
    entries: list[str] = []
    wraps = 3  # lines the last entry may still take; a heading or three lines close it
    for ln in lines:
        if _RUNNING_HEAD.match(ln.text) or re.fullmatch(r"[ivxlc]+|\d+", ln.text.strip(), re.I):
            continue  # page furniture inside a list that runs over pages
        if re.match(r"^\d+\.\s", ln.text):
            entries.append(ln.text)
            wraps = 0
        elif ln.lead or ln.text.endswith(":"):
            wraps = 3
        elif entries and wraps < 3 and not _SEAT_END.search(entries[-1]):
            entries[-1] += " " + ln.text  # an entry wrapped before its seat
            wraps += 1
    out = {}
    for e in entries:
        # The seat in brackets, then a party ("– PKR") or the member's office ("– Timbalan Tuan
        # Yang di-Pertua"). A Senator has no seat.
        m = _SEAT_END.search(e)
        senator = not m and re.search(r"\bSenator\b", e) is not None
        if not m and not senator:
            continue
        after = (m.group(2) or "").strip() if m else ""
        seat = m.group(1).strip() if m else ""
        party = after if re.fullmatch(r"[A-Z][A-Z+\-]{1,12}", after) else ""
        who = e[: m.start()] if m else e
        who = re.sub(r"^\d+\.\s*[“\"]?\s*", "", who)
        who = re.sub(r"^(Yang Amat Berhormat|Yang Berhormat|YAB|YB|YM|YBhg)\.?\s+", "", who)
        who = re.sub(r",\s*(?:[A-Z]\.){2,}[A-Z]?\.?\s*$", "", who.strip())  # honours: ", D.S.P.N."
        if "," in who and (_ROLE_START.match(who) or senator):
            who = who.rsplit(",", 1)[1]  # "Office, with commas, Name": the name follows the last comma
        name = _norm_name(who.strip(" ,–-"))
        # Numbered lines that are not members: a question ("... minta Menteri ..."), a bill on the
        # contents page ("Rang Undang-undang ... (Pindaan)"), a page reference.
        if name and not re.search(r"\d|\b(minta|menyatakan|akta|rang|halaman)\b", name):
            out[name] = Member(seat, party, senator)
    return out


def read_pdf(path, front_only: bool = False) -> list[Line]:
    """Every non-empty line with its page, its bold lead and whether it is all italic.

    `front_only` stops at the page where the debate opens: the front pages hold the attendance.
    """
    import pypdfium2 as pdfium
    import pypdfium2.raw as c

    buf = ctypes.create_string_buffer(256)
    out = []
    doc = pdfium.PdfDocument(str(path))
    try:
        for p in range(len(doc)):
            tp = doc[p].get_textpage()
            text = tp.get_text_range()
            fonts: dict[int, str] = {}

            def font(i: int) -> str:
                if i not in fonts:
                    n = c.FPDFText_GetFontInfo(tp.raw, i, buf, 256, None)
                    fonts[i] = buf.raw[: max(n - 1, 0)].decode("latin-1")
                return fonts[i]

            for m in re.finditer(r"[^\r\n]+", text):
                raw = m.group()
                if not raw.strip():
                    continue
                lead_end = m.start()
                while lead_end < m.end() and (text[lead_end].isspace() or "Bold" in font(lead_end)):
                    lead_end += 1
                letters = [i for i in range(m.start(), m.end()) if not text[i].isspace()]
                italic = bool(letters) and all("Italic" in font(i) or "Oblique" in font(i) for i in letters)
                clean = raw.replace("￾", "-").replace("­", "-")
                lead = clean[: lead_end - m.start()]
                out.append(Line(p + 1, clean.strip(), lead.strip(), italic))
            if front_only and _BODY_START.search(text):
                break
    finally:
        doc.close()
    return out


def _caps_share(s: str) -> float:
    letters = [ch for ch in s if ch.isalpha()]
    return sum(ch.isupper() for ch in letters) / max(len(letters), 1)


def _label_split(lead: str) -> tuple[str, str] | None:
    """(label, the rest of the bold lead) when the bold lead holds a speaker label."""
    lead = re.sub(r":\s*([\])])", r"\1", lead)  # a stray colon inside the bracket: "[Dr. Zulkifli bin Hasan:]:"
    if ":" not in lead:
        return None
    label, rest = lead.split(":", 1)
    label = label.strip()
    if not label or len(label) > 200 or _caps_share(label) > 0.6:
        return None  # a heading such as "USUL MENTERI ... DI BAWAH P.M. 27(3):"
    return label, rest.strip()


def parse_label(label: str, seats: set[str]) -> tuple[str, str, str]:
    """(role, name, seat) from a label. "Name [Seat]", "Role [Name]", "Role", "Name"."""
    m = re.fullmatch(r"(.*?)\s*\[([^\[\]]+)\]\s*(\.\.\.)?", label)
    if m:
        before, inside = m.group(1).strip(), m.group(2).strip()
        if inside.lower() in seats or not _PERSON.search(inside):
            return "", before, inside
        # A chair named with the seat: "Tuan Pengerusi [Dato' Ramli bin Dato' Mohd Nor (Cameron Highlands)]".
        if (p := re.fullmatch(r"(.+?)\s*\(([^()]+)\)", inside)) and p.group(2).lower() in seats:
            return before, p.group(1), p.group(2)
        return before, inside, ""
    if _PERSON.search(label) and not re.match(r"(Tuan|Timbalan) (Yang di-Pertua|Pengerusi|Speaker)", label, re.I):
        return "", label.rstrip(". "), ""
    return label, "", ""


def parse_sitting(lines: list[Line], s: Sitting, register: dict[str, Member]) -> tuple[list[Speech], Report]:
    """The sitting's speeches. `register` is the Parliament's members from every attendance list,
    for the sittings whose own list is missing (the Special Chamber prints none)."""
    rep = Report(s.chamber, s.date, pages=max((ln.page for ln in lines), default=0))
    start = next((k for k, ln in enumerate(lines) if _BODY_START.search(ln.text)), None)
    if start is None:
        rep.note = "no opening line (Mesyuarat dimulakan ...) found"
        return [], rep

    members = attendance(lines[:start])
    rep.attendees = len(members)
    seats = {m.seat.lower() for m in (*members.values(), *register.values()) if m.seat}
    for ln in lines[max(0, start - 6):start + 1]:
        if m := _DATE_LINE.match(ln.text):
            month = MALAY_MONTHS.get(m.group(3).lower())
            if month:
                rep.date_in_pdf = date(int(m.group(4)), month, int(m.group(2))).isoformat()

    speeches: list[Speech] = []
    body = [ln for ln in lines[start + 1:] if not _RUNNING_HEAD.match(ln.text)]
    time = topic = question_no = ""  # question_no holds from a numbered question to the next one or the next heading
    pending_bold: list[Line] = []  # wholly bold lines not yet known to be a heading or a label's start
    cur: Speech | None = None
    text_lines: list[str] = []

    def close() -> None:
        if cur is not None:
            cur.text = "\n".join(text_lines).strip()
            speeches.append(cur)

    def flush_headings() -> None:
        """Wholly bold lines that opened no label: a heading in capitals, else bold words in a speech."""
        nonlocal topic, question_no
        if not pending_bold:
            return
        heading = " ".join(ln.text for ln in pending_bold if not _TABLE_ROW.search(ln.text))
        heading = re.sub(r"\s+", " ", _HEADING_NOTE.sub(" ", heading)).strip()
        table = bool(text_lines) and text_lines[-1].rstrip().endswith(":")  # "... seperti berikut:" then a table
        if not heading:
            pass
        elif _caps_share(heading) > 0.6 and not table:
            # A stray lower-case word before the capitals ("researcher PERTANYAAN ...", DR 2023-10-18) goes.
            topic, question_no = re.sub(r"^(?:[a-z]+\s+)+(?=[A-Z])", "", heading), ""
        elif cur is not None:
            text_lines.extend(ln.text for ln in pending_bold)
            cur.page_end = pending_bold[-1].page
        pending_bold.clear()

    for ln in body:
        if m := _TIME.search(ln.text):
            time = m.group(1)
            rest = _TIME.sub("", ln.text).strip()
            if not rest:
                continue
            ln = Line(ln.page, rest, ln.lead.replace(m.group(), "").strip(), ln.italic)
        # The clock note stands alone or ends a heading; inside a sentence ("pada pukul 1.00 tgh.") it stays.
        if (m := _CLOCK.search(ln.text)) and (m.start() == 0 or len(ln.lead) >= len(ln.text) - 1):
            time = _clock(m)
            rest = ln.text[:m.start()].strip()
            if not rest:
                continue
            ln = Line(ln.page, rest, ln.lead[:len(rest)].strip(), ln.italic)
        whole_bold = ln.lead and len(ln.lead) >= len(ln.text) - 1
        split = _label_split(ln.lead)
        question = None
        if not split and ln.lead and (q := _QUESTION.match(ln.lead)) and "[" in ln.lead:
            question = q
        if split or question:
            if question:
                label, rest = question.group(2).rstrip(":").strip(), ln.text[len(ln.lead):].strip()
            else:
                label, lead_rest = split
                rest = (lead_rest + " " + ln.text[len(ln.lead):]).strip()
            # A wrapped label: the wholly bold lines above belong to it while its brackets are
            # unbalanced ("Ghazali]"), or once when it opens with the bracket ("[Dato' ...]").
            while pending_bold:
                if label.count("]") > label.count("[") or label.count(")") > label.count("("):
                    label = pending_bold.pop().text + " " + label
                elif label.startswith("["):
                    label = pending_bold.pop().text + " " + label
                    break
                else:
                    break
            label = re.sub(r"\s+", " ", label)
            flush_headings()
            close()
            role, name, seat = parse_label(label, seats)
            if question:
                question_no = question.group(1)
            cur = Speech(s.chamber, s.date, s.parliament, len(speeches) + 1, ln.page, ln.page, time, topic,
                         question_no, label, role, name, seat, False, "")
            text_lines = [rest] if rest else []
            continue
        if whole_bold:
            pending_bold.append(ln)
            continue
        flush_headings()
        if cur is None:
            rep.orphan_chars += len(ln.text)
        else:
            text_lines.append(ln.text)
            cur.page_end = ln.page
        rep.body_chars += len(ln.text)
    flush_headings()
    close()

    # A speaker labelled by name alone takes the seat that a fuller label in the sitting, its own
    # attendance list or the Parliament's register gives the same name.
    known: dict[str, Member] = {**register, **members}
    for sp in speeches:
        if sp.name and sp.seat:
            known.setdefault(_norm_name(sp.name), Member(sp.seat, "", False))
    words = {n: {x for x in n.split() if len(x) > 1} for n in known}

    def member_for(name: str) -> Member | None:
        key = _norm_name(name)
        if key in known:
            return known[key]
        # Labels shorten names ("Tuan M. Kulasegaran" for "M. Kulasegaran a/l V. Murugeson"): one
        # listed person whose name words hold all of the label's, or the reverse. Initials do not
        # count ("M. Saravanan" is "Saravanan a/l Murugan").
        mine = {x for x in key.split() if len(x) > 1}
        hits = {(known[n].seat, known[n].senator) for n, w in words.items()
                if mine and w and (mine <= w or w <= mine) and len(n.split()) > 1}
        if len(hits) != 1:
            return None
        seat, senator = hits.pop()
        return Member(seat, "", senator)

    for sp in speeches:
        if sp.name and not sp.seat and (m := member_for(sp.name)):
            sp.seat, sp.senator = m.seat, m.senator
    named = [sp for sp in speeches if sp.name and not sp.role.startswith("Setiausaha")]  # the Clerk is staff
    rep.speeches, rep.named = len(speeches), len(named)
    rep.resolved = sum(1 for sp in named if sp.seat or sp.senator)
    rep.no_seat = sorted({sp.label for sp in named if not (sp.seat or sp.senator)})
    if rep.date_in_pdf and rep.date_in_pdf != s.date:
        rep.note = f"the PDF is dated {rep.date_in_pdf}"
    return speeches, rep


def build_registers(sittings: list[Sitting]) -> dict[int, dict[str, Member]]:
    """Each Parliament's members, from the attendance lists of every Dewan Rakyat sitting whose
    PDF is cached. A name listed with two seats in one Parliament keeps the commoner. Writes
    data/members.csv."""
    seen: dict[int, dict[str, Counter]] = {}
    for s in sittings:
        if s.chamber != "DR" or not fetch.cache_path(s.url).exists():
            continue
        for name, m in attendance(read_pdf(fetch.cache_path(s.url), front_only=True)).items():
            seen.setdefault(s.parliament, {}).setdefault(name, Counter())[(m.seat, m.party, m.senator)] += 1
    registers = {p: {name: Member(*c.most_common(1)[0][0]) for name, c in names.items()}
                 for p, names in seen.items()}
    with open(MEMBERS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["parliament", "name_key", "seat", "party", "senator", "lists"])
        for p, names in sorted(seen.items()):
            for name, c in sorted(names.items()):
                m = registers[p][name]
                w.writerow([p, name, m.seat, m.party, int(m.senator), sum(c.values())])
    return registers


def read_registers() -> dict[int, dict[str, Member]]:
    """The registers as `build_registers` last wrote them to data/members.csv."""
    registers: dict[int, dict[str, Member]] = {}
    with open(MEMBERS_OUT, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            registers.setdefault(int(r["parliament"]), {})[r["name_key"]] = Member(r["seat"], r["party"], r["senator"] == "1")
    return registers


def parse_one(s: Sitting, registers: dict[int, dict[str, Member]], missing: str = "") -> tuple[list[Speech], Report]:
    """One sitting's speeches and report; a sitting the parser cannot read gives none and says why."""
    try:
        if missing:
            raise NoPdf(missing)
        lines = read_pdf(fetch.cache_path(s.url))
        return parse_sitting(lines, s, registers.get(s.parliament, {}))
    except NoPdf as e:
        return [], Report(s.chamber, s.date, note=str(e))
    except Exception as e:  # a sitting that breaks the parser is a finding, not a crash
        return [], Report(s.chamber, s.date, note=f"failed: {str(e)[:150]}")


def pilot_days(sittings: list[Sitting]) -> list[Sitting]:
    """Five days spread over each chamber and Parliament."""
    out = []
    groups: dict[tuple[str, int], list[Sitting]] = {}
    for s in sittings:
        groups.setdefault((s.chamber, s.parliament), []).append(s)
    for key in sorted(groups):
        days = sorted(groups[key], key=lambda s: s.date)
        out += [days[i * (len(days) - 1) // 4] for i in range(5)]
    return out


class NoPdf(Exception):
    """The listing gives no PDF for the sitting, or the site cannot serve it."""


REPORT_FIELDS = ["chamber", "date", "pages", "date_in_pdf", "speeches", "named", "resolved", "attendees",
                 "body_chars", "orphan_chars", "unresolved", "note"]


def report_row(r: Report) -> list:
    return [r.chamber, r.date, r.pages, r.date_in_pdf, r.speeches, r.named, r.resolved, r.attendees,
            r.body_chars, r.orphan_chars, " | ".join(r.no_seat)[:1000], r.note]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chamber", choices=["DR", "KK"])
    ap.add_argument("--dates", nargs="+", metavar="ISO")
    ap.add_argument("--pilot", action="store_true", help="five days from each chamber and Parliament")
    args = ap.parse_args()

    sittings = read_csv()
    if args.chamber:
        sittings = [s for s in sittings if s.chamber == args.chamber]
    if args.dates:
        sittings = [s for s in sittings if s.date in args.dates]
    if args.pilot:
        sittings = pilot_days(sittings)

    missing: dict[tuple[str, str], str] = {}  # (chamber, date) of a sitting whose PDF cannot be had: why
    for s in sittings:
        if not s.pdf_path.lower().endswith(".pdf"):
            missing[s.chamber, s.date] = "no PDF in the listing"
            continue
        try:
            fetch.get(s.url)
        except Exception as e:  # one file the site cannot serve is a finding, not a stop
            missing[s.chamber, s.date] = f"download failed: {str(e)[:150]}"
    registers = build_registers(read_csv())
    reports = []
    with open(SPEECHES_OUT, "w", encoding="utf-8") as out:
        for n, s in enumerate(sittings, 1):
            speeches, rep = parse_one(s, registers, missing.get((s.chamber, s.date), ""))
            for sp in speeches:
                out.write(json.dumps(asdict(sp), ensure_ascii=False) + "\n")
            reports.append(rep)
            print(f"{n}/{len(sittings)} {s.chamber} {s.date}: {rep.speeches} speeches, "
                  f"{rep.resolved}/{rep.named} named resolved {rep.note}", flush=True)

    with open(REPORT_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REPORT_FIELDS)
        w.writerows(report_row(r) for r in reports)
    named = sum(r.named for r in reports)
    print(f"{len(reports)} sittings; {sum(r.speeches for r in reports)} speeches; "
          f"{sum(r.resolved for r in reports)} of {named} named speeches resolve to a seat or a Senator; "
          f"date mismatches {sum(1 for r in reports if r.note.startswith('the PDF'))}; "
          f"failed {sum(1 for r in reports if r.note.startswith(('failed', 'no opening')))}; "
          f"no PDF {len(missing)}")


if __name__ == "__main__":
    main()
