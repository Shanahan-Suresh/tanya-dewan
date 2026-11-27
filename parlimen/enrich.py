"""Enrich the parsed Hansard with Claude Haiku 5.5: summaries in English and Malay, topics,
entities, question-answer pairs and ministers' commitments.

The parser decides who spoke, never the model. Each request holds one extract of a sitting, its
speeches numbered S1, S2, ...; the model cites speeches only by those ids (an enum in the
request's schema), and code maps them back to the parser's speakers. Extracts follow the
record: one agenda item at a time, a question kept with its answers, about UNIT_CHARS of text.

Code checks every record before it is kept: a commitment whose quote is not word for word in
the speech it cites is dropped, and so are figures and entities that the extract does not hold.
The counts of dropped items stay on the record.

The model, prompt and schema are the ones `tools/bench_enrich.py` chose: Haiku 5.5 with its
default adaptive thinking. Every call logs its usage to data/api-usage.jsonl.

Run:  python -m parlimen.enrich pilot          5 sitting days on the Messages API
      python -m parlimen.enrich audit          blind Opus 5.5 audit of a sample of the pilot
      python -m parlimen.enrich submit         every other extract to the Batch API
      python -m parlimen.enrich collect        fetch ended batches, then write data/enriched.jsonl
      python -m parlimen.enrich finish         rewrite data/enriched.jsonl from the raw results
Files: data/enrich/units.jsonl (the extracts), data/enrich/raw.jsonl (each model answer with its
usage), data/enrich/batches.json, data/enrich/audits/, data/enriched.jsonl (checked records).
"""

import argparse
import itertools
import json
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from . import config

SPEECHES = config.DATA / "speeches.jsonl"
OUT = config.DATA / "enrich"
UNITS = OUT / "units.jsonl"
RAW = OUT / "raw.jsonl"
BATCHES = OUT / "batches.json"
ENRICHED = config.DATA / "enriched.jsonl"
CHECKS = OUT / "commit-check.jsonl"  # Sonnet's verdict on each commitment (parlimen/commit_check.py)

