"""Compare Tesseract and Claude as readers of the scanned (image-only) Act PDFs.

Two page sets:
- known: pages that have a text layer, rendered to images, so the text layer is the right answer;
- scanned: pages from image-only PDFs, where a person compares the readers against the image.

Each page is rendered at 300 dpi, read by Tesseract (local) and by Claude (API, usage logged),
and scored against the text layer where there is one: the share of the right words each reader
gives in order, and the words it adds that the page does not have. Results go to
data/bench/ocr/.

Run: python tools/bench_ocr.py [--readers tesseract haiku] [--no-api]
"""

import argparse
import base64
import io
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import anthropic
import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parlimen import config  # noqa: E402
from parlimen.act_text import _page_lines  # noqa: E402

OUT = config.DATA / "bench" / "ocr"
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSDATA = config.DATA / "tessdata"  # tessdata_best eng, msa, osd
DPI = 300

# (act folder, file language, page). Known pages: 2006 reprints like the scanned ones, plus one
# modern reprint. Scanned pages: three of the five in-force Acts with no text at all.
KNOWN = [("588", "BI", 29), ("588", "BM", 31), ("711", "BM", 10)]
SCANNED = [("115", "BI", 6), ("150", "BM", 8), ("788", "BI", 12)]

MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0)}  # US$ per million tokens
PROMPT = (
    "This is one page of a Malaysian Act. Transcribe every word on the page exactly as printed, line by "
    "line, including headings, page numbers and footnotes. Do not correct, complete, modernise or "
    "translate anything. Where a character cannot be read, write [?]. Output only the page's text."
)
_lock = threading.Lock()


def words(s: str) -> list[str]:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.findall(r"[0-9A-Za-zÀ-ÿ]+", s.lower())


def render(act: str, lang: str, page: int) -> tuple[bytes, str]:
    """The page as a 300 dpi greyscale PNG, and its text layer ("" for a scanned page)."""
    pdf = next((config.ACTS / act).glob(f"{lang}-*.pdf"))
    doc = pdfium.PdfDocument(str(pdf))
    try:
        p = doc[page - 1]
        img = p.render(scale=DPI / 72, grayscale=True).to_pil()
        truth = "\n".join(t for t, _ in _page_lines(p.get_textpage()))
    finally:
        doc.close()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), truth


def read_tesseract(png: Path, lang: str) -> str:
    langs = "eng" if lang == "BI" else "msa+eng"
    out = subprocess.run([str(TESSERACT), str(png), "stdout", "-l", langs, "--tessdata-dir", str(TESSDATA)],
                         capture_output=True, timeout=300)
    return out.stdout.decode("utf-8", "replace")


def read_claude(client, model: str, png_bytes: bytes) -> tuple[str, dict]:
    msg = client.messages.create(
        model=model, max_tokens=8000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(png_bytes).decode()}},
            {"type": "text", "text": PROMPT},
        ]}],
    )
    pin, pout = PRICES[model]
    cost = (msg.usage.input_tokens * pin + msg.usage.output_tokens * pout) / 1e6
    entry = {"at": datetime.now(timezone.utc).isoformat(), "job": "bench_ocr", "model": model,
             "endpoint": "messages", "input_tokens": msg.usage.input_tokens,
             "output_tokens": msg.usage.output_tokens, "cost_usd": round(cost, 6)}
    with _lock, open(config.USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    text = "".join(b.text for b in msg.content if b.type == "text")
    return text, entry


def score(truth: str, got: str) -> dict:
    t, g = words(truth), words(got)
    sm = SequenceMatcher(None, t, g, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    added = [w for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("insert", "replace") for w in g[j1:j2]]
    return {"truth_words": len(t), "right_in_order": round(matched / max(len(t), 1), 4),
            "added_words": len(added), "added_sample": added[:15]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--readers", nargs="+", default=["tesseract", "haiku"], choices=["tesseract", *MODELS])
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    client = None
    if any(r in MODELS for r in args.readers):
        client = anthropic.Anthropic(api_key=config.api_key(), max_retries=4)
    results, spend = [], 0.0
    for kind, pages in (("known", KNOWN), ("scanned", SCANNED)):
        for act, lang, page in pages:
            png_bytes, truth = render(act, lang, page)
            stem = f"{kind}-{act}-{lang}-p{page}"
            png = OUT / f"{stem}.png"
            png.write_bytes(png_bytes)
            if kind == "known":
                (OUT / f"{stem}.truth.txt").write_text(truth, encoding="utf-8")
            for reader in args.readers:
                if reader == "tesseract":
                    text, usage = read_tesseract(png, lang), {}
                else:
                    text, usage = read_claude(client, MODELS[reader], png_bytes)
                    spend += usage["cost_usd"]
                (OUT / f"{stem}.{reader}.txt").write_text(text, encoding="utf-8")
                row = {"page": stem, "reader": reader, "words": len(words(text)), **usage}
                if kind == "known":
                    row.update(score(truth, text))
                results.append(row)
                print(json.dumps({k: v for k, v in row.items() if k not in ("at", "endpoint", "job")},
                                 ensure_ascii=False), flush=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"API spend US${spend:.4f}")


if __name__ == "__main__":
    main()
