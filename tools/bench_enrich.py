"""Quick benchmark: is Haiku 5.5 good enough for the enrichment, or does it need Sonnet 5.5?

Each arm enriches the same Hansard extracts (summaries in English and Malay, topics, entities,
question-answer pairs, ministers' commitments). Two checks score the results:

1. Code checks: every commitment quote must appear word for word in the speech it cites, and
   every figure and entity name must appear in the source.
2. A blind audit: Opus 5.5 reads each result alone, with no model name, and lists its defects
   (unsupported claims, wrong speaker, missed items, poor Malay, false commitments).

Extracts are cut from the sample texts in data/raw/text/ by a rough speaker splitter that lives
only here; the phase 2 parser replaces it. The model never names a speaker: it cites speech ids.

Run: python tools/bench_enrich.py run      (enrich, then audit; resumes from saved results)
     python tools/bench_enrich.py report   (tables from the saved results)
Results: data/bench/enrich/. Every call logs its usage to data/api-usage.jsonl.
"""

import json
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from parlimen import config

KEY_FILE = Path.home() / ".claude" / "anthropic-api-key.txt"
OUT = config.DATA / "bench" / "enrich"
TEXTS = config.RAW / "text"

# Arms run as production would: no thinking, so output tokens stay at the costed level.
ARMS = {
    "haiku": {"model": "claude-haiku-5-5", "thinking": {"type": "disabled"}},
    "haiku-think": {"model": "claude-haiku-5-5"},  # adaptive thinking at the default effort
    "sonnet": {"model": "claude-sonnet-5-5", "thinking": {"type": "between_tools"}},
}
JUDGE = "claude-opus-5-5"
PRICES = {  # US$ per million tokens, input and output, standard (not batch) rates
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
UNIT_CHARS = 6500  # about 3,400 tokens of Malay text per extract
UNITS_PER_TEXT = {"DR": 4, "KK": 1}

TOPICS = [
    "economy and finance", "tax", "budget and spending", "health", "education", "police and crime",
    "defence", "immigration and refugees", "labour and jobs", "housing", "transport",
    "infrastructure", "environment and climate", "floods and disasters", "agriculture and food",
    "energy and water", "digital and telecoms", "religion", "race and national unity",
    "law and courts", "corruption and governance", "parliament procedure", "foreign affairs",
    "local government", "Sabah and Sarawak", "women and family", "youth and sports",
    "social welfare", "trade and industry", "tourism and culture", "other",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "summary_en": {"type": "string"},
        "summary_ms": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string", "enum": TOPICS}},
        "entities": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["act", "bill", "agency", "company", "place",
                                                   "person", "organisation", "programme"]},
            },
            "required": ["name", "type"], "additionalProperties": False}},
        "qa_pairs": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "question_speech": {"type": "string"},
                "answer_speech": {"type": "string"},
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "figures": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}, "meaning": {"type": "string"}},
                    "required": ["value", "meaning"], "additionalProperties": False}},
            },
            "required": ["question_speech", "answer_speech", "question", "answer", "figures"],
            "additionalProperties": False}},
        "commitments": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "speech": {"type": "string"},
                "quote": {"type": "string"},
                "promise": {"type": "string"},
                "deadline": {"type": "string"},
                "amount": {"type": "string"},
            },
            "required": ["speech", "quote", "promise", "deadline", "amount"],
            "additionalProperties": False}},
    },
    "required": ["summary_en", "summary_ms", "topics", "entities", "qa_pairs", "commitments"],
    "additionalProperties": False,
}

SYSTEM = """You turn an extract of Malaysia's parliamentary record (Hansard) into a structured record for a public search site. The extract is split into speeches. Each speech starts with its id and its speaker as the record gives it, for example "[S3] Datuk Seri ... [Bagan]:". The speaker labels come from the official record; never change them.

Fill every field:
- summary_en: a neutral summary in English, 2 to 5 sentences. Say who raised what and what the government side answered, naming speakers as the record does. Never judge whether anyone was right.
- summary_ms: the same summary in natural Bahasa Malaysia.
- topics: the topics the extract is about, from the list only.
- entities: Acts, bills, agencies, companies, places, persons, organisations and programmes named in the extract. Write each name as it appears in the text.
- qa_pairs: each question an MP asks and the answer a minister or deputy minister gives, with the speech ids. question and answer are short English paraphrases. figures: every number the answer gives, with value copied exactly as written in the text and its meaning.
- commitments: each promise by a minister or deputy minister to do something in the future, especially with a date or amount. quote must be copied word for word from the cited speech, as one continuous span of the text. promise is a short English paraphrase. deadline and amount are copied from the text, or "" when none is given. A plan stated in general terms with no concrete action is not a commitment.

Use empty lists when the extract has no item of a kind. Never invent a fact that is not in the extract."""

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

