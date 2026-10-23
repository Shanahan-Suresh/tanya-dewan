"""Answer quality on the hand-written questions: does better retrieval give better answers?

For each question in data/eval/hand.json, Haiku 5.5 answers (`parlimen/answer.py`) from the
passages each arm's search finds. A separate Opus 5.5 call grades each answer against the
reference answer, seeing one answer and nothing about its arm, `--repeats` times:

- correct: does the answer give the reference's facts? yes / partly / no
- supported: is every claim backed by the sentences its citations quote? yes / partly / no

The targets: correct 65% or more (yes 1, partly 0.5); every claim backed in 80% or more of
answers (the share graded "supported: yes"). Rows go to data/eval/answers.json, the table to
results/answers-<date>.md.

Run:  python -m parlimen.judge [--arms "BM25 only" "Hybrid + Haiku rerank, pool 20"] [--repeats 2] [--limit N | --ids h021 ...]
      [--answer-effort high]   (rows to answers-effort-high.json, table to answers-<date>-effort-high.md)
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import anthropic

from . import config, enrich, evalset
from .answer import Answer, ask
from .evaluate import ARMS, RESULTS, filters_of, make_reranker
from .search import Searcher

JUDGE_MODEL = enrich.JUDGE
OUT = config.DATA / "eval" / "answers.json"

PROMPT = """You grade an answer from a search tool over Malaysia's Acts of Parliament and the Dewan Rakyat Hansard.

<question>{question}</question>
<reference_answer>{reference}</reference_answer>
<answer_to_grade>{answer}</answer_to_grade>
<cited_sentences>
{quotes}
</cited_sentences>