MODEL = "claude-haiku-5-5"
JUDGE = "claude-opus-5-5"
# US$ per million tokens, input and output
PRICES = {MODEL: (0.10, 0.50), JUDGE: (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}
BATCH_DISCOUNT = 0.5
MAX_TOKENS = 16000
UNIT_CHARS = 6500   # about 3,400 tokens of Malay text, as benchmarked
PART_CHARS = 12000  # a longer speech (the Budget speech) goes in parts, each its own id
# The prompt's version, stored on every raw answer; answers to an older prompt count as not done.
# 2: the strict summary instruction, chosen by tools/ab_enrich.py.
PROMPT_VERSION = 2
AUDITS = OUT / "audits" / f"prompt{PROMPT_VERSION}"
BATCH_REQUESTS = 5000  # requests per batch: the API takes 256 MB, and an extract is up to ~40 KB

TOPICS = [
    "economy and finance", "tax", "budget and spending", "health", "education", "police and crime",
    "defence", "immigration and refugees", "labour and jobs", "housing", "transport",
    "infrastructure", "environment and climate", "floods and disasters", "agriculture and food",
    "energy and water", "digital and telecoms", "religion", "race and national unity",
    "law and courts", "corruption and governance", "parliament procedure", "foreign affairs",
    "local government", "Sabah and Sarawak", "women and family", "youth and sports",
    "social welfare", "trade and industry", "tourism and culture", "other",
]
ENTITY_TYPES = ["act", "bill", "agency", "company", "place", "person", "organisation", "programme"]

SYSTEM = """You turn an extract of Malaysia's parliamentary record (Hansard) into a structured record for a public search site. The extract is split into speeches. Each speech starts with its id and its speaker as the record gives it, for example "[S3] Datuk Seri ... [Bagan]:". The speaker labels come from the official record; never change them.

Fill every field:
- summary_en: a neutral summary in English, 2 to 6 sentences. Cover every exchange in the extract, in order: who raised what, and what the other side answered, naming speakers as the record does. State only what each speaker said: never strengthen, soften or merge their words, and never give one speaker's words to another. A speaker who only stands up or interjects said nothing of substance. Name a motion, bill or ruling as exactly as the record does. Never judge whether anyone was right.
- summary_ms: the same summary in natural Bahasa Malaysia.
- topics: the topics the extract is about, from the list only.
- entities: Acts, bills, agencies, companies, places, persons, organisations and programmes named in the extract. Write each name as it appears in the text.
- qa_pairs: each question an MP asks and the answer a minister or deputy minister gives, with the speech ids. question and answer are short English paraphrases. figures: every number the answer gives, with value copied exactly as written in the text and its meaning.
- commitments: each promise by a minister or deputy minister to do something in the future, especially with a date or amount. quote must be copied word for word from the cited speech, as one continuous span of the text. promise is a short English paraphrase. deadline and amount are copied from the text, or "" when none is given. A plan stated in general terms with no concrete action is not a commitment.

Use empty lists when the extract has no item of a kind. Never invent a fact that is not in the extract."""

JUDGE_SYSTEM = """You audit a structured record that a program made from an extract of Malaysia's Hansard. The record will be published beside the verbatim text with a label saying it was written by AI. A wrong record could misrepresent what an MP or minister said, so audit strictly.

List every defect you find:
- unsupported_or_wrong: a statement in a summary, question, answer, figure or promise that the extract does not support, or gets wrong (a wrong number, a wrong ministry, an overstated claim).
- wrong_speaker: something attributed to the wrong person or the wrong speech id.
- missed_item: an important point, question-answer pair or concrete commitment in the extract that the record leaves out. Only items a reader of the record would expect.
- false_commitment: a listed commitment that is not a promise of future action, or whose quote does not say what the promise claims.
- malay_quality: summary_ms is unnatural, wrong, or says something different from summary_en.
- other: anything else that would mislead a reader.

severity: major when it would mislead a reader or misrepresent a speaker; minor when it is a small omission or wording issue. Report no defect you are unsure of. Set publishable to true only when the record has no major defect."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "defects": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": [
                    "unsupported_or_wrong", "wrong_speaker", "missed_item", "false_commitment",
                    "malay_quality", "other"]},
                "severity": {"type": "string", "enum": ["major", "minor"]},
                "field": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["category", "severity", "field", "detail"], "additionalProperties": False}},
        "publishable": {"type": "boolean"},
    },
    "required": ["defects", "publishable"],
    "additionalProperties": False,
}

_lock = threading.Lock()


def schema(ids: list[str]) -> dict:
    """The record's schema, with speech ids limited to the extract's own."""
    sid = {"type": "string", "enum": ids}
    strict = lambda props: {"type": "object", "properties": props, "required": list(props),  # noqa: E731
                            "additionalProperties": False}
    return strict({
        "summary_en": {"type": "string"},
        "summary_ms": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string", "enum": TOPICS}},
        "entities": {"type": "array", "items": strict({
            "name": {"type": "string"}, "type": {"type": "string", "enum": ENTITY_TYPES}})},
        "qa_pairs": {"type": "array", "items": strict({
            "question_speech": sid, "answer_speech": sid,
            "question": {"type": "string"}, "answer": {"type": "string"},
            "figures": {"type": "array", "items": strict({
                "value": {"type": "string"}, "meaning": {"type": "string"}})}})},
        "commitments": {"type": "array", "items": strict({
            "speech": sid, "quote": {"type": "string"}, "promise": {"type": "string"},
            "deadline": {"type": "string"}, "amount": {"type": "string"}})},
    })


# ---------- extracts ----------

def _parts(text: str) -> list[str]:
    """A speech's text in pieces of at most PART_CHARS, cut at line ends."""
    if len(text) <= PART_CHARS:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > PART_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    return out + [cur] if cur else out


def sittings() -> "itertools.groupby":
    """(chamber, date) and the sitting's speeches, in file order."""
    rows = (json.loads(line) for line in open(SPEECHES, encoding="utf-8"))
    return itertools.groupby(rows, key=lambda r: (r["chamber"], r["date"]))


def make_units(speeches: list[dict]) -> list[dict]:
    """A sitting's extracts. A question stays with its answers unless the group runs past 1.5
    extracts; an agenda item never shares an extract with the next one."""
    units: list[dict] = []
    cur: list[dict] = []

    def flush() -> None:
        nonlocal cur
        if cur:
            s0 = speeches[0]
            units.append({
                "id": f"{s0['chamber']}-{s0['date']}-{len(units) + 1:03d}",
                "chamber": s0["chamber"], "date": s0["date"], "parliament": s0["parliament"],
                "topic": cur[0]["topic"],
                "speeches": [{**p, "id": f"S{i + 1}"} for i, p in enumerate(cur)],
            })
        cur = []

    size = lambda: sum(len(p["text"]) for p in cur)  # noqa: E731
    groups = itertools.groupby(speeches, key=lambda r: (r["topic"], r["question_no"]))
    for (topic, _), group in groups:
        parts = []
        for sp in group:
            pieces = _parts(sp["text"])
            for k, piece in enumerate(pieces):
                label = sp["label"] + (f" (continued, part {k + 1} of {len(pieces)})" if k else "")
                parts.append({"seq": sp["seq"], "label": label, "text": piece, "topic": topic,
                              "name": sp["name"], "seat": sp["seat"], "role": sp["role"],
                              "senator": sp["senator"]})
        gsize = sum(len(p["text"]) for p in parts)
        if cur and (cur[-1]["topic"] != topic or size() + gsize > UNIT_CHARS * 1.5):
            flush()
        if gsize > UNIT_CHARS * 1.5:  # a long debate: cut at speech boundaries
            for p in parts:
                if cur and size() + len(p["text"]) > UNIT_CHARS * 1.5:
                    flush()
                cur.append(p)
                if size() >= UNIT_CHARS:
                    flush()
        else:
            cur.extend(parts)
            if size() >= UNIT_CHARS:
                flush()
    flush()
    return units


def prompt(unit: dict) -> str:
    head = f"Business: {unit['topic']}\n\n" if unit["topic"] else ""
    return head + "\n\n".join(f"[{s['id']}] {s['label']}: {s['text']}" for s in unit["speeches"])


def request(unit: dict) -> dict:
    return {"model": MODEL, "max_tokens": MAX_TOKENS, "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt(unit)}],
            "output_config": {"format": {"type": "json_schema",
                                         "schema": schema([s["id"] for s in unit["speeches"]])}}}


# ---------- calls ----------

def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.api_key(), max_retries=4)


