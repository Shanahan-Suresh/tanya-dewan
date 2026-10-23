"""Check parsed Act sections word for word against a second text extractor.

Takes N random text-layer sections from data/act_sections.jsonl (or the sections of the Acts
named), reads the same pages with poppler's pdftotext, and reports how many of the section's
words appear in order in that text. A section below the bar is printed with its first difference, for a person
to look at against the PDF page.

Run: python tools/check_act_text.py [--sample 50] [--seed 1] [--acts 265 711 ...]
"""

import argparse
import json
import random
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parlimen import config  # noqa: E402
from parlimen.act_text import SECTIONS_OUT  # noqa: E402

BAR = 0.98  # share of the section's words that pdftotext shows in the same order


def words(s: str) -> list[str]:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.findall(r"[0-9A-Za-zÀ-ÿ]+", s.lower())


def pdftotext(path: Path, first: int, last: int) -> str:
    out = subprocess.run(["pdftotext", "-f", str(first), "-l", str(last), "-raw", "-enc", "UTF-8", str(path), "-"],
                         capture_output=True, timeout=60)
    return out.stdout.decode("utf-8", "replace")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--acts", nargs="+", metavar="NUMBER")
    args = ap.parse_args()

    with open(SECTIONS_OUT, encoding="utf-8") as f:
        # A scanned file has no text layer for poppler to read; parlimen.act_ocr checks its sections.
        sections = [s for line in f if (s := json.loads(line)).get("source", "text") == "text"]
    if args.acts:
        sections = [s for s in sections if s["act"] in args.acts]
    else:
        sections = random.Random(args.seed).sample(sections, args.sample)

    low = 0
    for s in sections:
        folder = config.ACTS / re.sub(r"[^A-Za-z0-9]+", "-", s["act"]).strip("-")
        path = folder / f"{s['lang']}-{s['as_at'] or 'repealed'}.pdf"
        mine = words(s["text"])
        theirs = words(pdftotext(path, s["page_start"], s["page_end"]))
        sm = SequenceMatcher(None, mine, theirs, autojunk=False)
        share = sum(b.size for b in sm.get_matching_blocks()) / max(len(mine), 1)
        flag = "LOW" if share < BAR else "ok "
        low += share < BAR
        print(f"{flag} {share:.3f} Act {s['act']:>5} {s['lang']} s.{s['number']:<6} p{s['page_start']}-{s['page_end']} "
              f"{len(mine)} words")
        if share < BAR:
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag != "equal" and i2 > i1:
                    print(f"      parsed: {' '.join(mine[max(0, i1 - 3):i2 + 3])}")
                    print(f"      poppler: {' '.join(theirs[max(0, j1 - 3):j2 + 3])}")
                    break
    print(f"\n{len(sections) - low} of {len(sections)} sections at or above {BAR}")


if __name__ == "__main__":
    main()
