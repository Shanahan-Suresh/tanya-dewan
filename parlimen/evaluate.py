"""Score retrieval on the test sets, one configuration (arm) at a time.

Metrics per question, averaged over a set: recall@k (share of gold places in the top k chunks),
MRR@10, nDCG@10, as in novel-rag. A law question searches the law and a debate question the
debates (the `kind` filter), as the two search tools of phase 6 do; a filter question also
carries its own filter. The pairs set is scored per language, and the language gap is English
recall@10 less Malay recall@10.

Each arm's run is kept in data/eval/runs/; `results/eval-<date>.md` is rewritten from the latest
run of every arm on the current question sets.

Latency: `latency` runs the chosen setup on N questions with the models on the CPU and torch held
to --threads threads, like the demo's container, and reports the median and 95th percentile.
`--reranker local` times the Qwen3 reranker in place of the Messages API one.

Run:  python -m parlimen.evaluate run [--only "with notes"] [--sets law debate pairs filters] [--device cpu]
      python -m parlimen.evaluate latency [--n 40] [--threads 2] [--pool 20] [--reranker haiku|local]
"""

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from . import config, evalset
from .index import Row, connect, rows
from .search import Filters, Searcher

RESULTS = config.ROOT / "results"
RUNS = config.DATA / "eval" / "runs"


@dataclass(frozen=True)
class Arm:
    name: str
    mode: str          # bm25, dense, hybrid, full
    variant: str = "h"
    pool: int = config.RERANK_POOL  # fused hits the reranker reads
    reranker: str = "local"         # local (Qwen3) or haiku (Messages API, parlimen/llm_rerank.py)


def make_reranker(kind: str):
    if kind == "haiku":
        from .llm_rerank import HaikuReranker
        return HaikuReranker(job="eval-rerank")
    from .models import Reranker
    return Reranker(config.LOCAL_RERANKER)


ARMS = [
    Arm("BM25 only", "bm25"),
    Arm("BM25, with notes", "bm25", "hn"),
    Arm("Vectors only", "dense"),
    Arm("Hybrid (RRF)", "hybrid"),
    Arm("Hybrid + rerank", "full", pool=50),
    Arm("Hybrid + rerank, with notes", "full", "hn", pool=50),
    Arm("Hybrid + rerank, pool 20", "full", pool=20),
    Arm("Hybrid + rerank, pool 10", "full", pool=10),
    Arm("Hybrid + Haiku rerank, pool 20", "full", pool=20, reranker="haiku"),
    Arm("Hybrid + Haiku rerank, pool 50", "full", pool=50, reranker="haiku"),
]


def score(ranked: Sequence[Row], gold: list[dict]) -> dict[str, float]:
    found_at: dict[int, int] = {}
    gains: list[float] = []
    for rank, row in enumerate(ranked, start=1):
        new = [g for g, entry in enumerate(gold) if g not in found_at and evalset.matches(row, entry)]
        for g in new:
            found_at[g] = rank
        gains.append(1.0 if new else 0.0)
    out = {f"recall@{k}": sum(1 for r in found_at.values() if r <= k) / len(gold) for k in (5, 10, 20)}
    first = min(found_at.values(), default=None)
    out["mrr@10"] = 1.0 / first if first and first <= 10 else 0.0
    dcg = sum(g / math.log2(rank + 1) for rank, g in enumerate(gains[:10], start=1))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(gold), 10) + 1))
    out["ndcg@10"] = dcg / ideal if ideal else 0.0
    return out


def filters_of(item: dict) -> Filters:
    return Filters(kind=item["kind"], **item.get("filters", {}))


KEYS = ("recall@5", "recall@10", "recall@20", "mrr@10", "ndcg@10")


def average(per_q: list[dict]) -> dict:
    avg = {k: sum(q[k] for q in per_q) / len(per_q) for k in KEYS} if per_q else {}
    avg["ms"] = sum(q["ms"] for q in per_q) / len(per_q) if per_q else 0
    names = {n for q in per_q for n in q.get("stages", {})}
    avg["stage_ms_median"] = {n: statistics.median(q["stages"][n] for q in per_q if n in q.get("stages", {}))
                              for n in sorted(names)}
    avg["n"] = len(per_q)
    return avg


