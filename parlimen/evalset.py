"""Test questions with gold places, stored in data/eval/ (git-ignored):

- law.json: 150 questions from random law chunks, 75 drawn from English texts and asked in
  English, 75 from Malay texts and asked in Malay. Gold: the chunk's Act and section, in either
  language (the two texts are parallel).
- debate.json: 150 questions from random debate chunks of enriched extracts, half asked in
  English, half in Malay. Gold: the chunk's sitting and speech range.
- pairs.json: 50 questions (25 law, 25 debate), each written in English and in Malay; the recall
  gap between the two halves is the language gap.
- filters.json: 25 debate questions that name a year, a Parliament, a party or a speaker; the
  eval passes the filter with the question.
- hand.json: 30 questions a student, journalist or business owner would ask, with reference
  answers, written by hand (not generated here).

Sonnet 5.5 writes the generated questions from the chunk alone, told to ask the way a searcher
would and to avoid the passage's rare words, so a question matches by meaning, not spelling.

A gold entry is {"kind": "law", "act", "section"} or {"kind": "debate", "sitting", "seqs":
[first, last]}; a chunk matches a debate entry when it is from the same sitting ("DR-2024-03-12")
and its speeches overlap the range.

Run:  python -m parlimen.evalset build [--sets law debate pairs filters] [--workers 6]
"""

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

from . import config, enrich
from .index import Row, connect

EVAL = config.DATA / "eval"
GENERATED = ("law", "debate", "pairs", "filters")
SETS = GENERATED + ("hand",)
MODEL = "claude-sonnet-5-5"
LANGS = {"en": "English", "ms": "Malay (Bahasa Melayu)"}


def load(name: str) -> list[dict]:
    path = EVAL / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save(name: str, items: list[dict]) -> Path:
    EVAL.mkdir(parents=True, exist_ok=True)
    path = EVAL / f"{name}.json"
    path.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def gold_of(r: Row) -> dict:
    if r.kind == "law":
        return {"kind": "law", "act": r.act, "section": r.section}
    return {"kind": "debate", "sitting": r.unit[:-4], "seqs": [r.seq_first, r.seq_last]}


def matches(r: Row, g: dict) -> bool:
    if r.kind != g["kind"]:
        return False
    if g["kind"] == "law":
        return r.act == g["act"] and r.section == g["section"]
    return r.unit[:-4] == g["sitting"] and r.seq_first <= g["seqs"][1] and r.seq_last >= g["seqs"][0]


# ---------- drawing chunks ----------

def _pool(con, kind: str, min_tokens: int, extra: str = "") -> list[int]:
    return [i for (i,) in con.execute(f"SELECT id FROM chunks WHERE kind = ? AND tokens >= ? {extra} ORDER BY id",
                                      (kind, min_tokens))]


def draw(con, n: int, kind: str, rng: random.Random, taken: set[int], lang: str = "", min_tokens: int = 200) -> list[Row]:
    """n chunks of one kind, each from a different Act or extract, none drawn before."""
    from .index import rows
    extra = f"AND lang = '{lang}'" if lang else ""
    if kind == "debate":
        extra += " AND note != ''"  # enriched extracts: a run of real debate, not a roll call
    ids = _pool(con, kind, min_tokens, extra)
    rng.shuffle(ids)
    picked: list[Row] = []
    owners: set[str] = set()
    for i in ids:
        if i in taken:
            continue
        r = rows(con, [i])[0]
        owner = r.act if kind == "law" else r.unit
        if owner in owners:
            continue
        owners.add(owner)
        taken.add(i)
        picked.append(r)
        if len(picked) == n:
            break
    return picked


# ---------- prompts ----------

PROMPT = """Here is a passage from {source}.

<passage>
{header}
{text}
</passage>

Write a question that a {who} might type into a search box, which this passage answers.

Rules:
- The passage alone must answer it.
- Ask about its substance: what the law requires or allows, or what was asked, promised, reported or argued.
- Do not copy the passage's distinctive words or phrases: use everyday words of your own, so the question matches the passage by meaning, not by spelling. Act names, place names and people's names are allowed.
- Do not name the section number, the sitting date or the speech.
- One sentence, at most 25 words.
{extra}
If the passage has nothing a searcher would ask about (a roll call, procedure only, a table of amendments, a deleted section), set "usable" to false.

Also give the answer in one sentence."""

SOURCES = {"law": "a Malaysian Act of Parliament", "debate": "the Hansard of Malaysia's Dewan Rakyat (debates, mostly in Malay)"}
WHO = {"law": "law student, journalist or business owner", "debate": "journalist, researcher or voter"}


def schema(fields: list[str]) -> dict:
    props = {"usable": {"type": "boolean"}, **{f: {"type": "string"} for f in fields}}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def request(r: Row, extra: str, fields: list[str]) -> dict:
    content = PROMPT.format(source=SOURCES[r.kind], header=r.header, text=r.text, who=WHO[r.kind], extra=extra)
    return {"model": MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": content}],
            "output_config": {"format": {"type": "json_schema", "schema": schema(fields)}}}