def _log(job: str, model: str, endpoint: str, usage) -> float:
    pin, pout = PRICES[model]
    cost = (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6
    if endpoint == "batch":
        cost *= BATCH_DISCOUNT
    with _lock, open(config.USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "job": job, "model": model,
                            "endpoint": endpoint, "input_tokens": usage.input_tokens,
                            "output_tokens": usage.output_tokens, "cost_usd": round(cost, 6)}) + "\n")
    return cost


def _answer(msg, cost: float) -> dict:
    out = {"cost_usd": cost, "input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    if msg.stop_reason not in ("end_turn", "stop_sequence"):
        return {**out, "error": f"stop_reason {msg.stop_reason}"}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return {**out, "result": json.loads(text)}
    except json.JSONDecodeError as e:
        return {**out, "error": f"bad JSON: {e}"}


def call(client, params: dict, job: str) -> dict:
    with client.messages.stream(**params) as stream:
        msg = stream.get_final_message()
    return _answer(msg, _log(job, params["model"], "messages", msg.usage))


def _append(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path, encoding="utf-8")] if path.exists() else []


def _done(fresh_from: dict[str, int] | None = None) -> dict[str, dict]:
    """The latest raw answer per extract; an extract whose answer failed counts as not done. An
    extract in `fresh_from` (a revised sitting's) counts only answers from that line of RAW on."""
    fresh_from = fresh_from or {}
    return {r["unit"]: r for i, r in enumerate(_read(RAW))
            if "result" in r and r.get("prompt", 1) == PROMPT_VERSION and i >= fresh_from.get(r["unit"], 0)}