Grade two things:
1. correct: does the answer give the same facts as the reference answer? "yes" if it does, "partly" if it gets some right or adds a wrong claim, "no" if it misses or contradicts them. An answer that says the documents do not contain the answer is "no". Ignore the closing not-legal-advice line.
2. supported: is every claim in the answer backed by the cited sentences above? "yes", "partly", or "no". The answer may be in Malay or English and the sentences in the other language. A debate sentence starts with its speaker's label from the Hansard record (name, seat or office), which backs who said it; the citation title gives the chamber and sitting date, and the header gives the Act or agenda item and the speakers' parties on that date, which back those details.
Add a one-sentence note on the main problem, or "none"."""

SCHEMA = {"type": "object",
          "properties": {"correct": {"type": "string", "enum": ["yes", "partly", "no"]},
                         "supported": {"type": "string", "enum": ["yes", "partly", "no"]},
                         "note": {"type": "string"}},
          "required": ["correct", "supported", "note"], "additionalProperties": False}
POINTS = {"yes": 1.0, "partly": 0.5, "no": 0.0}


def grade(client, question: str, reference: str, answer: Answer) -> dict:
    quotes = "\n".join(f"[{s.n}] {s.cite}. Header: {s.context}\n    " + " / ".join(s.quotes)
                       for s in answer.sources) or "(none)"
    params = {"model": JUDGE_MODEL, "max_tokens": 4000,
              "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
              "messages": [{"role": "user", "content": PROMPT.format(question=question, reference=reference,
                                                                    answer=answer.text, quotes=quotes)}]}
    try:
        out = enrich.call(client, params, "judge")
    except anthropic.APIError as e:
        return {"correct": "no", "supported": "no", "note": f"judge error: {str(e)[:200]}", "usd": 0.0}
    if "result" not in out:
        return {"correct": "no", "supported": "no", "note": f"judge error: {out['error']}", "usd": out["cost_usd"]}
    return {**out["result"], "usd": out["cost_usd"]}


def run(items: list[dict], arm_names: list[str], repeats: int = 2, workers: int = 4, log=print,
        effort: str | None = None) -> list[dict]:
    from .models import Embedder
    embedder = Embedder(config.EMBEDDER)
    arms = [a for a in ARMS if a.name in arm_names]
    rerankers = {k: make_reranker(k) for k in {a.reranker for a in arms if a.mode == "full"}}
    searchers = {(a.variant, a.reranker): Searcher(variant=a.variant, embedder=embedder,
                                                   reranker=rerankers.get(a.reranker), rerank_size=None)
                 for a in arms}
    found = []
    for item in items:  # on this thread: the index connection belongs to it
        for arm in arms:
            t = time.perf_counter()
            trace = searchers[(arm.variant, arm.reranker)].search(item["question"], filters_of(item), arm.mode,
                                                                  pool=arm.pool)
            found.append((item, arm.name, trace.passages, time.perf_counter() - t))
    client = enrich._client()

    def one(job) -> dict:
        item, arm, passages, search_s = job
        t = time.perf_counter()
        answer = ask(item["question"], passages, item.get("lang", "en"), client, job="judged-answers",
                     **({"effort": effort} if effort else {}))
        seconds = search_s + time.perf_counter() - t
        grades = [grade(client, item["question"], item["answer"], answer) for _ in range(repeats)]
        return {"id": item["id"], "who": item.get("who", ""), "lang": item.get("lang", ""),
                "arm": arm + (f", answer effort {effort}" if effort else ""),
                "answer": answer.text, "dropped": answer.dropped, "sources": [s.cite for s in answer.sources],
                "quotes": [s.quotes for s in answer.sources], "seconds": round(seconds, 1),
                "answer_usd": answer.usd, "grades": grades,
                "correct": sum(POINTS[g["correct"]] for g in grades) / len(grades),
                "supported_all": sum(g["supported"] == "yes" for g in grades) / len(grades),
                "judge_usd": sum(g["usd"] for g in grades)}

    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, row in enumerate(pool.map(one, found), start=1):
            out.append(row)
            log(f"{i}/{len(found)} {row['id']} {row['arm']}: correct {row['correct']:.2f}, "
                f"supported {row['supported_all']:.2f}", flush=True)
    return out


def summary(rows: list[dict]) -> str:
    lines = ["| Retrieval | Questions | Correct | Every claim backed | Seconds per answer | US$ per answer |",
             "|---|---:|---:|---:|---:|---:|"]
    for arm in dict.fromkeys(r["arm"] for r in rows):
        rs = [r for r in rows if r["arm"] == arm]
        n = len(rs)
        lines.append(f"| {arm} | {n} | {sum(r['correct'] for r in rs) / n:.0%} | "
                     f"{sum(r['supported_all'] for r in rs) / n:.0%} | {sum(r['seconds'] for r in rs) / n:.1f} | "
                     f"{sum(r['answer_usd'] for r in rs) / n:.4f} |")
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", nargs="+", default=["BM25 only", "Hybrid + Haiku rerank, pool 20"])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="first N questions only (a pilot)")
    ap.add_argument("--ids", nargs="+", help="these questions only (a pilot)")
    ap.add_argument("--answer-effort", choices=["low", "medium", "high", "xhigh", "max"],
                    help="Haiku's effort for the answers, in place of answer.EFFORT; rows and table get their own files")
    a = ap.parse_args()
    items = evalset.load("hand")
    if a.ids:
        items = [it for it in items if it["id"] in a.ids]
    if a.limit:
        items = items[:a.limit]
    rows = run(items, a.arms, a.repeats, log=print, effort=a.answer_effort)
    suffix = f"-effort-{a.answer_effort}" if a.answer_effort else ""
    OUT.with_name(f"{OUT.stem}{suffix}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    table = summary(rows)
    print(table)
    print(f"answers US${sum(r['answer_usd'] for r in rows):.2f}, judge US${sum(r['judge_usd'] for r in rows):.2f}")
    if not (a.limit or a.ids):
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"answers-{date.today().isoformat()}{suffix}.md").write_text(
            f"# Answer quality, {date.today().isoformat()}\n\n{len(items)} hand-written questions; answers by "
            f"Haiku 5.5 from each arm's passages; graded blind by Opus 5.5, {a.repeats} times each.\n\n{table}\n",
            encoding="utf-8")


if __name__ == "__main__":
    main()