JUDGE_SYSTEM = """You audit a structured record that a program made from an extract of Malaysia's Hansard. The record will be published beside the verbatim text with a label saying it was written by AI. A wrong record could misrepresent what an MP or minister said, so audit strictly.

List every defect you find:
- unsupported_or_wrong: a statement in a summary, question, answer, figure or promise that the extract does not support, or gets wrong (a wrong number, a wrong ministry, an overstated claim).
- wrong_speaker: something attributed to the wrong person or the wrong speech id.
- missed_item: an important point, question-answer pair or concrete commitment in the extract that the record leaves out. Only items a reader of the record would expect.
- false_commitment: a listed commitment that is not a promise of future action, or whose quote does not say what the promise claims.
- malay_quality: summary_ms is unnatural, wrong, or says something different from summary_en.
- other: anything else that would mislead a reader.

severity: major when it would mislead a reader or misrepresent a speaker; minor when it is a small omission or wording issue. Report no defect you are unsure of. Set publishable to true only when the record has no major defect."""

_lock = threading.Lock()


# ---------- extracts ----------

_PAGE_HEAD = re.compile(r"^(\d+\s+)?(KK)?DR\.\d{1,2}\.\d{1,2}\.\d{4}(\s+\d+)?$")
_TIME = re.compile(r"^\d{1,2}\.\d{2}\s+(pg|ptg|tgh|mlm)\.?$", re.I)
_SPEAKER = re.compile(
    r"^((?:Tuan|Puan|Dato'|Dato’|Datuk|Dato|Datin|Dr\.|Tan Sri|Toh Puan|Ir\.|Ts\.|Haji|Hajah|"
    r"Yang|Timbalan|Menteri|Kapten|Senator|Prof|Profesor|Tengku|Tunku|Wan|Mohd|Mohamad|Muhammad|"
    r"Setiausaha|Beberapa Ahli|Seorang Ahli)"
    r"[^:\n]{0,160}?):\s*(.*)$"
)


def split_speeches(text: str) -> list[tuple[str, str]]:
    """(speaker label, text) pairs. A rough benchmark splitter, not the phase 2 parser."""
    lines = [ln.strip() for ln in text.replace("\f", "\n").splitlines()]
    lines = [ln for ln in lines if ln and not _PAGE_HEAD.match(ln) and not _TIME.match(ln)]
    joined, wrapped = [], False
    for ln in lines:  # a speaker label can wrap once: "... [Tuan Haji" + "Akmal ... Nasir]: text"
        prev = joined[-1] if joined else ""
        if (not wrapped and prev.count("[") > prev.count("]") and ":" not in prev
                and _SPEAKER.match(prev + " " + ln)):
            joined[-1] = prev + " " + ln
            wrapped = True
        else:
            joined.append(ln)
            wrapped = False
    speeches: list[list] = []
    for ln in joined:
        m = _SPEAKER.match(ln)
        if m and len(m.group(1)) < 170 and not m.group(1).rstrip().endswith((".", ",")):
            speeches.append([m.group(1).strip(), m.group(2)])
        elif speeches:
            speeches[-1][1] += "\n" + ln
    return [(s, t.strip()) for s, t in speeches if t.strip()]


