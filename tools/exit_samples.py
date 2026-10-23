"""Draw the phase 3 exit samples: 100 oral-question answer joins and 100 commitments, each with
the speeches it rests on, for a reader to check (ROADMAP Goals: 95% and 85%).

Run: python tools/exit_samples.py   ->  data/enrich/exit-samples.json
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parlimen import enrich

OUT = enrich.OUT / "exit-samples.json"


def main() -> None:
    records = [json.loads(line) for line in open(enrich.ENRICHED, encoding="utf-8")]
    rng = random.Random(100)
    qa = [(r["unit"], q) for r in records if "PERTANYAAN" in (r["business"] or "").upper() for q in r["qa_pairs"]]
    cm = [(r["unit"], c) for r in records for c in r["commitments"]]
    picks_qa, picks_cm = rng.sample(qa, 100), rng.sample(cm, 100)
    need = {u for u, _ in picks_qa + picks_cm}
    units = {u["id"]: u for u in enrich.all_units() if u["id"] in need}

    def source(uid: str) -> list[dict]:
        return [{"seq": s["seq"], "label": s["label"], "text": s["text"]} for s in units[uid]["speeches"]]

    out = {
        "qa": [{"n": i + 1, "unit": u, "question_by": q["question_by"]["label"], "question_seq": q["question_by"]["seq"],
                "answer_by": q["answer_by"]["label"], "answer_seq": q["answer_by"]["seq"],
                "question": q["question"], "answer": q["answer"], "speeches": source(u)}
               for i, (u, q) in enumerate(picks_qa)],
        "commitments": [{"n": i + 1, "unit": u, "by": c["speaker"]["label"], "seq": c["speaker"]["seq"],
                         "quote": c["quote"], "promise": c["promise"], "deadline": c["deadline"],
                         "amount": c["amount"], "speeches": source(u)}
                        for i, (u, c) in enumerate(picks_cm)],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(OUT, len(qa), "question-time pairs,", len(cm), "commitments in the corpus")


if __name__ == "__main__":
    main()
