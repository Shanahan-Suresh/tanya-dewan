"""Survey every cached Act PDF before the section parser runs.

For each file: pages, characters per page (an image-only file has almost none), the page of the
arrangement of sections, the page where the body starts (the long title or the enacting words),
schedules, the "no Malay text" cover, a repeal notice, and the PDF's producer and creation year.
Text comes from pdfium: pdfplumber drops the digits 1 and 2 in the 2006 reprints' font.
Writes data/acts-survey.csv and prints counts.

Run: python tools/survey_acts.py
"""

import collections
import csv
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parlimen import config  # noqa: E402

ARRANGEMENT = re.compile(r"ARRANGEMENT OF (SECTIONS|ARTICLES|RULES|CLAUSES)|SUSUNAN (SEKSYEN|PERKARA)", re.I)
BODY = re.compile(r"^(An Act|An Ordinance|An Enactment|Suatu Akta|Suatu Ordinan|Suatu Enakmen|"
                  r"(BE IT )?ENACTED|DIPERBUAT|MAKA INILAH|WHEREAS|BAHAWASANYA)\b", re.I)
MARKERS = {
    "schedule": re.compile(r"^(\w+ )?(SCHEDULE|JADUAL)( \w+)?$", re.M),
    "no_malay": re.compile(r"Tiada teks bahasa kebangsaan", re.I),
    "repeal_notice": re.compile(r"\b(repealed|dimansuhkan)\b", re.I),
}


def survey(path: Path) -> dict:
    row = {"act": path.parent.name, "file": path.name, "lang": path.name[:2]}
    doc = pdfium.PdfDocument(str(path))
    try:
        pages = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
        meta = doc.get_metadata_dict()
    finally:
        doc.close()
    lines = [(i + 1, ln.strip()) for i, t in enumerate(pages) for ln in t.splitlines()]
    arr = next((k for k, (_, ln) in enumerate(lines) if ARRANGEMENT.search(ln)), None)
    body = next((k for k in range(arr or 0, len(lines)) if BODY.match(lines[k][1])), None)
    row["pages"] = len(pages)
    row["chars_per_page"] = round(sum(len(t) for t in pages) / max(len(pages), 1))
    row["arrangement_page"] = lines[arr][0] if arr is not None else ""
    row["body_page"] = lines[body][0] if body is not None else ""
    joined = "\n".join(pages)
    row["schedule"] = bool(MARKERS["schedule"].search(joined))
    row["no_malay"] = bool(MARKERS["no_malay"].search("\n".join(pages[:2])))
    row["repeal_notice"] = len(pages) <= 3 and bool(MARKERS["repeal_notice"].search(pages[0] if pages else ""))
    row["producer"] = str(meta.get("Producer", ""))[:40]
    m = re.search(r"(\d{4})", str(meta.get("CreationDate", "")))
    row["created"] = m.group(1) if m else ""
    return row


def main() -> None:
    files = sorted(config.ACTS.glob("*/*.pdf"))
    rows = []
    for i, f in enumerate(files):
        try:
            rows.append(survey(f))
        except Exception as e:  # a broken file is a finding, not a crash
            rows.append({"act": f.parent.name, "file": f.name, "lang": f.name[:2], "error": str(e)[:120]})
        if i % 200 == 0:
            print(f"{i} of {len(files)}", flush=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    out = config.DATA / "acts-survey.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} files surveyed, written to {out}")
    print("errors:", sum(1 for r in rows if "error" in r))
    ok = [r for r in rows if "error" not in r]
    image = [r for r in ok if r["chars_per_page"] < 200 and not r["repeal_notice"]]
    print("image only (under 200 characters a page, not a repeal notice):", len(image))
    for lang in ("BI", "BM"):
        sub = [r for r in ok if r["lang"] == lang]
        text = [r for r in sub if r["chars_per_page"] >= 200 and not r["repeal_notice"] and not r["no_malay"]]
        print(f"\n{lang}: {len(sub)} files, {len(text)} with text to parse")
        print("  no arrangement:", sum(1 for r in text if not r["arrangement_page"]))
        print("  no body start:", sum(1 for r in text if not r["body_page"]))
        for name in MARKERS:
            print(f"  {name}: {sum(1 for r in sub if r[name])}")
        print("  created:", sorted(collections.Counter(r["created"][:3] + "0s" for r in sub).items()))
        print("  producers:", collections.Counter(r["producer"] for r in sub).most_common(5))


if __name__ == "__main__":
    main()