def make_units() -> list[dict]:
    units = []
    for path in sorted(TEXTS.glob("*.txt")):
        chamber, day = path.stem.split("-", 1)
        speeches = split_speeches(path.read_text(encoding="utf-8"))
        windows, cur, size = [], [], 0
        for sp in speeches:
            cur.append(sp)
            size += len(sp[1])
            if size >= UNIT_CHARS:
                windows.append(cur)
                cur, size = [], 0
        if cur:
            windows.append(cur)
        if not windows:
            print(f"{path.name}: no speeches found, skipped")
            continue
        k = UNITS_PER_TEXT[chamber]
        picks = sorted({round((i + 1) * (len(windows) - 1) / (k + 1)) for i in range(k)}) if len(windows) > 1 else [0]
        for w in picks:
            sp = windows[w]
            body = "\n\n".join(f"[S{i + 1}] {s}: {t}" for i, (s, t) in enumerate(sp))
            units.append({"id": f"{chamber}-{day}-w{w}", "chamber": chamber, "date": day,
                          "speeches": [{"id": f"S{i + 1}", "speaker": s, "text": t} for i, (s, t) in enumerate(sp)],
                          "text": body})
    return units


# ---------- calls ----------

def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=KEY_FILE.read_text().strip(), max_retries=4)


def _log(job: str, model: str, usage) -> float:
    pin, pout = PRICES[model]
    cost = (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6
    with _lock, open(config.USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "job": job, "model": model,
                            "endpoint": "messages", "input_tokens": usage.input_tokens,
                            "output_tokens": usage.output_tokens, "cost_usd": round(cost, 6)}) + "\n")
    return cost


def _call(client, model, system, user, schema, job, **extra) -> dict:
    with client.messages.stream(
        model=model, max_tokens=16000, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}}, **extra,
    ) as stream:
        msg = stream.get_final_message()
    cost = _log(job, model, msg.usage)
    if msg.stop_reason not in ("end_turn", "stop_sequence"):
        return {"error": f"stop_reason {msg.stop_reason}", "cost_usd": cost}
    text = next(b.text for b in msg.content if b.type == "text")
    return {"result": json.loads(text), "cost_usd": cost, "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens}


def enrich(client, arm: str, unit: dict) -> dict:
    a = ARMS[arm]
    extra = {"thinking": a["thinking"]} if "thinking" in a else {}
    return _call(client, a["model"], SYSTEM, unit["text"], SCHEMA, f"bench-enrich-{arm}", **extra)


def audit(client, unit: dict, record: dict) -> dict:
    user = ("<extract>\n" + unit["text"] + "\n</extract>\n\n<record>\n"
            + json.dumps(record, ensure_ascii=False, indent=1) + "\n</record>")
    return _call(client, JUDGE, JUDGE_SYSTEM, user, JUDGE_SCHEMA, "bench-enrich-audit")


# ---------- code checks ----------

def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "-", s)  # words split across lines ("berlama-\nlama")
    return re.sub(r"\s+", " ", s).strip().lower()


def code_checks(unit: dict, rec: dict) -> dict:
    by_id = {s["id"]: _norm(s["text"]) for s in unit["speeches"]}
    whole = _norm(unit["text"])
    quotes = [c for c in rec["commitments"]]
    quote_ok = sum(1 for c in quotes if _norm(c["quote"]) and _norm(c["quote"]) in by_id.get(c["speech"], ""))
    figures = [f for q in rec["qa_pairs"] for f in q["figures"]]
    fig_ok = sum(1 for f in figures if _norm(f["value"]) in whole)
    ents = rec["entities"]
    ent_ok = sum(1 for e in ents if _norm(e["name"]) in whole)
    ids_ok = all(q["question_speech"] in by_id and q["answer_speech"] in by_id for q in rec["qa_pairs"])
    return {"quotes": len(quotes), "quotes_verbatim": quote_ok, "figures": len(figures),
            "figures_in_source": fig_ok, "entities": len(ents), "entities_in_source": ent_ok,
            "speech_ids_valid": ids_ok}


# ---------- run and report ----------

