"""Split each cached Act PDF into its sections.

The arrangement of sections at the front of an Act lists every section number and heading in
order, with the Parts and Chapters they sit in. The parser reads that list, then finds each
section in the body in the same order: the heading on its own line, then a line starting with
the section number ("3. (1) The Yang di-Pertuan Agong may ..."). A section the body does not show
is reported, never guessed. Text comes from pdfium, which reads the 2006 reprints' font
correctly. A scanned file with no text layer is parsed from its OCR reading (`parlimen.act_ocr`)
when every page has one, and reported as image_only when not. Repeal notices and "no Malay text"
covers are reported with their kind and not parsed.

Writes data/act_sections.jsonl (one record per section and language) and
data/act-parse-report.csv (one row per file).

Run: python -m parlimen.act_text [--only NUMBER ...]
"""

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from . import config

SECTIONS_OUT = config.DATA / "act_sections.jsonl"
REPORT_OUT = config.DATA / "act-parse-report.csv"

MIN_CHARS_PER_PAGE = 200  # below this a file is an image with no text layer
# Acts the listing shows in force whose repeal another Act states. Their files are not current text.
REPEALED_ELSEWHERE = {
    "175": "repealed by the Trademarks Act 2019 [Act 815], s. 164; the file is the 1976 text "
           "with amendments marked by hand",
}
CLOSE_HEADING = 0.85      # similarity at which a body heading counts as the arrangement's heading

# Malay of the 1960s spells "Sekshen", "Suatu Act", "MAKA INI-LAH DI-PERBUAT" (Act 408).
_ARRANGEMENT = re.compile(r"ARRANGEMENT OF (SECTIONS|ARTICLES|CLAUSES)|SUSUNAN (SEKSYEN|SEKSHEN|PERKARA)", re.I)
_BODY = re.compile(r"^(An Act|An Ordinance|An Enactment|Suatu Akta|Suatu Act|Suatu Ordinan|Suatu Enakmen|"
                   r"(BE IT )?ENACTED|DIPERBUAT|MAKA INI-?LAH|WHEREAS|BAHAWASANYA)\b", re.I)
# "PART III", "Part One (A)—COMPUTERIZED LAND REGISTRATION SYSTEM", "Chapter 1—Powers of ...":
# the title follows on the next line or after a dash on the same line.
_WORD_NUMBERS = (r"One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|Thirteen|Fourteen|"
                 r"Fifteen|Sixteen|Seventeen|Eighteen|Nineteen|Twenty")
_PART = re.compile(rf"^(PART|BAHAGIAN)\s+([IVXLC]+[A-Z]{{0,2}}|(?:{_WORD_NUMBERS})(?:\s*\([A-Z]\))?)"
                   rf"(?:\s*[—–-]\s*(.+))?$", re.I)
_CHAPTER = re.compile(r"^(CHAPTER|BAB)\s+(\d+[A-Z]{0,2}|[IVXLC]+)(?:\s*[—–-]\s*(.+))?$", re.I)
_LABEL = re.compile(r"^(Sections?|Seksyen|Sekshen)$", re.I)
_NUM = r"\d+[A-Za-z]{0,3}"
_ENTRY = re.compile(rf"^({_NUM})\s*\.\s*(.*)$")
_RANGE = re.compile(rf"^({_NUM})\s*(?:-|–|—|to|hingga)\s*({_NUM})\s*\.\s*(.*)$")
_SCHEDULE = re.compile(r"^((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|"
                       r"TWELFTH)\s+)?SCHEDULES?$|^JADUAL(\s+[A-Z]+)?$")
# The body ends here; an appendix (an appended amending Act, a table of State adoptions) is not section text.
_END = re.compile(r"^(LIST OF AMENDMENTS|SENARAI PINDAAN|LIST OF SECTIONS AMENDED|"
                  r"SENARAI SEKSYEN YANG DIPINDA|(?-i:(?:APPENDIX|LAMPIRAN)$))", re.I)