def evaluate(items: list[dict], searcher: Searcher, mode: str, log=print,
             pool: int = config.RERANK_POOL) -> tuple[dict, list[dict]]:
    per_q = []
    t0 = time.perf_counter()
    for i, item in enumerate(items, start=1):
        t = time.perf_counter()
        trace = searcher.search(item["question"], filters_of(item), mode, xrefs=0, pool=pool)
        ms = (time.perf_counter() - t) * 1000
        ranked = trace.ranked[:20]
        m = score(searcher.fetch(ranked), item["gold"])
        per_q.append({"id": item["id"], "ms": round(ms), "stages": {st.name: round(st.ms) for st in trace.stages},
                      "top": ranked[:10], **m})
        if i % 50 == 0:
            log(f"  {i}/{len(items)} questions, {time.perf_counter() - t0:.0f} s")
    return average(per_q), per_q


def fingerprint(items: Sequence[dict]) -> str:
    blob = json.dumps([[it["id"], it["question"], it["gold"]] for it in items], ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")


def save_run(arm: str, set_name: str, avg: dict, per_q: list[dict], qid: str, device: str = "") -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{_slug(arm)}--{set_name}.json").write_text(json.dumps(
        {"arm": arm, "set": set_name, "questions_id": qid, "device": device, "avg": avg, "questions": per_q},
        indent=1), encoding="utf-8")


def load_runs(current: dict[str, str]) -> dict[str, dict[str, dict]]:
    """Saved runs per arm and set, on today's question sets, in ARMS order."""
    found = {}
    for path in RUNS.glob("*--*.json") if RUNS.exists() else []:  # not the latency-*.json files
        run = json.loads(path.read_text(encoding="utf-8"))
        if current.get(run["set"]) == run.get("questions_id"):
            found[(run["arm"], run["set"])] = run
    return {a.name: {s: found[(a.name, s)] for s in current if (a.name, s) in found}
            for a in ARMS if any((a.name, s) in found for s in current)}


def split_pairs(items: list[dict]) -> dict[str, list[dict]]:
    return {f"pairs-{lang}": [it for it in items if it.get("lang") == lang] for lang in ("en", "ms")}


def table(runs: dict[str, dict[str, dict]]) -> str:
    sets = [s for s in ("law", "debate", "filters") if any(s in by for by in runs.values())]
    head = ("| Arm | " + " | ".join(f"{s} recall@10 | {s} MRR@10" for s in sets)
            + " | pairs EN recall@10 | pairs MS recall@10 | language gap | ms per question |")
    lines = [head, "|---|" + "---:|" * (2 * len(sets) + 4)]
    for arm, by in runs.items():
        cells = []
        for s in sets:
            m = by.get(s, {}).get("avg")
            cells += [f"{m['recall@10']:.3f}", f"{m['mrr@10']:.3f}"] if m else ["", ""]
        en, ms = by.get("pairs-en", {}).get("avg"), by.get("pairs-ms", {}).get("avg")
        cells += [f"{en['recall@10']:.3f}" if en else "", f"{ms['recall@10']:.3f}" if ms else "",
                  f"{(en['recall@10'] - ms['recall@10']) * 100:+.1f} pts" if en and ms else ""]
        speed = max((r["avg"]["ms"] for r in by.values()), default=0)
        cpu = " (CPU)" if any(r.get("device") == "cpu" for r in by.values()) else ""
        lines.append(f"| {arm} | " + " | ".join(cells) + f" | {speed:.0f}{cpu} |")
    return "\n".join(lines)


def write_results(current: dict[str, str], extra: str = "") -> str:
    runs = load_runs(current)
    sizes = ", ".join(f"{s} {r['avg']['n']}" for s, r in next(iter(runs.values()), {}).items())
    text = (f"# Retrieval eval, {date.today().isoformat()}\n\n"
            f"Questions per set: {sizes}. Embedder Qwen3-Embedding-{config.EMBEDDER}, reranker "
            f"Qwen3-Reranker-{config.LOCAL_RERANKER}; candidates {config.CANDIDATES}, rerank pool 50 unless "
            "the arm names one. "
            "Haiku rerank arms send the pool to Claude Haiku 5.5 through the Messages API "
            "(`parlimen/llm_rerank.py`). Language gap: English less Malay recall@10 on the same questions. "
            "Speed: warm models on the GPU, or on the CPU where marked.\n\n"
            + table(runs) + "\n" + extra)
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"eval-{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return text


