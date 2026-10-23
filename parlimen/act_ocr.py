"""Read the image-only Act PDFs: Claude transcribes each page, Tesseract checks it.

A scanned PDF has no text layer, so `parlimen.act_text` cannot read it. Each page is rendered at
300 dpi, turned upright, and read by Claude Haiku and by Tesseract on this machine. The share of
Haiku's words that Tesseract also gives (ignoring order, since the two take table columns in
different orders) marks a hard page: a tilted, faint or crowded scan. Below AGREE, Claude Sonnet
reads the page too, and its text is kept in place of Haiku's. Claude marks a character it cannot
read as [?]; where Tesseract gives the word with that gap filled, its word goes in. A page where
Sonnet and Haiku still differ by more than a few words is flagged for a person to read against
the image. Each reading is cached under data/ocr/, so a re-run spends nothing on pages already
read. `parlimen.act_text` reads the cache in place of the missing text layer.

Measured 2026-10-22 (tools/bench_ocr.py and the pilot on Acts 115, 119, 150, 788): on pages with a
known text layer Haiku and Tesseract got every word right; on scans Tesseract read an italic "(i)"
as "(1)". Haiku misread words on a page stored upside down (now turned first), and on a tilted
page with notes in the margin it moved words between lines and dropped "dalam"; Sonnet read that
page right.

Writes data/act-ocr-report.csv (one row per page). Run:
python -m parlimen.act_ocr [--only NUMBER ...] [--in-force] [--workers 4]
"""

import argparse
import base64
import csv
import io
import json
import re
import subprocess
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import config

OCR = config.DATA / "ocr"
REPORT_OUT = config.DATA / "act-ocr-report.csv"
KEY_FILE = Path.home() / ".claude" / "anthropic-api-key.txt"
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSDATA = config.DATA / "tessdata"  # tessdata_best eng, msa, osd
# Cache name: (model, US$ per million input and output tokens).
READERS = {"claude": ("claude-haiku-5-5", (0.10, 0.50)), "sonnet": ("claude-sonnet-5-5", (2.0, 10.0))}
DPI = 300
MAX_SIDE = 4000  # px; the API refuses an image over 8000 px or 10 MB (Act 544's Malay pages)
ORIENT_CONFIDENCE = 5.0  # below this Tesseract's orientation guess is noise (an upside-down page: 16.6)
AGREE = 0.97  # share of Haiku's words that Tesseract also gives; below it, Sonnet reads the page
SECOND_AGREE = 0.9  # share of Sonnet's words that Haiku also gives; below it, a person looks

BLANK = "[BLANK]"  # Claude's answer for a page with no printed text
PROMPT = (
    "This is one page of a Malaysian Act. Transcribe every word on the page exactly as printed, one "
    "output line for each printed line, including headings, page numbers and footnotes. Do not "
    "correct, complete, modernise or translate anything. Where a character cannot be read, write "
    "[?]. Skip handwriting and stamps. Output plain text only: no Markdown, no bold or italic marks, "
    f"no comments. If the page has no printed text, output only {BLANK}."
)
_lock = threading.Lock()
_pdfium_lock = threading.Lock()


def _cache(pdf: Path, index: int, reader: str) -> Path:
    """data/ocr/<act>/<file stem>/p0001.claude.txt: one folder per PDF, one file per page and reader."""
    return OCR / pdf.parent.name / pdf.stem / f"p{index + 1:04d}.{reader}.txt"


def _words(s: str) -> list[str]:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.findall(r"[0-9A-Za-zÀ-ÿ]+", s.lower())


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _turn(png: bytes) -> int:
    """Degrees the page is turned from upright, by Tesseract's orientation check (0 if unsure)."""
    out = subprocess.run([str(TESSERACT), "stdin", "stdout", "--psm", "0", "--tessdata-dir", str(TESSDATA)],
                         input=png, capture_output=True, timeout=300).stdout.decode("utf-8", "replace")
    turn, conf = re.search(r"Rotate: (\d+)", out), re.search(r"Orientation confidence: ([\d.]+)", out)
    return int(turn.group(1)) if turn and conf and float(conf.group(1)) >= ORIENT_CONFIDENCE else 0


