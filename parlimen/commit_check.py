"""Check every kept commitment with Claude Sonnet 5.5: is it a real promise of future action by
the government, or past action, existing policy, a vague aim, or words from someone who does
not speak for the government?

The enrichment keeps a commitment only when its quote is word for word in the speech; this check
reads the quote in its context. The phase 3 exit sample found 92 of 100 commitments real, and the
failures were past action or existing policy given as a promise (5) and vague aims (3).

One request per extract that has commitments. Each commitment goes as C1, C2, ... with its
speaker label and a window of its speech around the quote, so the request stays small. The
verdicts land in data/enrich/commit-check.jsonl, keyed by extract, speech and quote;
`enrich.finish` drops the commitments judged not real and applies corrected paraphrases, so
`enrich finish` keeps the check.

Run:  python -m parlimen.commit_check pilot      the exit sample's extracts on the Messages API,
                                                 scored against data/enrich/exit-review.md
      python -m parlimen.commit_check submit     every other extract to the Batch API
      python -m parlimen.commit_check collect    fetch ended batches, then rewrite data/enriched.jsonl
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import anthropic

from . import enrich

MODEL = "claude-sonnet-5-5"
# Sonnet 5.5 cannot turn thinking off; "between_tools" keeps it from thinking before a plain answer.
THINKING = {"type": "between_tools"}
MAX_TOKENS = 8000
WINDOW = 1200  # characters of the speech kept on each side of the quote
CHECKS = enrich.CHECKS
BATCHES = enrich.OUT / "commit-check-batches.json"
EXIT_SAMPLES = enrich.OUT / "exit-samples.json"
EXIT_REVIEW = enrich.OUT / "exit-review.md"
# The prompt's version, stored on every row; rows of an older version count as not checked.
# 2: ongoing work with a future step is a promise; paraphrases are corrected only when wrong.
# 3: not_government only on evidence; past and future judged against the sitting date.
CHECK_VERSION = 3
BATCH_REQUESTS = 5000

VERDICTS = ["promise", "routine", "past_or_existing", "vague", "not_government"]
KEEP = {"promise", "routine"}

SYSTEM = """You check items that a program listed as ministers' commitments in Malaysia's parliamentary record (Hansard). A public site will show them in a list of government promises, each beside its verbatim quote. An item that is not a real promise would misrepresent the speaker, so check strictly.

Each item has an id (C1, C2, ...), the speaker label from the official record, the quote, the program's English paraphrase of the promise, and a window of the speech around the quote, with the quote marked <<like this>>.

Give each item one verdict:
- promise: the speaker, for the government, says the government or a ministry will do something specific in the future. These all count: a promise with a condition; a dated target or expected completion for a named project or programme; the next step, rollout, completion or decision of work that is under way ("will be gazetted", "will be implemented from year end", "once the study ends we will take it to Cabinet"); a stated commitment to keep doing a concrete thing.
- routine: a real undertaking with no public substance: to reply in writing, look into a case, discuss with an MP, consider a suggestion, or pass a matter to another ministry.
- past_or_existing: the quote itself only reports what is already done or in place: an action completed, a policy, rule or allocation that already exists, or a description of how a body works now. If the quote also names a future step, it is a promise.
- vague: an aim, hope or assurance with no concrete action ("we will ensure", "we will settle it soon", a general target with nothing the government will do).
- not_government: the speaker does not speak for the government, for example a backbench or opposition MP, or the Speaker. Use it only when the label or the speech shows this: the record often labels a minister or deputy minister by name alone, and one who answers a question speaks for the government.
Judge past and future against the sitting date at the top: a step set for a date after the sitting is future, even when the decision to take it is already made.
When an item is between promise and another verdict, choose promise.

