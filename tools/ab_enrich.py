"""A/B on the enrichment pilot's weak spot, its summaries: does a stricter summary instruction,
alone or with effort "high", fix the defects the blind audit found?

Extracts: the 10 audited pilot records that were not publishable and 10 that were. Arms:
  base         the pilot's own answers (prompt and settings of parlimen/enrich.py)
  strict       the summary instruction below
  strict-high  the same, with output_config effort "high"
Every new record goes through the same checks and the same blind Opus audit as the pilot.

Run: python tools/ab_enrich.py   (resumes from data/bench/enrich-ab/; prints the table)
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parlimen import config, enrich

OUT = config.DATA / "bench" / "enrich-ab"
BASE_AUDITS = enrich.OUT / "audits" / "prompt1"  # the pilot's audits under the first prompt
OLD_SUMMARY = enrich.SYSTEM.split("\n")[3]
STRICT_SUMMARY = (
    "- summary_en: a neutral summary in English, 2 to 6 sentences. Cover every exchange in the "
    "extract, in order: who raised what, and what the other side answered, naming speakers as the "
    "record does. State only what each speaker said: never strengthen, soften or merge their words, "
    "and never give one speaker's words to another. A speaker who only stands up or interjects said "
    "nothing of substance. Name a motion, bill or ruling as exactly as the record does. Never judge "
    "whether anyone was right.")
assert OLD_SUMMARY.startswith("- summary_en:")
STRICT_SYSTEM = enrich.SYSTEM.replace(OLD_SUMMARY, STRICT_SUMMARY)
ARMS = {"strict": {}, "strict-high": {"effort": "high"}}


def picks() -> list[str]:
    audits = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in BASE_AUDITS.glob("*.json")}
    bad = sorted(u for u, a in audits.items() if not a["result"]["publishable"])[:10]
    good = sorted(u for u, a in audits.items() if a["result"]["publishable"])[:10]
    return bad + good


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ids = picks()
    units = {u["id"]: u for u in enrich.all_units() if u["id"] in ids}
    client = enrich._client()

    def run(job):
        uid, arm = job
        path = OUT / arm / f"{uid}.json"
        if path.exists():
            return
        params = enrich.request(units[uid])
        params["system"] = STRICT_SYSTEM
        params["output_config"] = {**params["output_config"], **ARMS[arm]}
        out = enrich.call(client, params, f"ab-enrich-{arm}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    def audit(job):
        uid, arm = job
        path = OUT / "audits" / f"{uid}--{arm}.json"
        if path.exists():
            return
        res = json.loads((OUT / arm / f"{uid}.json").read_text(encoding="utf-8"))
        rec = enrich.finish(units[uid], res["result"])
        shown = {k: rec[k] for k in ("summary_en", "summary_ms", "topics", "entities", "qa_pairs", "commitments")}
        user = ("<extract>\n" + enrich.prompt(units[uid]) + "\n</extract>\n\n<record>\n"
                + json.dumps(shown, ensure_ascii=False, indent=1) + "\n</record>")
        params = {"model": enrich.JUDGE, "max_tokens": enrich.MAX_TOKENS, "system": enrich.JUDGE_SYSTEM,
                  "messages": [{"role": "user", "content": user}],
                  "output_config": {"format": {"type": "json_schema", "schema": enrich.JUDGE_SCHEMA}}}
        out = enrich.call(client, params, "ab-enrich-audit")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    jobs = [(u, a) for u in ids for a in ARMS]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(run, jobs))
        list(pool.map(audit, jobs))

    base = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in BASE_AUDITS.glob("*.json")}
    print("| Arm | Publishable (of 10 failing) | Publishable (of 10 passing) | Major defects | Cost US$ (20 extracts) |")
    print("|---|---|---|---|---|")
    raw = {r["unit"]: r for r in enrich._read(enrich.RAW) if "result" in r and r.get("prompt", 1) == 1}
    rows = {"base": ([base[u] for u in ids], sum(raw[u]["cost_usd"] for u in ids))}
    for arm in ARMS:
        rows[arm] = ([json.loads((OUT / "audits" / f"{u}--{arm}.json").read_text(encoding="utf-8")) for u in ids],
                     sum(json.loads((OUT / arm / f"{u}.json").read_text(encoding="utf-8"))["cost_usd"] for u in ids))
    for arm, (audits, cost) in rows.items():
        ok = [a["result"]["publishable"] for a in audits]
        major = sum(1 for a in audits for d in a["result"]["defects"] if d["severity"] == "major")
        print(f"| {arm} | {sum(ok[:10])} | {sum(ok[10:])} | {major} | {cost:.3f} |")


if __name__ == "__main__":
    main()