def single(lang: str) -> tuple[str, list[str]]:
    return f"- Write the question in {LANGS[lang]}.", ["question", "answer"]


PAIR = ("- Write the question in English as \"question_en\", and the same question in natural Malay "
        "(Bahasa Melayu) as \"question_ms\": a faithful translation, as a Malaysian would ask it.",
        ["question_en", "question_ms", "answer"])


def filter_for(r: Row, con, k: int) -> tuple[dict, str]:
    """The filter a filter question carries, round robin: year, Parliament, party, speaker."""
    spk = [dict(s) for s in con.execute("SELECT name, party, tokens FROM speakers WHERE chunk = ? ORDER BY tokens DESC",
                                        (r.id,))]
    kinds = ["year", "parliament", "party", "speaker"]
    for kind in kinds[k % 4:] + kinds[:k % 4]:
        if kind == "year":
            y = r.date[:4]
            return {"date_from": f"{y}-01-01", "date_to": f"{y}-12-31"}, f"in {y}"
        if kind == "parliament":
            return {"parliament": r.parliament}, f"in the {r.parliament}th Parliament"
        if kind == "party" and spk and spk[0]["party"]:
            return {"party": spk[0]["party"]}, f"by {spk[0]['party']} MPs"
        if kind == "speaker" and spk:
            return {"speaker": spk[0]["name"]}, f"by {spk[0]['name']}"
    y = r.date[:4]
    return {"date_from": f"{y}-01-01", "date_to": f"{y}-12-31"}, f"in {y}"


# ---------- building ----------

def plan(con, seed: int = 11) -> dict[str, list[tuple[Row, dict]]]:
    """Every generated question's chunk and request details, by set; one chunk is used once."""
    rng = random.Random(seed)
    taken: set[int] = set()
    out: dict[str, list[tuple[Row, dict]]] = {s: [] for s in GENERATED}
    for lang, code in (("BI", "en"), ("BM", "ms")):
        out["law"] += [(r, {"lang": code}) for r in draw(con, 75, "law", rng, taken, lang)]
    for k, r in enumerate(draw(con, 150, "debate", rng, taken, min_tokens=250)):
        out["debate"].append((r, {"lang": "en" if k % 2 == 0 else "ms"}))
    out["pairs"] = [(r, {"pair": True}) for r in draw(con, 25, "law", rng, taken, "BI")
                    + draw(con, 25, "debate", rng, taken, min_tokens=250)]
    for k, r in enumerate(draw(con, 25, "debate", rng, taken, min_tokens=250)):
        flt, phrase = filter_for(r, con, k)
        out["filters"].append((r, {"lang": "en" if k % 2 == 0 else "ms", "filters": flt, "phrase": phrase}))
    return out


def ask(client, r: Row, spec: dict) -> dict:
    if spec.get("pair"):
        extra, fields = PAIR
    else:
        extra, fields = single(spec["lang"])
        if "phrase" in spec:
            extra += (f"\n- The question must ask for statements made {spec['phrase']}, and say so in its "
                      "own words (the searcher filters on it).")
    try:
        return enrich.call(client, request(r, extra, fields), "eval-questions")
    except anthropic.APIError as e:
        return {"error": str(e)[:300], "cost_usd": 0.0}


def build(sets=GENERATED, workers: int = 6, seed: int = 11, log=print) -> dict[str, int]:
    con = connect()
    jobs = plan(con, seed)
    client = enrich._client()
    counts = {}
    for name in sets:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            answers = list(pool.map(lambda job: ask(client, *job), jobs[name]))
        items = []
        for (r, spec), out in zip(jobs[name], answers):
            res = out.get("result")
            if not res or not res["usable"]:
                continue
            base = {"answer": res["answer"], "chunk": r.id, "gold": [gold_of(r)], "kind": r.kind}
            n = len(items) + 1
            if spec.get("pair"):
                items.append({"id": f"{name[0]}{n:03d}en", "pair": n, "lang": "en", "question": res["question_en"], **base})
                items.append({"id": f"{name[0]}{n:03d}ms", "pair": n, "lang": "ms", "question": res["question_ms"], **base})
            else:
                items.append({"id": f"{name[0]}{n:03d}", "lang": spec["lang"], "question": res["question"],
                              **({"filters": spec["filters"]} if "filters" in spec else {}), **base})
        save(name, items)
        cost = sum(o.get("cost_usd", 0) for o in answers)
        counts[name] = len(items)
        log(f"{name}: {len(items)} questions from {len(jobs[name])} chunks, US${cost:.2f}")
    return counts


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--sets", nargs="+", default=list(GENERATED), choices=list(GENERATED))
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--seed", type=int, default=11)
    p = sub.add_parser("pilot", help="5 questions of each generated set, printed, not saved")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.sets, a.workers, a.seed)
    else:
        con = connect()
        jobs = plan(con)
        client = enrich._client()
        for name in GENERATED:
            for r, spec in jobs[name][:5]:
                out = ask(client, r, spec)
                print(f"--- {name} {spec} chunk {r.id}\n{r.header}\n{r.text[:300]}\n=> {out.get('result', out.get('error'))}\n")


if __name__ == "__main__":
    main()