promise_fixed: "" in almost every case. Write a corrected short English paraphrase only when the paraphrase is wrong: it states an amount, date, body or action that the quote and its context contradict or do not support, or it claims more than the quote says. A paraphrase that is short or leaves out detail is not wrong.
reason: one short sentence. Judge from the quote and its context only."""


def schema(ids: list[str]) -> dict:
    strict = lambda props: {"type": "object", "properties": props, "required": list(props),  # noqa: E731
                            "additionalProperties": False}
    return strict({"checks": {"type": "array", "items": strict({
        "id": {"type": "string", "enum": ids},
        "verdict": {"type": "string", "enum": VERDICTS},
        "promise_fixed": {"type": "string"},
        "reason": {"type": "string"},
    })}})


def key(unit: str, seq: int, quote: str) -> str:
    return f"{unit}|{seq}|{enrich._norm(quote)}"


# ---------- requests ----------

def _norm_map(text: str) -> tuple[str, list[int]]:
    """`enrich._norm(text)` with, for each of its characters, the index of the source character."""
    out, idx = [], []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace() or (ch == "-" and re.match(r"-\s*\n", text[i:])):
            j = i + 1 if ch == "-" else i
            while j < len(text) and text[j].isspace():
                j += 1
            if ch == "-":
                out.append("-"); idx.append(i)
            elif out and out[-1] != " ":
                out.append(" "); idx.append(i)
            i = j
            continue
        out.append({"’": "'", "‘": "'", "“": '"', "”": '"'}.get(ch, ch).lower())
        idx.append(i)
        i += 1
    while out and out[-1] == " ":
        out.pop(); idx.pop()
    if out and out[0] == " ":
        out.pop(0); idx.pop(0)
    return "".join(out), idx


def window(text: str, quote: str) -> str:
    """The speech around the quote, the quote marked <<...>>; the whole speech if it is short."""
    norm, idx = _norm_map(text)
    q = enrich._norm(quote)
    at = norm.find(q)
    if at < 0:  # finish() kept it, so the quote is there; only an edge case of the mapping lands here
        return text[:2 * WINDOW]
    start, end = idx[at], idx[at + len(q) - 1] + 1
    lo, hi = max(0, start - WINDOW), min(len(text), end + WINDOW)
    return (("..." if lo else "") + text[lo:start] + "<<" + text[start:end] + ">>" + text[end:hi]
            + ("..." if hi < len(text) else ""))


def items(unit: dict, record: dict) -> list[dict]:
    """The record's commitments with their speech window and key, in record order."""
    by_seq: dict[int, dict] = {}
    for s in unit["speeches"]:
        sp = by_seq.setdefault(s["seq"], {"label": s["label"], "text": ""})
        sp["text"] += ("\n" if sp["text"] else "") + s["text"]
    out = []
    for i, c in enumerate(record["commitments"]):
        seq = c["speaker"]["seq"]
        out.append({"id": f"C{i + 1}", "key": key(unit["id"], seq, c["quote"]), "label": by_seq[seq]["label"],
                    "quote": c["quote"], "promise": c["promise"], "window": window(by_seq[seq]["text"], c["quote"])})
    return out


def prompt(unit: dict, its: list[dict]) -> str:
    head = f"Sitting: {unit['chamber']} {unit['date']}. Business: {unit['topic'] or '-'}\n\n"
    return head + "\n\n".join(
        f"[{it['id']}] Speaker: {it['label']}\nQuote: {it['quote']}\nParaphrase: {it['promise']}\n"
        f"Speech:\n{it['window']}" for it in its)


def request(unit: dict, its: list[dict]) -> dict:
    return {"model": MODEL, "max_tokens": MAX_TOKENS, "system": SYSTEM, "thinking": THINKING,
            "messages": [{"role": "user", "content": prompt(unit, its)}],
            "output_config": {"format": {"type": "json_schema", "schema": schema([it["id"] for it in its])}}}


def rows(unit_id: str, its: list[dict], out: dict, endpoint: str) -> list[dict]:
    """One check row per commitment; a failed request gives one error row for the extract."""
    meta = {"unit": unit_id, "endpoint": endpoint, "version": CHECK_VERSION, "model": MODEL}
    if "result" not in out:
        return [{**meta, "error": out["error"], "cost_usd": out["cost_usd"]}]
    got = {c["id"]: c for c in out["result"]["checks"]}
    share = out["cost_usd"] / len(its)
    return [{**meta, "key": it["key"], "cost_usd": share,
             **({k: got[it["id"]][k] for k in ("verdict", "promise_fixed", "reason")} if it["id"] in got
                else {"error": "no verdict for this item"})} for it in its]


# ---------- data ----------

def _todo(only: set[str] | None = None) -> list[tuple[dict, list[dict]]]:
    """(extract, its commitments) for every record with a commitment not yet checked. Reads the
    extracts file line by line, keeping only the ones needed."""
    done = {r["key"] for r in enrich._read(CHECKS) if "verdict" in r and r["version"] == CHECK_VERSION}
    records = {}
    for line in open(enrich.ENRICHED, encoding="utf-8"):
        r = json.loads(line)
        if r["commitments"] and (only is None or r["unit"] in only):
            records[r["unit"]] = r
    out = []
    for line in open(enrich.UNITS, encoding="utf-8"):
        if not line.startswith('{"id": "') or line[8:line.index('"', 8)] not in records:
            continue
        u = json.loads(line)
        its = items(u, records[u["id"]])
        if any(it["key"] not in done for it in its):
            out.append((u, its))
    return out


def tally(check_rows: list[dict]) -> str:
    ok = [r for r in check_rows if "verdict" in r]
    counts = {v: sum(r["verdict"] == v for r in ok) for v in VERDICTS}
    fixed = sum(bool(r["promise_fixed"]) and r["verdict"] in KEEP for r in ok)
    return (f"{len(ok)} checked, {len(check_rows) - len(ok)} errors; {counts}; "
            f"{fixed} paraphrases corrected; US${sum(r['cost_usd'] for r in check_rows):.2f}")


# ---------- commands ----------

def _exit_truth() -> dict[int, bool]:
    """Exit review: commitment number -> real (True) or not (False)."""
    truth = {}
    for m in re.finditer(r"^C (\d+): (real|not real)", EXIT_REVIEW.read_text(encoding="utf-8"), re.M):
        truth[int(m.group(1))] = m.group(2) == "real"
    return truth


