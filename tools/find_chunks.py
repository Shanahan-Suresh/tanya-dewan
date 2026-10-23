"""Keyword search over index.db for writing eval questions by hand: no models, no GPU.

    .venv\\Scripts\\python.exe tools\\find_chunks.py "minimum wage" [--kind law|debate] [--act 265]
        [--date-from 2023-01-01] [--date-to 2023-12-31] [--n 10] [--full]
    .venv\\Scripts\\python.exe tools\\find_chunks.py --id 12345      one chunk in full

Prints each hit's id, header, speech range and the start of its text (--full: all of it).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parlimen.index import connect, rows  # noqa: E402
from parlimen.search import Filters, Searcher  # noqa: E402


class NoModel:
    def query(self, *a, **k):
        raise RuntimeError("keyword search only")


def show(r, full: bool) -> None:
    span = f" speeches {r.seq_first}-{r.seq_last} of {r.unit}" if r.kind == "debate" else f" Act {r.act} s.{r.section} {r.lang}"
    print(f"=== chunk {r.id}{span}\n{r.header}")
    if r.note:
        print(r.note[:300])
    print(r.text if full else r.text[:500])
    print()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--id", type=int)
    ap.add_argument("--kind")
    ap.add_argument("--act")
    ap.add_argument("--date-from")
    ap.add_argument("--date-to")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    if a.id is not None:
        show(rows(connect(), [a.id])[0], True)
        return
    s = Searcher(embedder=NoModel(), reranker=None, rerank_size=None)
    f = Filters(kind=a.kind, act=a.act, date_from=a.date_from, date_to=a.date_to)
    for h in s.bm25(a.query, f, a.n):
        show(s.row(h.id), a.full)


if __name__ == "__main__":
    main()