def _render(pdf: Path, index: int) -> bytes:
    """The page at 300 dpi, upright. A scan stored upside down or sideways (a landscape list of
    amendments) is turned first: Haiku misreads words on an upside-down page."""
    import pypdfium2 as pdfium

    with _pdfium_lock:  # pdfium is not thread-safe: two threads loading at once fail with "Data format error"
        doc = pdfium.PdfDocument(str(pdf))
        try:
            img = doc[index].render(scale=DPI / 72, grayscale=True).to_pil()
        finally:
            doc.close()
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    png = _png(img)
    if turn := _turn(png):
        # Try each way round and keep the one the orientation check calls upright.
        for angle in (-turn, turn):
            upright = _png(img.rotate(angle, expand=True))
            if _turn(upright) == 0:
                return upright
    return png


def _tesseract(png: bytes, lang: str) -> str:
    langs = "eng" if lang == "BI" else "msa+eng"
    out = subprocess.run([str(TESSERACT), "stdin", "stdout", "-l", langs, "--tessdata-dir", str(TESSDATA)],
                         input=png, capture_output=True, timeout=300)
    return out.stdout.decode("utf-8", "replace")


def _claude(client, png: bytes, reader: str) -> str:
    model, (price_in, price_out) = READERS[reader]
    msg = client.messages.create(
        model=model, max_tokens=8000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(png).decode()}},
            {"type": "text", "text": PROMPT},
        ]}],
    )
    cost = (msg.usage.input_tokens * price_in + msg.usage.output_tokens * price_out) / 1e6
    with _lock, open(config.USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "job": "act_ocr", "model": model,
                            "endpoint": "messages", "input_tokens": msg.usage.input_tokens,
                            "output_tokens": msg.usage.output_tokens, "cost_usd": round(cost, 6)}) + "\n")
    if msg.stop_reason != "end_turn":
        raise RuntimeError(f"stop_reason {msg.stop_reason}")
    text = "".join(b.text for b in msg.content if b.type == "text")
    return "" if text.strip() == BLANK else text


def _agreement(text: str, other: str) -> tuple[float, Counter, Counter]:
    """Share of `text`'s words that `other` also gives, ignoring order, and the words each has alone."""
    mine, theirs = Counter(_words(text)), Counter(_words(other))
    only_mine = mine - theirs
    return 1 - sum(only_mine.values()) / max(sum(mine.values()), 1), only_mine, theirs - mine


def fill_gaps(text: str, check: str) -> str:
    """Claude's words with a [?] in them, filled from Tesseract's reading where it has one fit.

    "declar[?]tion" takes "declaration" when that is the only word of Tesseract's that fits.
    """
    def fill(m: re.Match) -> str:
        parts = m.group().split("[?]")
        if not any(parts):
            return m.group()
        pattern = r"\S{1,2}".join(re.escape(p) for p in parts)
        fits = set(re.findall(rf"(?<!\S){pattern}(?!\S)", check))
        return fits.pop() if len(fits) == 1 else m.group()

    return re.sub(r"\S*\[\?\]\S*", fill, text)


def read_page(client, pdf: Path, index: int, lang: str) -> dict:
    """The readings of one page, from the cache when present, and how far they agree."""
    paths = {r: _cache(pdf, index, r) for r in ("tesseract", "claude", "sonnet")}
    paths["claude"].parent.mkdir(parents=True, exist_ok=True)
    png = None

    def read(reader: str) -> str:
        nonlocal png
        if not paths[reader].exists():
            png = png or _render(pdf, index)
            text = _tesseract(png, lang) if reader == "tesseract" else _claude(client, png, reader)
            paths[reader].write_text(text, encoding="utf-8")
        return paths[reader].read_text(encoding="utf-8")

    check, haiku = read("tesseract"), read("claude")
    agree, only_haiku, only_check = _agreement(haiku, check)
    row = {"page": index + 1, "words": len(_words(haiku)), "agree": round(agree, 4), "reader": "haiku",
           "only_claude": " ".join(only_haiku.elements()), "only_tesseract": " ".join(only_check.elements())}
    if agree < AGREE:
        second, _, _ = _agreement(read("sonnet"), haiku)
        row.update(reader="sonnet", sonnet_vs_haiku=round(second, 4))
    return row