# ---------- checks ----------

def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "-", s)  # words split across lines ("berlama-\nlama")
    return re.sub(r"\s+", " ", s).strip().lower()


def _checks() -> dict[str, dict]:
    """Sonnet's latest verdict per commitment key ("unit|seq|normalised quote")."""
    from .commit_check import CHECK_VERSION  # commit_check imports this module
    return {r["key"]: r for r in _read(CHECKS) if "verdict" in r and r["version"] == CHECK_VERSION}


def finish(unit: dict, res: dict, checks: dict[str, dict] | None = None) -> dict:
    """The checked record: speech ids become the parser's speakers; a commitment quote that is
    not word for word in its speech, and figures and entities not in the extract, are dropped.
    A commitment Sonnet judged not real is dropped too, and its corrected paraphrase replaces
    the model's."""
    by_id = {s["id"]: s for s in unit["speeches"]}
    seq_text = {}
    for s in unit["speeches"]:
        seq_text[s["seq"]] = seq_text.get(s["seq"], "") + " " + _norm(s["text"])
    # Names may come from the speaker labels and bills from the agenda heading, as the model sees them.
    whole = " ".join([*seq_text.values(), *(_norm(s["label"]) for s in unit["speeches"]), _norm(unit["topic"] or "")])

    def who(sid: str) -> dict:
        s = by_id[sid]
        return {"seq": s["seq"], "label": s["label"], "name": s["name"], "seat": s["seat"],
                "role": s["role"], "senator": s["senator"]}

    dropped = {"commitments": 0, "commitments_not_real": 0, "figures": 0, "entities": 0}
    commitments = []
    for c in res["commitments"]:
        quote = _norm(c["quote"])
        seq = by_id[c["speech"]]["seq"]
        if not (quote and quote in seq_text[seq]):
            dropped["commitments"] += 1
            continue
        kept = {"speaker": who(c["speech"]), **{k: c[k] for k in ("quote", "promise", "deadline", "amount")}}
        check = (checks or {}).get(f"{unit['id']}|{seq}|{quote}")
        if check:
            if check["verdict"] not in ("promise", "routine"):
                dropped["commitments_not_real"] += 1
                continue
            kept["promise"] = check["promise_fixed"] or kept["promise"]
            kept["check"] = check["verdict"]
        commitments.append(kept)
    qa = []
    for q in res["qa_pairs"]:
        figures = [f for f in q["figures"] if _norm(f["value"]) in whole]
        dropped["figures"] += len(q["figures"]) - len(figures)
        qa.append({"question_by": who(q["question_speech"]), "answer_by": who(q["answer_speech"]),
                   "question": q["question"], "answer": q["answer"], "figures": figures})
    entities = [e for e in res["entities"] if _norm(e["name"]) in whole]
    dropped["entities"] = len(res["entities"]) - len(entities)
    return {"unit": unit["id"], "chamber": unit["chamber"], "date": unit["date"],
            "parliament": unit["parliament"], "business": unit["topic"],
            "speeches": sorted({s["seq"] for s in unit["speeches"]}),
            "summary_en": res["summary_en"], "summary_ms": res["summary_ms"], "topics": res["topics"],
            "entities": entities, "qa_pairs": qa, "commitments": commitments, "dropped": dropped,
            "model": MODEL, "ai_written": True}


def write_enriched(units: dict[str, dict], path: Path = ENRICHED) -> list[dict]:
    """Rewrite `path` from the raw answers of the given extracts; returns the records."""
    done, checks = _done(), _checks()
    records = [finish(units[uid], done[uid]["result"], checks) for uid in units if uid in done]
    tmp = path.with_suffix(".part")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return records


