"""Hand-check aid for downloaded Act PDFs: does each file hold the Act, language and date its row says?

For every cached PDF it prints the row's Act number, language, title and date beside what the
PDF's first pages say: the "Act <n>" / "Akta <n>" line, the LAWS OF MALAYSIA or UNDANG-UNDANG
MALAYSIA heading, the reprint or "as at" date, and the page count.

Run: python tools/check_acts.py [act number ...]
"""

import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parlimen import acts as lom  # noqa: E402

_HEAD = {"BI": "LAWS OF MALAYSIA", "BM": "UNDANG-UNDANG MALAYSIA"}
_NUMBER = re.compile(r"\b(?:Act|Akta)\s+(A?\d+)\b")
_DATE_LINE = re.compile(r"(?i)(as at|sebagaimana pada|reprint|cetakan semula|incorporating|termasuk)[^\n]{0,80}")


def check(act: lom.Act, lang: str) -> str:
    path = act.pdf_path(lang)
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:3])
        pages = len(pdf.pages)
    heading = "yes" if _HEAD[lang] in text.upper().replace("‑", "-") else "NO"
    numbers = sorted(set(_NUMBER.findall(text)))[:4]
    number_ok = "yes" if act.number in numbers else "NO"
    dates = [" ".join(m.group(0).split()) for m in _DATE_LINE.finditer(text)][:2]
    title = act.title_bi if lang == "BI" else act.title_bm
    return (
        f"{act.number:>5} {lang} {pages:>4}p  heading {heading:<3} number {number_ok:<3} {numbers}\n"
        f"      row: {title[:70]} | {act.as_at or act.status}\n"
        f"      pdf: {dates}"
    )


def main() -> None:
    import json

    rows = json.loads(lom.LISTING.read_text(encoding="utf-8"))
    wanted = set(sys.argv[1:])
    for act in (lom.parse_row(c) for c in rows):
        if wanted and act.number not in wanted:
            continue
        for lang in ("BI", "BM"):
            if act.pdf_path(lang).exists():
                print(check(act, lang))


if __name__ == "__main__":
    main()