# printer stamps: "Act 265.indd 20", "012e.fm Page 3 Monday, ...", "029B.FM Page 4 ..."
_FOOTER = re.compile(r"\.indd\b|\.fm\s+Page\s+\d+", re.I)
_EDGE = 2  # lines at the top and at the bottom of a page where running heads sit
_NOTE_SIZE = 0.85  # a note's type is at most this share of the body text's size
_NOTE_START = re.compile(r"^[*†‡]+\s*\S|^(NOTE|CATATAN)\b")
_SCHEDULE_ENTRY = re.compile(r"^(\w+\s+)?(SCHEDULES?|JADUAL)\b", re.I)
_TITLE_BLOCK = re.compile(r"^(LAWS OF MALAYSIA|UNDANG-UNDANG MALAYSIA)$", re.I)
_NOTICE = re.compile(r"\b(repealed|dimansuhkan|superseded|diganti\w*|ceased to have effect|terhenti berkuat kuasa|"
                     r"tidak mempunyai apa-apa kuat kuasa|no force of law)\b", re.I)


@dataclass
class Line:
    page: int
    text: str
    small: bool = False  # set in smaller type than the body text
    note: bool = False   # part of an editorial note at the foot of the page


@dataclass
class Entry:
    """One section as the arrangement lists it."""
    number: str           # "18A"; a range of deleted sections is "34-36"
    heading: str
    part: str = ""        # "Part III"
    part_title: str = ""
    chapter: str = ""
    chapter_title: str = ""


@dataclass
class Section:
    act: str
    lang: str
    as_at: str
    number: str
    heading: str
    part: str
    part_title: str
    chapter: str
    chapter_title: str
    text: str
    notes: str             # editorial notes printed at the foot of the section's pages
    page_start: int
    page_end: int
    # Where the heading comes from: "exact" (the body's heading line matches the arrangement),
    # "close" (the body's wording differs a little; heading holds the body's wording),
    # "arrangement" (no heading line found above the number) or "deleted" (none expected).
    heading_source: str
    source: str = "text"   # "text" (the PDF's text layer) or "ocr" (a reading of the scanned page)


@dataclass
class FileReport:
    act: str
    lang: str
    file: str
    kind: str = "text"     # text, image_only, notice, no_malay, wrong_language, failed
    pages: int = 0
    listed: int = 0        # entries in the arrangement
    found: int = 0
    heading_close: int = 0     # body heading differs a little from the arrangement
    heading_missing: int = 0   # no heading line found above the section number
    missing: list[str] = field(default_factory=list)
    text_lang: str = ""        # language the text is in (BI or BM), whatever the listing says
    source: str = "text"       # "text" or "ocr", as for Section
    note: str = ""


def norm_number(n: str) -> str:
    return re.sub(r"\s+", "", n).upper()


def _leading_int(number: str) -> int:
    """"18A" -> 18, "34-36" -> 34."""
    return int(re.match(r"\d+", number).group())


def _label_number(n: str) -> str:
    """"iii" -> "III", "ONE (A)" -> "One (A)"."""
    return n.upper() if re.fullmatch(r"[IVXLC]+[A-Z]{0,2}|\d+[A-Z]{0,2}", n, re.I) else n.title()


def _squash(s: str) -> str:
    return re.sub(r"[^0-9a-z]", "", s.lower())


_SPACED = re.compile(r"(?:\S ){4,}\S")  # "b y s u b s t i t u t i n g": letter-spaced type


