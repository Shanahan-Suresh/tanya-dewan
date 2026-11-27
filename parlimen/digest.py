"""A weekly digest for one sector, written from the week's records: a working sample of a sector alert.

The week's agenda items on the sector's topics go to Haiku 5.5 with their AI summaries, their
question-answer pairs and their checked commitments, each under its record id. Haiku writes a
neutral digest (structured output): a few items, each citing the ids it rests on, and a list of
the dated or costed commitments to watch. Code then keeps only items whose ids are in the input,
and the page quotes every cited commitment verbatim from the record, never from the model. Each
item links to the record pages, so a reader checks it against the Hansard.

Run:  python -m parlimen.digest --sector energy --from 2026-10-19 --to 2026-10-23 [--base URL]
      -> data/digests/<sector>-<from>-<to>.html and .json
"""
import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

from . import config, enrich
from .records import Records, slug, who

MODEL = "claude-haiku-5-5"
OUT = config.DATA / "digests"
SECTORS = {
    "energy": ("Energy, water and climate", ["energy and water", "environment and climate"]),
    "digital": ("Digital and telecoms", ["digital and telecoms"]),
    "labour": ("Labour and jobs", ["labour and jobs"]),
    "health": ("Health", ["health"]),
    "trade": ("Trade, industry and tax", ["trade and industry", "tax"]),
    "transport": ("Transport and infrastructure", ["transport", "infrastructure"]),
    "agriculture": ("Agriculture and food", ["agriculture and food"]),
}
MAX_CHARS = 300_000  # the week's records sent at most; a busier week keeps the items in date order

SYSTEM = """You write a weekly digest of Malaysia's Parliament for professionals who follow one sector (consultancies, chambers of commerce, corporate affairs teams). You get the week's records on that sector from the Dewan Rakyat Hansard, each under an id in square brackets. The summaries, question-answer joins and commitment notes were written by a model from the verbatim record.
Rules:
- Use only the records. Every item cites the ids it rests on, in `ids`. Cite a commitment by its own id (it ends in -cN) and a question-answer pair by its id (it ends in -qN).
- Say who said what: name the minister, deputy minister or MP and their office as the record gives it. Never present an MP's claim as fact.
- Stay neutral: no judgement of people, parties or policies, no words such as "slammed", "failed" or "welcome". Describe what was said, asked, announced or promised.
- Prefer concrete content: figures, dates, named projects, bills, policies, deadlines.
- 5 to 8 items, most important for the sector first; each body two to four sentences, in plain English.
- `watch`: up to 8 commitments with a date or an amount, one line each, citing the commitment id.
- `headline`: one sentence on the week for this sector. `intro`: two sentences at most."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "intro": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "body": {"type": "string"},
            "ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["title", "body", "ids"], "additionalProperties": False}},
        "watch": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["text", "ids"], "additionalProperties": False}},
    },
    "required": ["headline", "intro", "items", "watch"],
    "additionalProperties": False,
}


def gather(r: Records, topics: list[str], date_from: str, date_to: str) -> list[dict]:
    """The week's items on the topics, each with its pairs and commitments."""
    units = r.units_between(date_from, date_to, [slug(t) for t in topics])
    for u in units:
        u["qa"] = r.unit_qa(u["id"])
        u["commitments"] = r.unit_commitments(u["id"])
    return units


def prompt(units: list[dict], sector: str, date_from: str, date_to: str) -> str:
    parts = [f"Sector: {sector}. Week: {date_from} to {date_to}.\n"]
    used = 0
    for u in units:
        lines = [f"[{u['id']}] {'Dewan Rakyat' if u['chamber'] == 'DR' else 'Special Chamber'} {u['date']}: "
                 f"{u['business']}", f"Summary (AI): {u['summary_en']}"]
        for q in u["qa"]:
            lines.append(f"[{q['id']}] Question by {q['asker']}: {q['question']} Answer by "
                         f"{who(q['answerer'], q['office'])}: {q['answer']}")
        for c in u["commitments"]:
            extra = "; ".join(x for x in (c["deadline"] and f"by {c['deadline']}", c["amount"] and f"amount {c['amount']}") if x)
            lines.append(f"[{c['id']}] Commitment by {who(c['speaker'], c['office'])}: "
                         f"{c['promise']}{' (' + extra + ')' if extra else ''}. Quote: \"{c['quote']}\"")
        block = "\n".join(lines)
        if used + len(block) > MAX_CHARS:
            parts.append("[Further items left out: the week is long.]")
            break
        used += len(block)
        parts.append(block)
    return "\n\n".join(parts)


def check(result: dict, units: list[dict]) -> tuple[dict, list[str]]:
    """Keep only cited ids that are in the input; drop an item or watch line left with none."""
    known = {u["id"] for u in units} | {q["id"] for u in units for q in u["qa"]} | {
        c["id"] for u in units for c in u["commitments"]}
    dropped = []
    out = {"headline": result["headline"], "intro": result["intro"], "items": [], "watch": []}
    for key in ("items", "watch"):
        for it in result.get(key, []):
            ids = [i for i in it["ids"] if i in known]
            dropped += [i for i in it["ids"] if i not in known]
            if ids:
                out[key].append({**it, "ids": ids})
            else:
                dropped.append(f"{key}: {it.get('title') or it.get('text')}")
    return out, dropped