def ocr_text(pdf: Path, n_pages: int) -> list[str] | None:
    """Each page's text (Sonnet's where it read the page, else Haiku's, gaps filled from Tesseract),
    or None if any page is unread."""
    pages = []
    for i in range(n_pages):
        sonnet, haiku, tess = (_cache(pdf, i, r) for r in ("sonnet", "claude", "tesseract"))
        kept = sonnet if sonnet.exists() else haiku
        if not (kept.exists() and tess.exists()):
            return None
        pages.append(fill_gaps(kept.read_text(encoding="utf-8"), tess.read_text(encoding="utf-8")))
    return pages


def main() -> None:
    import anthropic
    import pypdfium2 as pdfium

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="NUMBER", help="read only these Act numbers")
    ap.add_argument("--in-force", action="store_true", help="read only Acts the listing shows in force")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    with open(config.DATA / "acts.csv", encoding="utf-8") as f:
        in_force = {a["number"] for a in csv.DictReader(f) if a["status"] == "in force"}

    # Scanned files: unread ones are image_only in the parse report, read ones have source ocr.
    with open(config.DATA / "act-parse-report.csv", encoding="utf-8") as f:
        files = [r for r in csv.DictReader(f) if r["kind"] == "image_only" or r.get("source") == "ocr"]
    if args.only:
        files = [r for r in files if r["act"] in args.only]
    if args.in_force:
        files = [r for r in files if r["act"] in in_force]
    client = anthropic.Anthropic(api_key=KEY_FILE.read_text().strip(), max_retries=4)

    jobs = []
    for r in files:
        pdf = config.ACTS / r["file"]
        doc = pdfium.PdfDocument(str(pdf))
        jobs += [(r, pdf, i) for i in range(len(doc))]
        doc.close()
    print(f"{len(files)} files, {len(jobs)} pages", flush=True)

    def run(job):
        r, pdf, i = job
        try:
            return r, read_page(client, pdf, i, r["lang"])
        except Exception as e:  # a page that fails is reported and read again on the next run
            return r, {"page": i + 1, "error": str(e)[:200]}

    rows = []
    with ThreadPoolExecutor(args.workers) as pool:
        for n, (r, res) in enumerate(pool.map(run, jobs), 1):
            rows.append({"act": r["act"], "lang": r["lang"], "file": r["file"], **res})
            if n % 25 == 0:
                print(f"{n} of {len(jobs)} pages", flush=True)

    def flag(x: dict) -> str:
        if "error" in x:
            return "error"
        return "check" if x.get("sonnet_vs_haiku", 1.0) < SECOND_AGREE else ""

    with open(REPORT_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["act", "lang", "file", "page", "words", "agree", "reader", "sonnet_vs_haiku", "flag",
                    "only_claude", "only_tesseract", "error"])
        for x in rows:
            w.writerow([x["act"], x["lang"], x["file"], x["page"], x.get("words", ""), x.get("agree", ""),
                        x.get("reader", ""), x.get("sonnet_vs_haiku", ""), flag(x),
                        x.get("only_claude", "")[:1000], x.get("only_tesseract", "")[:1000], x.get("error", "")])
    counts = Counter(flag(x) for x in rows)
    sonnet = sum(1 for x in rows if x.get("reader") == "sonnet")
    print(f"{len(rows)} pages; {sonnet} read again by Sonnet; {counts['check']} flagged to check; "
          f"{counts['error']} errors; report {REPORT_OUT.name}")


if __name__ == "__main__":
    main()