def _page_lines(textpage) -> list[tuple[str, float]]:
    """The page's non-empty lines, each with its font size, letter-spaced words put back together.

    For letter-spaced type pdfium puts a space it generated between every two letters, and no
    wider one between words. The character boxes still show the word breaks: the gap between
    words is several times the gap between letters. A run with any real space in it is
    ordinary text and stays as it is.
    """
    import pypdfium2.raw as pdfium_c

    def respace(m: re.Match, base: int) -> str | None:
        span = range(base + m.start(), base + m.end())
        if not all(pdfium_c.FPDFText_IsGenerated(textpage.raw, i) for i in span if text[i] == " "):
            return None
        letters = [i for i in span if text[i] != " "]
        boxes = [textpage.get_charbox(i) for i in letters]
        gaps = [boxes[k + 1][0] - boxes[k][2] for k in range(len(boxes) - 1)]
        gap = statistics.median(gaps)
        width = statistics.median(b[2] - b[0] for b in boxes)
        word_break = max(2 * gap, gap + width / 2)
        return text[letters[0]] + "".join((" " if g > word_break else "") + text[i]
                                          for g, i in zip(gaps, letters[1:]))

    text = textpage.get_text_range()
    out = []
    for line in re.finditer(r"[^\r\n]+", text):
        s = line.group()
        if not s.strip():
            continue
        pieces, last = [], 0
        for m in _SPACED.finditer(s):
            if (rebuilt := respace(m, line.start())) is not None:
                pieces += [s[last:m.start()], rebuilt]
                last = m.end()
        sizes = [pdfium_c.FPDFText_GetFontSize(textpage.raw, i)
                 for i in range(line.start(), line.end(), 3) if not text[i].isspace()]
        out.append(("".join(pieces + [s[last:]]).strip(), statistics.median(sizes) if sizes else 0.0))
    return out


