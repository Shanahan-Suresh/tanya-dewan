"""Record real answers from the running full site, for the static demo (tools/static_demo.py).

Each question goes through the site's own /api/ask/stream, and every server-sent event is saved
with the milliseconds since the question was sent, so the demo can play the answer back at the
pace it was written. The questions are the site's example questions (parlimen/web/app.py EXAMPLES).

Run, with the full site up on port 8780 (each answer costs about [amount removed], logged as usual):
    .venv\\Scripts\\python.exe tools\\record_answers.py [--site http://127.0.0.1:8780] [--only SLUG ...]
Writes docs/demo/answers/<slug>.json: {"question", "lang", "recorded", "events": [{"t", "event", "data"}]}.
"""
import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from parlimen.web.app import EXAMPLES  # noqa: E402

OUT = ROOT / "docs" / "demo" / "answers"


def slug(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:60]


def record(site: str, question: str) -> list[dict]:
    events, start = [], time.monotonic()
    with httpx.stream("POST", f"{site}/api/ask/stream", json={"question": question}, timeout=180) as res:
        res.raise_for_status()
        buf = ""
        for chunk in res.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                ev, data = "message", ""
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        data += line[5:].strip()
                if data:
                    events.append({"t": round((time.monotonic() - start) * 1000), "event": ev,
                                   "data": json.loads(data)})
    return events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="http://127.0.0.1:8780")
    ap.add_argument("--only", nargs="*", default=None, help="record only these slugs")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, questions in EXAMPLES.items():
        for q in questions:
            s = slug(q)
            if a.only and s not in a.only:
                continue
            events = record(a.site, q)
            last = events[-1]["event"] if events else "none"
            if last != "done":
                print(f"FAILED {s}: last event {last}", flush=True)
                continue
            done = events[-1]["data"]
            (OUT / f"{s}.json").write_text(json.dumps(
                {"question": q, "lang": lang, "recorded": date.today().isoformat(), "events": events},
                ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{s}: {len(events)} events, {len(done.get('sources') or [])} sources, "
                  f"{events[-1]['t'] / 1000:.1f} s, US${done.get('usd') or 0:.4f}", flush=True)


if __name__ == "__main__":
    main()