def write(client, units: list[dict], sector: str, date_from: str, date_to: str) -> dict:
    params = {"model": MODEL, "max_tokens": 16000, "system": SYSTEM,
              "messages": [{"role": "user", "content": prompt(units, sector, date_from, date_to)}],
              "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}}}
    return enrich.call(client, params, "digest")


def _when(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def render(d: dict, units: list[dict], sector: str, date_from: str, date_to: str, base: str) -> str:
    esc = html.escape
    by_id = {u["id"]: u for u in units}
    commit = {c["id"]: c for u in units for c in u["commitments"]}
    qa = {q["id"]: q for u in units for q in u["qa"]}

    def unit_of(i: str) -> str:
        return i.rsplit("-", 1)[0] if i in commit or i in qa else i

    def link(i: str) -> str:
        u = by_id[unit_of(i)]
        seq = commit[i]["seq"] if i in commit else qa[i]["answerer_seq"] if i in qa else None
        url = f"{base}/debate/{u['id']}" + (f"#seq-{seq}" if seq else "")
        return f'<a href="{esc(url)}">{"Dewan Rakyat" if u["chamber"] == "DR" else "Special Chamber"}, {_when(u["date"])}</a>'

    def sources(ids: list[str]) -> str:
        seen, out = set(), []
        for i in ids:
            if unit_of(i) in seen and i not in commit:
                continue
            seen.add(unit_of(i))
            if i in commit:
                c = commit[i]
                out.append(f'<li><q>{esc(c["quote"])}</q> <span class="who">{esc(c["speaker"])}, {link(i)}</span></li>')
            else:
                out.append(f"<li>{link(i)}: {esc(by_id[unit_of(i)]['business'][:120])}</li>")
        return f'<ul class="src">{"".join(out)}</ul>'

    items = "".join(f'<section><h2>{esc(it["title"])}</h2><p>{esc(it["body"])}</p>{sources(it["ids"])}</section>'
                    for it in d["items"])
    watch = "".join(f"<li>{esc(w['text'])} {sources(w['ids'])}</li>" for w in d["watch"])
    index = "".join(f'<li><a href="{esc(base)}/debate/{u["id"]}">{_when(u["date"])}</a>: {esc(u["business"][:140])}</li>'
                    for u in units)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(sector)}: Parliament this week</title>
<style>
:root {{ --ink:#1c1f23; --muted:#5e646c; --line:#dedbd2; --accent:#0f5e63; --ai:#2e4682; --bg:#f7f6f2; --card:#fff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --ink:#e7e5df; --muted:#9aa0a8; --line:#33373d; --accent:#5fb8bd; --ai:#a9bbef; --bg:#15171a; --card:#1d2024; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 system-ui, "Segoe UI", sans-serif; }}
main {{ max-width:760px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font:600 1.7rem/1.25 Georgia, serif; margin:.2em 0; }}
h2 {{ font-size:1.1rem; margin:1.6em 0 .3em; }}
.eyebrow, .who, .foot {{ color:var(--muted); font-size:.88rem; }}
.ai {{ color:var(--ai); font-size:.88rem; border-left:3px solid var(--ai); padding-left:10px; }}
.headline {{ font-size:1.12rem; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:4px 16px 10px; margin:12px 0; }}
ul.src {{ font-size:.9rem; padding-left:1.1em; }}
q {{ font-family:Georgia, serif; }}
a {{ color:var(--accent); }}
details {{ margin-top:24px; }}
</style></head>
<body><main>
<p class="eyebrow">Tanya Dewan · weekly digest · {esc(sector)}</p>
<h1>Parliament this week: {_when(date_from)} to {_when(date_to)}</h1>
<p class="headline">{esc(d["headline"])}</p>
<p>{esc(d["intro"])}</p>
<p class="ai">Written by AI (Claude) from this week's Hansard. Quotes are verbatim and checked against the Hansard text. Each item links to the speeches it rests on.</p>
{items}
{f'<h2>Commitments to watch</h2><ul>{watch}</ul>' if watch else ''}
<details><summary>All debates on this sector this week ({len(units)})</summary><ul class="src">{index}</ul></details>
<p class="foot">Source: Hansard of the Dewan Rakyat, Parliament of Malaysia. This is general information from the published record, not legal advice.</p>
</main></body></html>
"""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sector", choices=list(SECTORS), required=True)
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8780", help="the site address the links point at")
    a = ap.parse_args()
    name, topics = SECTORS[a.sector]
    units = gather(Records(), topics, a.date_from, a.date_to)
    if not units:
        print(f"No items on {name} between {a.date_from} and {a.date_to}.")
        return
    print(f"{len(units)} items, {sum(len(u['qa']) for u in units)} pairs, "
          f"{sum(len(u['commitments']) for u in units)} commitments")
    ans = write(enrich._client(), units, name, a.date_from, a.date_to)
    if "error" in ans:
        sys.exit(f"digest failed: {ans['error']} (US${ans['cost_usd']:.4f})")
    d, dropped = check(ans["result"], units)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / f"{a.sector}-{a.date_from}-{a.date_to}"
    stem.with_suffix(".json").write_text(json.dumps({"raw": ans["result"], "kept": d, "dropped": dropped},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    stem.with_suffix(".html").write_text(render(d, units, name, a.date_from, a.date_to, a.base.rstrip("/")),
                                         encoding="utf-8")
    print(f"{stem.with_suffix('.html')}: {len(d['items'])} items, {len(d['watch'])} to watch, "
          f"{len(dropped)} unknown ids dropped; US${ans['cost_usd']:.4f}")


if __name__ == "__main__":
    main()