def cmd_run(a) -> None:
    sets = {}
    for name in a.sets:
        items = evalset.load(name)
        if name == "pairs":
            sets.update(split_pairs(items))
        elif items:
            sets[name] = items
    current = {s: fingerprint(items) for s, items in sets.items()}
    from .models import Embedder
    embedder = Embedder(config.EMBEDDER, device=a.device)
    rerankers: dict[str, object] = {}
    searchers: dict[tuple[str, str], Searcher] = {}
    for arm in ARMS:
        if a.only and not any(o.lower() in arm.name.lower() for o in a.only):
            continue
        key = (arm.variant, arm.reranker)
        if key not in searchers:
            rerankers.setdefault(arm.reranker, make_reranker(arm.reranker))
            searchers[key] = Searcher(variant=arm.variant, embedder=embedder, reranker=rerankers[arm.reranker])
            searchers[key].warm()
        for s, items in sets.items():
            print(f"{arm.name} / {s}: {len(items)} questions", flush=True)
            avg, per_q = evaluate(items, searchers[key], arm.mode, pool=arm.pool)
            save_run(arm.name, s, avg, per_q, current[s], a.device or "")
            print(f"  recall@10 {avg['recall@10']:.3f}  MRR@10 {avg['mrr@10']:.3f}  {avg['ms']:.0f} ms  "
                  f"stages {avg['stage_ms_median']}", flush=True)
    haiku = rerankers.get("haiku")
    if haiku is not None:
        print(f"Haiku rerank: {haiku.calls} calls, {haiku.failures} failed, US${haiku.usd:.3f}", flush=True)
    print(write_results(current))


def cmd_latency(a) -> None:
    import torch
    torch.set_num_threads(a.threads)
    from .models import Embedder, Reranker
    items = [it for name in ("law", "debate") for it in evalset.load(name)][::7][:a.n]
    reranker = make_reranker("haiku") if a.reranker == "haiku" else Reranker(config.LOCAL_RERANKER, device="cpu")
    s = Searcher(embedder=Embedder(config.EMBEDDER, device="cpu"), reranker=reranker)
    s.warm()
    times, stages = [], {}
    for i, it in enumerate(items, start=1):
        t = time.perf_counter()
        trace = s.search(it["question"], filters_of(it), pool=a.pool)
        times.append((time.perf_counter() - t) * 1000)
        for st in trace.stages:
            stages.setdefault(st.name, []).append(st.ms)
        print(f"  {i}/{len(items)}: {times[-1]:.0f} ms", flush=True)
    times.sort()
    p95 = times[min(len(times) - 1, math.ceil(0.95 * len(times)) - 1)]
    line = (f"CPU latency, {a.threads} threads, {len(times)} questions, full pipeline ({config.VARIANT}, "
            f"{a.reranker} rerank pool {a.pool}): median {statistics.median(times):.0f} ms, 95th percentile {p95:.0f} ms; "
            "stage medians " + ", ".join(f"{k} {statistics.median(v):.0f} ms" for k, v in stages.items()))
    print(line)
    RUNS.mkdir(parents=True, exist_ok=True)
    name = f"latency-pool{a.pool}" + ("-haiku" if a.reranker == "haiku" else "")
    (RUNS / f"{name}.json").write_text(json.dumps(
        {"threads": a.threads, "pool": a.pool, "reranker": a.reranker, "ms": times, "line": line}), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--only", nargs="+")
    p.add_argument("--sets", nargs="+", default=["law", "debate", "pairs", "filters"])
    p.add_argument("--device", choices=["cpu", "cuda"], help="embedder device (default: the GPU if free)")
    p = sub.add_parser("latency")
    p.add_argument("--reranker", choices=["local", "haiku"], default="haiku" if config.RERANKER == "haiku" else "local")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--pool", type=int, default=config.RERANK_POOL)
    a = ap.parse_args()
    {"run": cmd_run, "latency": cmd_latency}[a.cmd](a)


if __name__ == "__main__":
    main()