def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def run() -> None:
    client = _client()
    units_path = OUT / "units.json"
    if units_path.exists():
        units = json.loads(units_path.read_text(encoding="utf-8"))
    else:
        units = make_units()
        _save(units_path, units)
    print(f"{len(units)} extracts")

    # Blind ids: the audit files carry a random id, and the map lives in its own file.
    key_path = OUT / "blind-key.json"
    key = json.loads(key_path.read_text(encoding="utf-8")) if key_path.exists() else {}
    jobs = [(u, arm) for u in units for arm in ARMS]
    rng = random.Random(7)
    for u, arm in jobs:
        key.setdefault(f"{u['id']}|{arm}", f"r{rng.randrange(16**6):06x}")
    _save(key_path, key)

    def one(job):
        u, arm = job
        rid = key[f"{u['id']}|{arm}"]
        epath, apath = OUT / "enriched" / f"{u['id']}--{arm}.json", OUT / "audits" / f"{rid}.json"
        if not epath.exists():
            out = enrich(client, arm, u)
            _save(epath, out)
        out = json.loads(epath.read_text(encoding="utf-8"))
        if "result" in out and not apath.exists():
            _save(apath, audit(client, u, out["result"]))
        print(f"done {u['id']} {arm}", flush=True)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(one, jobs))


def report() -> None:
    units = {u["id"]: u for u in json.loads((OUT / "units.json").read_text(encoding="utf-8"))}
    key = json.loads((OUT / "blind-key.json").read_text(encoding="utf-8"))
    rows = {arm: {"n": 0, "errors": 0, "cost": 0.0, "in": 0, "out": 0, "quotes": 0, "quotes_verbatim": 0,
                  "figures": 0, "figures_in_source": 0, "entities": 0, "entities_in_source": 0,
                  "ids_bad": 0, "publishable": 0, "major": 0, "minor": 0, "cats": {}, "audit_cost": 0.0}
            for arm in ARMS}
    for uid, u in units.items():
        for arm in ARMS:
            r = rows[arm]
            e = json.loads((OUT / "enriched" / f"{uid}--{arm}.json").read_text(encoding="utf-8"))
            r["n"] += 1
            r["cost"] += e["cost_usd"]
            if "result" not in e:
                r["errors"] += 1
                continue
            r["in"] += e["input_tokens"]
            r["out"] += e["output_tokens"]
            c = code_checks(u, e["result"])
            for k in ("quotes", "quotes_verbatim", "figures", "figures_in_source", "entities", "entities_in_source"):
                r[k] += c[k]
            r["ids_bad"] += not c["speech_ids_valid"]
            a = json.loads((OUT / "audits" / f"{key[uid + '|' + arm]}.json").read_text(encoding="utf-8"))
            r["audit_cost"] += a["cost_usd"]
            if "result" not in a:
                continue
            r["publishable"] += a["result"]["publishable"]
            for d in a["result"]["defects"]:
                r[d["severity"]] += 1
                if d["severity"] == "major":
                    r["cats"][d["category"]] = r["cats"].get(d["category"], 0) + 1

    corpus_tokens = 100e6
    print("| Measure | " + " | ".join(ARMS) + " |")
    print("|---|" + "---|" * len(ARMS))

    def line(name, fn):
        print(f"| {name} | " + " | ".join(fn(rows[a]) for a in ARMS) + " |")

    line("Extracts", lambda r: f"{r['n']} ({r['errors']} failed)")
    line("Publishable as is (audit)", lambda r: f"{r['publishable']} of {r['n'] - r['errors']}")
    line("Major defects", lambda r: str(r["major"]))
    line("Minor defects", lambda r: str(r["minor"]))
    line("Major by kind", lambda r: ", ".join(f"{k} {v}" for k, v in sorted(r["cats"].items())) or "none")
    line("Commitment quotes word for word", lambda r: f"{r['quotes_verbatim']} of {r['quotes']}")
    line("Figures found in the text", lambda r: f"{r['figures_in_source']} of {r['figures']}")
    line("Entities found in the text", lambda r: f"{r['entities_in_source']} of {r['entities']}")
    line("Bad speech ids", lambda r: str(r["ids_bad"]))
    line("Output tokens per input token", lambda r: f"{r['out'] / max(r['in'], 1):.2f}")
    line("Benchmark cost (standard rates)", lambda r: f"US${r['cost']:.2f}")
    line("Full corpus on the Batch API", lambda r: f"about US${r['cost'] / max(r['in'], 1) * corpus_tokens / 2:.0f}")
    print(f"\nAudit cost: US${sum(r['audit_cost'] for r in rows.values()):.2f}")


if __name__ == "__main__":
    {"run": run, "report": report}[sys.argv[1] if len(sys.argv) > 1 else "report"]()