def pdf_pages(path: Path) -> list[list[tuple[str, float]]]:
    """Each page's lines from the PDF's text layer, with their font sizes."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        return [_page_lines(doc[i].get_textpage()) for i in range(len(doc))]
    finally:
        doc.close()


_OCR_NOTE = re.compile(r"^[*†‡]*\s*(NOTE|CATATAN)\b")
# A margin note read into the line in front of a section number: "Sharat² 4. (1) Pengerusi ...".
# One to three words with no digit, and not a cross-reference ("under section 4. (1)").
_MARGIN_LEAD = re.compile(r"^((?:[^\s\d]+\s+){1,3}?)(\d+[A-Z]{0,2}\.\s+(?:\(\d+\)\s+)?[A-Z\"“(].*)$")
_REFERENCE_WORD = re.compile(r"(section|seksyen|sekshen|subsection|subseksyen|paragraph|perenggan|Act|Akta|"
                             r"and|or|dan|atau|of|to|in|under|di-bawah|dibawah|No)\s*$", re.I)


# A margin heading closed by a full stop, as older Acts print them: "Umur minimum untuk
# per-kahwinan. 8. Tiada ...", "Pindaan seksyen 39. 9. Subseksyen ...".
_MARGIN_HEADING = re.compile(r"^([A-Z]\S*(?:\s+\S+){0,7}\.)\s+(\d+[A-Z]{0,2}\.\s+(?:\(\d+\)\s+)?[A-Z\"“(].*)$")


def _split_margin_lead(line: str) -> list[str]:
    if m := _MARGIN_HEADING.match(line):
        return [m.group(1), m.group(2)]
    m = _MARGIN_LEAD.match(line)
    if not m or _REFERENCE_WORD.search(m.group(1)):
        return [line]
    return [m.group(1).strip(), m.group(2)]


def ocr_pages(path: Path, n_pages: int) -> list[list[tuple[str, float]]] | None:
    """Each page's lines from the OCR cache (`parlimen.act_ocr`), or None if a page is unread.

    A reading has no font sizes, so the editorial note that closes a page ("*NOTE—...") and the
    lines after it are given a small size, and every other line the body size.
    """
    from .act_ocr import ocr_text

    texts = ocr_text(path, n_pages)
    if texts is None:
        return None
    pages = []
    for t in texts:
        # A tab parts a margin note from the text beside it. A line of nothing but unreadable
        # marks ("[?] [?]") is a speck on the scan, not text.
        lines = [part for ln in re.split(r"[\t\n]", t) if re.search(r"\w", ln.replace("[?]", ""))
                 for part in _split_margin_lead(ln.strip())]
        note = next((k for k, ln in enumerate(lines) if _OCR_NOTE.match(ln)), len(lines))
        pages.append([(ln, 1.0 if k < note else 0.5) for k, ln in enumerate(lines)])
    return pages


def read_lines(path: Path, pages: list[list[tuple[str, float]]] | None = None) -> tuple[list[Line], int]:
    """Every non-empty line of the PDF with its page, minus running heads and printer footers.

    `pages` replaces the PDF's text layer (an OCR reading of a scanned PDF).
    """
    if pages is None:
        pages = pdf_pages(path)
    chars = sum(len(t) + 2 for lines in pages for t, _ in lines)  # with its line break, as pdfium counts
    per_page = [[t for t, _ in lines] for lines in pages]
    sizes = [[size for _, size in lines] for lines in pages]
    weights = Counter()
    for lines in pages:
        for t, size in lines:
            weights[round(size * 2) / 2] += len(t)
    body_size = weights.most_common(1)[0][0] if weights else 0.0

    # A running head ("20 Laws of Malaysia Act 265", "Employment 13") carries the printed page
    # number, which runs at a fixed offset from the PDF page; a reprint of an older book can
    # carry the book's own numbers too ("48 Act 828"), at a second offset. A head's words,
    # digits aside, are its key. pdfium may split the number from the words, or emit the head
    # mid-page, so a line goes when it sits at a page edge with a head's key, or anywhere with a
    # head's key and the page's own number. Headings such as "Pindaan seksyen 2" repeat their
    # words too, but their numbers do not follow the pages.
    def key(s: str) -> str:
        return _squash(re.sub(r"\d+", "", s))

    def page_number(s: str) -> int | None:
        m = re.match(r"^(\d+)(\s|$)", s) or re.search(r"\s(\d+)$", s)
        return int(m.group(1)) if m else None

    edge_lines = [(i, ln) for i, lines in enumerate(per_page) for ln in lines[:_EDGE] + lines[-_EDGE:]]
    # The commonest offset is the page numbering; a second one needs a third of the pages, since
    # headings like "Pindaan seksyen 54" put stray numbers at page edges too.
    counts = Counter(n - (i + 1) for i, ln in edge_lines if (n := page_number(ln)) is not None)
    offsets = {o for o, n in counts.most_common(1)} | {o for o, n in counts.items() if n >= max(3, len(pages) // 3)}
    # A bare number or a number-led head at a page edge ("47", "48 Act 828") is distinctive
    # enough to trust a numbering that runs only a few pages, as a reprinted book's own page
    # numbers do between inserted pages: a neighbouring page must carry the same offset.
    page_offsets = [{n - (i + 1) for ln in lines[:_EDGE] + lines[-_EDGE:] if (n := page_number(ln)) is not None}
                    for i, lines in enumerate(per_page)]

    def own_number(ln: str, i: int, weak: bool = False) -> bool:
        n = page_number(ln)
        if n is None:
            return False
        o = n - (i + 1)
        near = range(max(0, i - 2), min(len(per_page), i + 3))
        return o in offsets or (weak and any(o in page_offsets[j] for j in near if j != i))

    # The odd-page head is the Act's short title, as on the cover ("Employment 13").
    cover = key(" ".join(per_page[0])) if per_page else ""

    def head_like(ln: str, i: int) -> bool:
        if len(ln.split()) > 12 or re.search(r"[.,;:—]$", ln):
            return False
        if re.match(r"^\d+\s", ln):
            return own_number(ln, i, weak=True)
        return own_number(ln, i) and len(key(ln)) >= 4 and key(ln) in cover

    heads = Counter(key(ln) for i, ln in edge_lines if head_like(ln, i))
    furniture = {k for k, n in heads.items() if k and n >= 2}
    out = []
    for i, lines in enumerate(per_page):
        kept = []
        for k, ln in enumerate(lines):
            at_edge = k < _EDGE or k >= len(lines) - _EDGE
            own = own_number(ln, i)
            is_head = (at_edge and head_like(ln, i)) or (key(ln) in furniture and (at_edge or own))
            bare_number = ln.isdigit() and (own or (at_edge and own_number(ln, i, weak=True)))
            if _FOOTER.search(ln) or is_head or bare_number:
                continue
            kept.append(Line(i + 1, ln, small=sizes[i][k] <= _NOTE_SIZE * body_size))
        # Editorial notes ("*NOTE—see P.U. (A) 450/2017") close the page in small type.
        start = len(kept)
        while start > 0 and kept[start - 1].small:
            start -= 1
        first_note = next((k for k in range(start, len(kept)) if _NOTE_START.match(kept[k].text)), None)
        for ln in kept[first_note:] if first_note is not None else []:
            ln.note = True
        out.extend(kept)
    return out, round(chars / max(len(pages), 1))


def parse_arrangement(lines: list[Line]) -> list[Entry]:
    """The section entries between the arrangement heading and the body, in order."""
    entries: list[Entry] = []
    part = part_title = chapter = chapter_title = ""
    collecting = None  # "part", "chapter" or "entry": where a continuation line belongs
    schedule_lines: list[str] = []  # list of schedules, or a heading that wraps onto "Schedule"
    in_schedules = False
    for ln in lines:
        t = ln.text
        if _END.match(t):
            break
        if _TITLE_BLOCK.match(t):
            # The page's own title block ("LAWS OF MALAYSIA", "Act 775", the title), which pdfium
            # may read after the entries: none of it continues a heading.
            collecting = None
            continue
        # "FIRST SCHEDULE" starts the list of schedules, which may number its forms "1.", "2.".
        # A Part or a section number past the last one means the sections go on (Act 829 puts
        # a schedule between Parts II and III).
        if _SCHEDULE_ENTRY.match(t) and t.isupper():
            in_schedules = True
            continue
        if in_schedules:
            m = _ENTRY.match(t) or _RANGE.match(t)
            if not (_PART.match(t) or (m and entries and _leading_int(m.group(1)) > _leading_int(entries[-1].number))):
                continue
            in_schedules = False
        if _SCHEDULE_ENTRY.match(t) or schedule_lines:
            if _ENTRY.match(t) or _RANGE.match(t) or _PART.match(t):
                # a section follows, so the "Schedule" line was the end of a wrapped heading
                if entries:
                    entries[-1].heading = " ".join([entries[-1].heading, *schedule_lines])
                schedule_lines = []
            else:
                schedule_lines.append(t)
                continue
        if m := _PART.match(t):
            part, part_title, chapter, chapter_title = f"Part {_label_number(m.group(2))}", m.group(3) or "", "", ""
            collecting = "part"
        elif m := _CHAPTER.match(t):
            chapter, chapter_title = f"Chapter {_label_number(m.group(2))}", m.group(3) or ""
            collecting = "chapter"
        elif _LABEL.match(t):
            continue
        elif m := _RANGE.match(t):
            entries.append(Entry(f"{norm_number(m.group(1))}-{norm_number(m.group(2))}", m.group(3),
                                 part, part_title, chapter, chapter_title))
            collecting = "entry"
        elif m := _ENTRY.match(t):
            entries.append(Entry(norm_number(m.group(1)), m.group(2), part, part_title, chapter, chapter_title))
            collecting = "entry"
        elif collecting == "part":
            part_title = f"{part_title} {t}".strip()
        elif collecting == "chapter":
            chapter_title = f"{chapter_title} {t}".strip()
        elif collecting == "entry":
            entries[-1].heading = f"{entries[-1].heading} {t}".strip()
    # Overprinted bold type reaches pdfium twice; the second copy repeats a number, headless.
    seen: set[str] = set()
    kept = []
    for e in entries:
        if e.number in seen and not e.heading:
            continue
        seen.add(e.number)
        kept.append(e)
    return kept


def _number_pattern(number: str) -> re.Pattern:
    """A body line that opens the section; "*" or "†" before the number points to a footnote."""
    if "-" in number:
        a, b = number.split("-")
        return re.compile(rf"^[*†‡]*\s*{re.escape(a)}\s*(?:-|–|—|to|hingga)\s*{re.escape(b)}\s*\.(\s|\(|$)", re.I)
    return re.compile(rf"^[*†‡]*\s*{re.escape(number)}\s*\.(\s|\(|$)", re.I)


def _heading_span(body: list[Line], i: int, heading: str, floor: int, close: bool = False) -> int:
    """How many lines above body[i] spell the heading (0 when they do not).

    With close=True, lines that differ from the arrangement's wording in a word or two
    ("Provision of" against "Provisions of") also count.
    """
    want = _squash(heading)
    if not want:
        return 0
    got = ""
    for k in range(1, 5):
        if i - k < floor:
            break
        got = _squash(body[i - k].text) + got
        if got == want:
            return k
        if close and abs(len(got) - len(want)) <= max(4, len(want) // 8) \
                and SequenceMatcher(None, got, want).ratio() >= CLOSE_HEADING:
            return k
        if not close and not want.endswith(got):
            break
    return 0


def _is_deleted(entry: Entry) -> bool:
    return bool(re.match(r"^\((Deleted|Omitted|Dipotong|Ditinggalkan)", entry.heading, re.I)) or "-" in entry.number


_CONFIRMED = ("exact", "close")  # heading sources that prove a candidate is the section itself


def locate(entries: list[Entry], body: list[Line]) -> list[tuple[Entry, int, int, str]]:
    """For each entry, its line in the body and the lines its heading takes, in order.

    A candidate whose heading matches wins over an earlier one that does not. A section with no
    heading line to confirm it (a deleted section has none) is taken at its first candidate, but
    it does not move the search on, and it is dropped when it lands outside its confirmed
    neighbours: a stray "65." in a schedule table must not hide every section after it. An entry
    with no candidate is left out; the caller reports it.
    """
    found = []
    ptr = 0
    for e in entries:
        rx = _number_pattern(e.number)
        candidates = [i for i in range(ptr, len(body)) if rx.match(body[i].text)]
        if not candidates:
            continue
        pick, span, how = candidates[0], 0, "deleted" if _is_deleted(e) else "arrangement"
        if how != "deleted":
            for close, label in ((False, "exact"), (True, "close")):
                hit = next(((i, s) for i in candidates if (s := _heading_span(body, i, e.heading, ptr, close))), None)
                if hit:
                    (pick, span), how = hit, label
                    break
        found.append((e, pick, span, how))
        if how in _CONFIRMED:
            ptr = pick + 1

    kept, last = [], -1
    for n, item in enumerate(found):
        _, i, _, how = item
        if how not in _CONFIRMED:
            nxt = next((j for _, j, _, h in found[n + 1:] if h in _CONFIRMED), len(body))
            if not last < i < nxt:
                continue
        kept.append(item)
        last = i
    return kept


def _trim_tail(lines: list[Line], entries: list[Entry]) -> list[Line]:
    """Drop Part and Chapter headings that sit between a section and the next one's heading."""
    titles = {_squash(t) for e in entries for t in (e.part_title, e.chapter_title) if t}
    out = list(lines)
    while out:
        t = out[-1].text
        if _PART.match(t) or _CHAPTER.match(t) or _squash(t) in titles:
            out.pop()
            continue
        # a title that wraps over two lines
        if len(out) >= 2 and _squash(out[-2].text + out[-1].text) in titles:
            out = out[:-2]
            continue
        break
    return out


