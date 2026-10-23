"""Build the owner's review page for the enrichment pilot: 20 AI records beside the speeches they
came from, each marked right or wrong, saved to the page's database.

The sample favours records with question-answer pairs or commitments, since those are the
fields a reader acts on: 14 such records and 6 others, fixed by a seed.

Run: python tools/pilot_review.py   ->  docs/enrich-pilot-review.html (publish with the Artifact tool)
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parlimen import config, enrich

OUT = config.ROOT / "docs" / "enrich-pilot-review.html"
CHAMBER = {"DR": "Dewan Rakyat", "KK": "Special Chamber"}


def sample() -> list[dict]:
    records = [json.loads(line) for line in open(enrich.OUT / "pilot.jsonl", encoding="utf-8")]
    units = {u["id"]: u for u in enrich.all_units() if u["id"] in {r["unit"] for r in records}}
    rng = random.Random(5)
    rich = [r for r in records if r["qa_pairs"] or r["commitments"]]
    plain = [r for r in records if not (r["qa_pairs"] or r["commitments"])]
    picks = rng.sample(rich, min(14, len(rich)))
    picks += rng.sample(plain, min(20 - len(picks), len(plain)))
    picks.sort(key=lambda r: r["unit"])
    out = []
    for r in picks:
        u = units[r["unit"]]
        out.append({
            "id": r["unit"], "chamber": CHAMBER[r["chamber"]], "date": r["date"], "business": r["business"],
            "summary_en": r["summary_en"], "summary_ms": r["summary_ms"], "topics": r["topics"],
            "qa": [{"q_by": q["question_by"]["label"], "a_by": q["answer_by"]["label"], "q": q["question"],
                    "a": q["answer"], "figures": q["figures"]} for q in r["qa_pairs"]],
            "commitments": [{"by": c["speaker"]["label"], "quote": c["quote"], "promise": c["promise"],
                             "deadline": c["deadline"], "amount": c["amount"]} for c in r["commitments"]],
            "speeches": [{"label": s["label"], "text": s["text"]} for s in u["speeches"]],
        })
    return out


def main() -> None:
    page = (Path(__file__).with_name("pilot_review_template.html")).read_text(encoding="utf-8")
    data = json.dumps(sample(), ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(page.replace("__RECORDS__", data), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