def cmd_pilot(args) -> None:
    samples = json.loads(EXIT_SAMPLES.read_text(encoding="utf-8"))["commitments"]
    todo = _todo({s["unit"] for s in samples})
    client = enrich._client()
    print(f"pilot: {len(todo)} extracts to check", flush=True)

    def one(job: tuple[dict, list[dict]]) -> None:
        u, its = job
        try:
            out = enrich.call(client, request(u, its), "commit-check-pilot")
        except anthropic.APIError as e:
            out = {"error": str(e)[:300], "cost_usd": 0.0}
        enrich._append(CHECKS, rows(u["id"], its, out, "messages"))
        print(f"{u['id']}: {'ok' if 'result' in out else out['error']}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, todo))

    checks = {r["key"]: r for r in enrich._read(CHECKS) if "verdict" in r and r["version"] == CHECK_VERSION}
    truth = _exit_truth()
    agree, disagree = 0, []
    for s in samples:
        c = checks.get(key(s["unit"], s["seq"], s["quote"]))
        if c is None:
            disagree.append(f"C {s['n']}: no verdict")
            continue
        if (c["verdict"] in KEEP) == truth[s["n"]]:
            agree += 1
        else:
            disagree.append(f"C {s['n']}: review says {'real' if truth[s['n']] else 'not real'}, "
                            f"check says {c['verdict']}: {c['reason']}")
    pilot_rows = [r for r in enrich._read(CHECKS) if r["endpoint"] == "messages" and r["version"] == CHECK_VERSION]
    print(f"agreement with the exit review: {agree} of {len(samples)}")
    print("\n".join(disagree))
    print("pilot:", tally(pilot_rows))
    n_all = sum(1 for line in open(enrich.ENRICHED, encoding="utf-8") if '"commitments": [{' in line)
    units = len({r["unit"] for r in pilot_rows})
    cost = sum(r["cost_usd"] for r in pilot_rows)
    print(f"all {n_all} extracts on the Batch API at this rate: about "
          f"US${cost / units * n_all * enrich.BATCH_DISCOUNT:.0f}")


def cmd_submit(args) -> None:
    sent = {uid for b in _read_batches() if not b["collected"] for uid in b["units"]}
    todo = [(u, its) for u, its in _todo() if u["id"] not in sent]
    if args.limit:
        todo = todo[:args.limit]
    client = enrich._client()
    batches = _read_batches()
    for k in range(0, len(todo), BATCH_REQUESTS):
        chunk = todo[k:k + BATCH_REQUESTS]
        b = client.messages.batches.create(requests=[{"custom_id": u["id"], "params": request(u, its)} for u, its in chunk])
        batches.append({"id": b.id, "units": [u["id"] for u, _ in chunk], "collected": False})
        _write_batches(batches)
        print(f"batch {b.id}: {len(chunk)} extracts", flush=True)


def _read_batches() -> list[dict]:
    return json.loads(BATCHES.read_text(encoding="utf-8")) if BATCHES.exists() else []


def _write_batches(batches: list[dict]) -> None:
    tmp = BATCHES.with_suffix(".part")
    tmp.write_text(json.dumps(batches, indent=1), encoding="utf-8")
    tmp.replace(BATCHES)


def cmd_collect(args) -> None:
    client = enrich._client()
    batches = _read_batches()
    pending = [b for b in batches if not b["collected"]]
    if not pending:
        print("no batch waiting")
    need = {uid for b in pending for uid in b["units"]}
    its_by_unit = {u["id"]: its for u, its in _todo(need)} if need else {}
    for b in pending:
        status = client.messages.batches.retrieve(b["id"])
        if status.processing_status != "ended":
            c = status.request_counts
            print(f"batch {b['id']}: {status.processing_status}, {c.processing} processing, "
                  f"{c.succeeded} succeeded, {c.errored} errored", flush=True)
            continue
        out_rows = []
        for item in client.messages.batches.results(b["id"]):
            its = its_by_unit.get(item.custom_id)
            if its is None:  # checked meanwhile
                continue
            if item.result.type == "succeeded":
                msg = item.result.message
                out = enrich._answer(msg, enrich._log("commit-check-batch", MODEL, "batch", msg.usage))
            else:
                out = {"error": f"batch {item.result.type}", "cost_usd": 0.0}
            out_rows += rows(item.custom_id, its, out, "batch")
        enrich._append(CHECKS, out_rows)
        b["collected"] = True
        _write_batches(batches)
        print(f"batch {b['id']}: {tally(out_rows)}", flush=True)
    enrich.cmd_finish(args)
    all_rows = [r for r in enrich._read(CHECKS) if r["version"] == CHECK_VERSION]
    print("all checks:", tally(all_rows))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("submit")
    p.add_argument("--limit", type=int, default=0, help="send only the first N extracts")
    sub.add_parser("collect")
    args = ap.parse_args()
    {"pilot": cmd_pilot, "submit": cmd_submit, "collect": cmd_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