def summary(records: list[dict], raw: list[dict]) -> str:
    n = len(records)
    commit = sum(len(r["commitments"]) for r in records)
    drop = {k: sum(r["dropped"][k] for r in records)
            for k in ("commitments", "commitments_not_real", "figures", "entities")}
    cost = sum(r["cost_usd"] for r in raw)
    tin, tout = sum(r["input_tokens"] for r in raw), sum(r["output_tokens"] for r in raw)
    return (f"{n} records; {sum(len(r['qa_pairs']) for r in records)} question-answer pairs; "
            f"{commit} commitments kept, {drop['commitments']} dropped (quote not in the speech), "
            f"{drop['commitments_not_real']} dropped (not a real promise); "
            f"figures dropped {drop['figures']}, entities dropped {drop['entities']}; "
            f"{tin:,} input and {tout:,} output tokens; US${cost:.2f}")


# ---------- commands ----------

def all_units() -> list[dict]:
    """Every extract, written to data/enrich/units.jsonl so a batch's answers can be checked
    against the exact extracts that were sent."""
    if UNITS.exists():
        return _read(UNITS)
    units = [u for _, sp in sittings() for u in make_units(list(sp))]
    _append(UNITS, units)
    return units


def pilot_days() -> list[tuple[str, str]]:
    """Two Dewan Rakyat days from each Parliament and one Special Chamber day, fixed by a seed."""
    days: dict[tuple, list] = {}
    for (chamber, date), sp in sittings():
        first = next(sp)
        if chamber == "DR" or first["parliament"] == 15:
            days.setdefault((chamber, first["parliament"] if chamber == "DR" else 0), []).append((chamber, date))
    rng = random.Random(22)
    return sorted(d for key, n in ((("DR", 14), 2), (("DR", 15), 2), (("KK", 0), 1))
                  for d in rng.sample(days[key], n))