def parse_file(path: Path, act: str, lang: str, as_at: str) -> tuple[list[Section], FileReport]:
    rep = FileReport(act, lang, f"{path.parent.name}/{path.name}")
    if act in REPEALED_ELSEWHERE:
        rep.kind, rep.note = "notice", REPEALED_ELSEWHERE[act]
        return [], rep
    pages = pdf_pages(path)
    lines, chars_per_page = read_lines(path, pages)

    def cover_kind() -> str:
        head = " ".join(ln.text for ln in lines[:40])
        if rep.pages <= 3 and _NOTICE.search(head):
            return "notice"  # repealed, superseded, ceased or without legal force: no sections
        return "no_malay" if re.search(r"Tiada teks bahasa kebangsaan", head, re.I) else ""

    # A notice or cover is short and may carry too little text to pass for a text file, so its
    # kind is decided first.
    rep.pages = max((ln.page for ln in lines), default=0)
    if kind := cover_kind():
        rep.kind = kind
        return [], rep
    if chars_per_page < MIN_CHARS_PER_PAGE:
        # A scanned PDF: its OCR reading, when every page has one, stands in for the text layer.
        if (pages := ocr_pages(path, len(pages))) is None:
            rep.kind = "image_only"
            return [], rep
        lines, _ = read_lines(path, pages)
        rep.source = "ocr"
        rep.pages = max((ln.page for ln in lines), default=0)
        if kind := cover_kind():
            rep.kind = kind
            return [], rep

    arr = next((k for k, ln in enumerate(lines) if _ARRANGEMENT.search(ln.text)), None)
    start = next((k for k in range((arr or 0) + 1, len(lines)) if _BODY.match(lines[k].text)), None)
    if start is None and arr is not None:
        # A long title the parser cannot read ("Surat Akta" for "Suatu Akta" in Act 424): the
        # title block that opens the body comes next.
        start = next((k for k in range(arr + 1, len(lines)) if _TITLE_BLOCK.match(lines[k].text)), None)
    if start is None:
        rep.kind, rep.note = "failed", "no body start (long title or enacting words) found"
        return [], rep
    if arr is None:
        entries = _entries_without_arrangement(lines[start:])
        rep.note = "no arrangement; sections numbered 1, 2, 3 ... from the body"
    else:
        # The arrangement starts at the top of its heading's page, since pdfium may read the
        # heading after the entries. The body opens on a new page with the Act's title block, so
        # lines on that page belong to the arrangement only when the arrangement starts there.
        top = next(k for k, ln in enumerate(lines) if ln.page == lines[arr].page)
        body_page = lines[start].page
        entries = parse_arrangement([ln for ln in lines[top:start]
                                     if ln.page != body_page or lines[arr].page == body_page])
    rep.listed = len(entries)

    body = lines[start:]
    found = locate(entries, body)
    rep.found = len(found)
    located = {e.number for e, *_ in found}
    rep.missing = [e.number for e in entries if e.number not in located]

    sections = []
    for n, (e, i, span, how) in enumerate(found):
        if n + 1 < len(found):
            _, j, next_span, _ = found[n + 1]
            stop = j - next_span
        else:
            stop = next((k for k in range(i + 1, len(body)) if _SCHEDULE.match(body[k].text) or _END.match(body[k].text)),
                        len(body))
        chunk = _trim_tail(body[i:stop], entries)
        heading = " ".join(ln.text for ln in body[i - span:i]) if how == "close" else e.heading
        rep.heading_close += how == "close"
        rep.heading_missing += how == "arrangement"
        sections.append(Section(
            act=act, lang=lang, as_at=as_at, number=e.number, heading=heading,
            part=e.part, part_title=e.part_title, chapter=e.chapter, chapter_title=e.chapter_title,
            text="\n".join(ln.text for ln in chunk if not ln.note),
            notes="\n".join(ln.text for ln in chunk if ln.note), page_start=body[i].page,
            page_end=chunk[-1].page if chunk else body[i].page, heading_source=how, source=rep.source,
        ))
    rep.text_lang = text_language(sections[0].text if sections else "", [e.heading for e in entries])
    if rep.text_lang != lang:
        # The portal serves the other language's text under this label (Act 337 "English" is
        # Malay). The sections carry the language they are in; the caller keeps them only when
        # no file of that language has text.
        rep.kind, rep.note = "wrong_language", f"the text is in {rep.text_lang}"
        for s in sections:
            s.lang = rep.text_lang
    return sections, rep


