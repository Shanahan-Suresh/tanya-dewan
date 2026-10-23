"""Phase 0 measurements on a sample of sitting days.

For each sampled sitting: download the PDF (cached), extract its text with pdfplumber, count
pages and characters, count tokens with the Claude token-counting endpoint (free, logged), and
look for the draft or revised marking on the first pages. Also sends one HEAD request per
sitting of the meeting in progress to read when each PDF went up (publishing lag).

Writes data/phase0/sample.json and the extracted text to data/raw/text/. Run from the repo
root: .venv\\Scripts\\python.exe tools\\phase0_sample.py [DR|KK]. KK samples the Dewan Khas,
writes data/phase0/sample-KK.json and skips the lag check.
"""

import json
import re
import sys
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
import pdfplumber

from parlimen import config, fetch
from parlimen.sittings import read_csv

SAMPLE_DATES = ["2018-07-16", "2020-11-26", "2022-03-23", "2024-03-12", "2026-10-20"]
MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5"]
MARKERS = re.compile(r"(BELUM DISEMAK|DISEMAK|PINDAAN|NASKHAH SEMENTARA|UNREVISED)", re.I)
KEY_FILE = Path.home() / ".claude" / "anthropic-api-key.txt"


def log_usage(entry: dict) -> None:
    config.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(config.USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def extract(pdf_bytes: bytes) -> tuple[int, str]:
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return len(pages), "\n\f\n".join(pages)


def main() -> None:
    chamber = sys.argv[1] if len(sys.argv) > 1 else "DR"
    sittings = {s.date: s for s in read_csv() if s.chamber == chamber}
    # The Dewan Khas sits on fewer days, so its sample is five days spread evenly over the list.
    days = sorted(sittings)
    dates = SAMPLE_DATES if chamber == "DR" else [days[i * (len(days) - 1) // 4] for i in range(5)]
    client = anthropic.Anthropic(api_key=KEY_FILE.read_text().strip())
    text_dir = config.RAW / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for d in dates:
        s = sittings[d]
        pdf = fetch.get(s.url)
        n_pages, text = extract(pdf)
        (text_dir / f"{chamber}-{d}.txt").write_text(text, encoding="utf-8")
        row = {"date": d, "parliament": s.parliament, "pdf_bytes": len(pdf), "pages": n_pages,
               "chars": len(text), "markers": sorted({m.upper() for m in MARKERS.findall(text[:6000])})}
        for model in MODELS:
            count = client.messages.count_tokens(model=model, messages=[{"role": "user", "content": text}])
            row[f"tokens_{model}"] = count.input_tokens
            log_usage({"at": datetime.now(timezone.utc).isoformat(), "job": "phase0-count",
                       "model": model, "endpoint": "count_tokens", "input_tokens": count.input_tokens,
                       "cost_usd": 0.0})
        results.append(row)
        print(row)

    lag = []
    for s in [s for s in sittings.values() if s.source == "current" and chamber == "DR"]:
        r = fetch.head(s.url)
        modified = r.headers.get("last-modified")
        up = parsedate_to_datetime(modified).date() if modified else None
        lag.append({"date": s.date, "status": r.status_code, "last_modified": modified,
                    "days_after_sitting": (up - date.fromisoformat(s.date)).days if up else None})
        print(lag[-1])

    out = config.DATA / "phase0" / ("sample.json" if chamber == "DR" else f"sample-{chamber}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"measured": time.strftime("%Y-%m-%d"), "sample": results,
                               "publishing_lag": lag}, indent=2), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