def cmd_pilot(args) -> None:
    days = set(pilot_days())
    units = {u["id"]: u for u in all_units() if (u["chamber"], u["date"]) in days}
    print("pilot days:", ", ".join(f"{c} {d}" for c, d in sorted(days)), f"- {len(units)} extracts", flush=True)
    done = _done()
    todo = [u for uid, u in units.items() if uid not in done]
    client = _client()

    def one(u: dict) -> None:
        try:
            out = call(client, request(u), "enrich-pilot")
        except anthropic.APIError as e:
            out = {"error": str(e)[:300], "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        _append(RAW, [{"unit": u["id"], "endpoint": "messages", "prompt": PROMPT_VERSION, **out}])
        print(f"{u['id']}: {'ok' if 'result' in out else out['error']}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, todo))
    records = write_enriched(units, OUT / "pilot.jsonl")
    raw = [r for r in _read(RAW) if r["unit"] in units and r.get("prompt", 1) == PROMPT_VERSION]
    print(summary(records, raw))
    chars = sum(len(s["text"]) for u in units.values() for s in u["speeches"])
    corpus = sum(len(s["text"]) for u in all_units() for s in u["speeches"])
    cost = sum(r["cost_usd"] for r in raw)
    print(f"failed {len(units) - len(records)}; full corpus on the Batch API at this rate: "
          f"about US${cost / chars * corpus * BATCH_DISCOUNT:.0f}")


def cmd_audit(args) -> None:
    units = {u["id"]: u for u in all_units()}
    records = _read(OUT / "pilot.jsonl")
    sample = random.Random(args.seed).sample(records, min(args.sample, len(records)))
    client = _client()
    AUDITS.mkdir(parents=True, exist_ok=True)

    def one(rec: dict) -> dict:
        path = AUDITS / f"{rec['unit']}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        shown = {k: rec[k] for k in ("summary_en", "summary_ms", "topics", "entities", "qa_pairs", "commitments")}
        user = ("<extract>\n" + prompt(units[rec["unit"]]) + "\n</extract>\n\n<record>\n"
                + json.dumps(shown, ensure_ascii=False, indent=1) + "\n</record>")
        params = {"model": JUDGE, "max_tokens": MAX_TOKENS, "system": JUDGE_SYSTEM,
                  "messages": [{"role": "user", "content": user}],
                  "output_config": {"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}}}
        out = call(client, params, "enrich-audit")
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        audits = list(pool.map(one, sample))
    ok = [a["result"] for a in audits if "result" in a]
    major = [d for a in ok for d in a["defects"] if d["severity"] == "major"]
    kinds: dict[str, int] = {}
    for d in major:
        kinds[d["category"]] = kinds.get(d["category"], 0) + 1
    print(f"{sum(a['publishable'] for a in ok)} of {len(ok)} publishable; {len(major)} major defects "
          f"{kinds}; {sum(1 for a in ok for d in a['defects'] if d['severity'] == 'minor')} minor; "
          f"audit cost US${sum(a['cost_usd'] for a in audits):.2f}")


def cmd_submit(args) -> None:
    done = _done()
    # In flight: batches not yet collected. A collected extract with no ok answer goes again.
    sent = {uid for b in _read_batches() if not b["collected"] for uid in b["units"]}
    todo = [u for u in all_units() if u["id"] not in done and u["id"] not in sent]
    if args.limit:
        todo = todo[:args.limit]
    client = _client()
    batches = _read_batches()
    for k in range(0, len(todo), BATCH_REQUESTS):
        chunk = todo[k:k + BATCH_REQUESTS]
        b = client.messages.batches.create(requests=[{"custom_id": u["id"], "params": request(u)} for u in chunk])
        batches.append({"id": b.id, "units": [u["id"] for u in chunk], "prompt": PROMPT_VERSION, "collected": False})
        _write_batches(batches)
        print(f"batch {b.id}: {len(chunk)} extracts", flush=True)


def _read_batches() -> list[dict]:
    return json.loads(BATCHES.read_text(encoding="utf-8")) if BATCHES.exists() else []


def _write_batches(batches: list[dict]) -> None:
    BATCHES.parent.mkdir(parents=True, exist_ok=True)
    tmp = BATCHES.with_suffix(".part")
    tmp.write_text(json.dumps(batches, indent=1), encoding="utf-8")
    tmp.replace(BATCHES)


def cmd_collect(args) -> None:
    client = _client()
    batches = _read_batches()
    for b in batches:
        if b["collected"]:
            continue
        status = client.messages.batches.retrieve(b["id"])
        if status.processing_status != "ended":
            c = status.request_counts
            print(f"batch {b['id']}: {status.processing_status}, {c.processing} processing, "
                  f"{c.succeeded} succeeded, {c.errored} errored", flush=True)
            continue
        rows = []
        for item in client.messages.batches.results(b["id"]):
            if item.result.type == "succeeded":
                msg = item.result.message
                out = _answer(msg, _log("enrich-batch", MODEL, "batch", msg.usage))
            else:
                out = {"error": f"batch {item.result.type}", "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
            rows.append({"unit": item.custom_id, "endpoint": "batch", "prompt": b.get("prompt", 1), **out})
        _append(RAW, rows)
        b["collected"] = True
        _write_batches(batches)
        print(f"batch {b['id']}: {sum('result' in r for r in rows)} of {len(rows)} ok", flush=True)
    cmd_finish(args)


def cmd_finish(args) -> None:
    units = {u["id"]: u for u in all_units()}
    records = write_enriched(units)
    raw = list(_done().values())
    print(summary(records, raw))
    print(f"{len(units) - len(records)} of {len(units)} extracts have no record yet")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("audit")
    p.add_argument("--sample", type=int, default=40)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("submit")
    p.add_argument("--limit", type=int, default=0, help="send only the first N extracts")
    sub.add_parser("collect")
    sub.add_parser("finish")
    args = ap.parse_args()
    {"pilot": cmd_pilot, "audit": cmd_audit, "submit": cmd_submit, "collect": cmd_collect,
     "finish": cmd_finish}[args.cmd](args)


if __name__ == "__main__":
    main()