_ENGLISH = {"the", "of", "and", "or", "to", "in", "for", "amendment", "section", "power", "new"}
_MALAY = {"yang", "dan", "atau", "dalam", "kepada", "bagi", "pindaan", "seksyen", "kuasa", "baharu"}


def text_language(first_section: str, headings: list[str]) -> str:
    """BI or BM, by the short-title clause, else by the commonest words of the headings.

    Not by the text at large: a Malay Finance Act quotes long English passages of the tax Acts
    it amends, which exist in English only.
    """
    if re.search(r"\bmay be cited\b", first_section):
        return "BI"
    if re.search(r"\bboleh-?lah di-?namakan\b", first_section):
        return "BM"
    words = Counter(w for h in headings for w in h.lower().split())
    return "BI" if sum(words[w] for w in _ENGLISH) > sum(words[w] for w in _MALAY) else "BM"


def _entries_without_arrangement(body: list[Line]) -> list[Entry]:
    """A short Act with no arrangement: sections 1, 2, 3 ... in order.

    The heading is the lines just above the number, back to the line that ends the text before
    it ("... as follows:", "... this Act."); a heading line never ends a sentence.
    """
    entries = []
    n = 1
    for k, ln in enumerate(body):
        if _number_pattern(str(n)).match(ln.text):
            top = k
            while top > max(0, k - 3) and not re.search(r"[.;:,—”\"]$", body[top - 1].text):
                top -= 1
            entries.append(Entry(str(n), " ".join(x.text for x in body[top:k])))
            n += 1
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="NUMBER", help="parse only these Act numbers")
    args = ap.parse_args()

    with open(config.DATA / "acts.csv", encoding="utf-8") as f:
        acts = list(csv.DictReader(f))
    if args.only:
        acts = [a for a in acts if a["number"] in args.only]

    reports: list[FileReport] = []
    by_act: dict[str, dict[str, set[str]]] = {}
    with open(SECTIONS_OUT, "w", encoding="utf-8") as out:
        for a in acts:
            folder = config.ACTS / re.sub(r"[^A-Za-z0-9]+", "-", a["number"]).strip("-")
            results = []
            for lang in ("BI", "BM"):
                path = folder / f"{lang}-{a['as_at'] or a['status']}.pdf"
                if not path.exists():
                    continue
                try:
                    results.append(parse_file(path, a["number"], lang, a["as_at"]))
                except Exception as e:  # a file that breaks the parser is a finding, not a crash
                    results.append(([], FileReport(a["number"], lang, path.name, kind="failed", note=str(e)[:200])))
            # A file in the wrong language counts only where no file of that language has text
            # (Act 104 has one PDF, labelled English, in Malay).
            have = {rep.lang for _, rep in results if rep.kind == "text"}
            langs = by_act.setdefault(a["number"], {})
            for sections, rep in results:
                reports.append(rep)
                if rep.kind == "wrong_language" and rep.text_lang in have:
                    continue
                for s in sections:
                    langs.setdefault(s.lang, set()).add(s.number)
                    out.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")

    with open(REPORT_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["act", "lang", "file", "kind", "source", "text_lang", "pages", "listed", "found", "heading_close",
                    "heading_missing", "missing", "only_in_this_language", "note"])
        for r in reports:
            other = by_act[r.act].get("BM" if r.lang == "BI" else "BI")
            mine = by_act[r.act].get(r.lang, set()) if r.kind == "text" else set()
            only = sorted(mine - other) if other else []
            w.writerow([r.act, r.lang, r.file, r.kind, r.source, r.text_lang, r.pages, r.listed, r.found, r.heading_close,
                        r.heading_missing, " ".join(r.missing), " ".join(only), r.note])

    kinds = Counter(r.kind for r in reports)
    text = [r for r in reports if r.kind == "text"]
    print(f"{len(reports)} files: {dict(kinds)}")
    print(f"sections listed {sum(r.listed for r in text)}, found {sum(r.found for r in text)}, "
          f"headings close {sum(r.heading_close for r in text)}, "
          f"headings not found {sum(r.heading_missing for r in text)}")
    both = [langs for langs in by_act.values() if langs.get("BI") and langs.get("BM")]
    print(f"Acts parsed in both languages: {len(both)}, "
          f"with different section numbers: {sum(1 for langs in both if langs['BI'] != langs['BM'])}")
    print(f"files with every listed section found: {sum(1 for r in text if r.listed and not r.missing)} of {len(text)}")
    wrong = [f"{r.act} {r.lang}" for r in reports if r.kind == "wrong_language"]
    print(f"files whose text is in the other language: {len(wrong)} ({', '.join(wrong)})")
    print(f"written: {SECTIONS_OUT.name}, {REPORT_OUT.name}")


if __name__ == "__main__":
    main()
