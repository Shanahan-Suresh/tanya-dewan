"""Hybrid search over the law and the debates, as in novel-rag:

    question -> filters -> BM25 top 100 + vector top 100 -> RRF -> rerank top 20 -> top 8 -> expand

The reranker is Haiku 5.5 through the Messages API (`config.RERANKER`, chosen by the phase 5 eval);
a Qwen3 size there selects the local cross-encoder instead.

Filters: kind (law or debate), Act, language of a law text, date range, Parliament, chamber,
speaker, party (on the sitting's date) and topic. Every stage records its ranked list and its time
in a `Trace`. `mode` stops early for the eval's arms: "bm25", "dense", "hybrid" (fused) or "full"
(reranked).

Expansion merges each hit with its neighbouring chunks of the same section or extract. A law
passage then brings the sections it names (`xrefs`, up to XREFS), and `debates_for_act` lists the
bill debates linked to an Act.

Run:  python -m parlimen.search "question" [--kind law|debate] [--act 265] [--party DAP] [--trace]
"""

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from . import config
from .chunk import MIN_SPEAKER_TOKENS
from .index import FTS, VARIANTS, Row, connect, db_path, load_vectors, rows

MODES = ("bm25", "dense", "hybrid", "full")

# Question words that carry no meaning for keyword search, English and Malay.
STOPWORDS = frozenset("""a an and are as at be but by can did do does for from had has have he her his how
i if in into is it its me my of on or our she so that the their them then there they this to was we were
what when where which who whom why will with would you your
ada adakah adalah agar akan apa apakah atau bagaimana bagi bahawa berapa berapakah boleh dan dalam dari
daripada dengan di dia ialah ini itu jika juga kami kita ke kenapa kepada mana manakah mengapa oleh pada
para sahaja sama saya sebagai sejak siapa siapakah tentang telah tersebut untuk yang""".split())


@dataclass
class Filters:
    kind: str | None = None        # "law" or "debate"
    act: str | None = None         # law sections of this Act, or debates of its bills
    lang: str | None = None        # "BI" or "BM" for law texts
    date_from: str | None = None   # ISO dates, inclusive: sitting dates (reprint dates when kind="law")
    date_to: str | None = None
    parliament: int | None = None
    chamber: str | None = None     # "DR" or "KK"
    speaker: str | None = None     # part of a speaker's name
    party: str | None = None
    topic: str | None = None

    def describe(self) -> str:
        parts = [f"{k}={v}" for k, v in vars(self).items() if v not in (None, "")]
        return ", ".join(parts) or "no filter"

    def needs_sql(self) -> bool:
        return bool(self.speaker or self.party or self.topic)


@dataclass
class Hit:
    id: int
    score: float


@dataclass
class Stage:
    name: str
    hits: list[Hit]
    ms: float


@dataclass
class Passage:
    """Neighbouring chunks of one section or extract merged into one stretch of text."""
    ids: list[int]
    score: float
    kind: str
    key: str
    header: str
    text: str
    act: str = ""
    lang: str = ""
    section: str = ""
    chamber: str = ""
    date: str = ""
    unit: str = ""
    via: str = ""                  # "cross-reference from section 12" for an added section

    @property
    def cite(self) -> str:
        if self.kind == "law":
            return f"Act {self.act}, s. {self.section} ({self.lang}, as at {self.date})"
        return f"{'Dewan Rakyat' if self.chamber == 'DR' else 'Special Chamber'} {self.date} ({self.unit})"


@dataclass
class Trace:
    question: str
    filters: Filters
    mode: str
    stages: list[Stage] = field(default_factory=list)
    passages: list[Passage] = field(default_factory=list)

    def stage(self, name: str) -> Stage | None:
        return next((s for s in self.stages if s.name == name), None)

    @property
    def ranked(self) -> list[int]:
        """The final ranked chunk ids before expansion: what the eval scores."""
        return [h.id for h in self.stages[-1].hits] if self.stages else []


def keyword_query(question: str) -> str:
    """FTS5 query: every meaningful word, OR-ed, each quoted so FTS5 syntax cannot leak in."""
    seen: list[str] = []
    for w in re.findall(r"[^\W_]+", question.lower()):
        if w not in STOPWORDS and w not in seen:
            seen.append(w)
    return " OR ".join(f'"{w}"' for w in seen)


def rrf(lists: Sequence[Sequence[Hit]], k: int = config.RRF_K) -> list[Hit]:
    scores: dict[int, float] = {}
    for hits in lists:
        for rank, h in enumerate(hits, start=1):
            scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (k + rank)
    return [Hit(i, s) for i, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


_CONTINUED = re.compile(r"^[^\n]{1,200}? \(continued(?:, part \d+ of \d+)?\): ")


def merge_texts(a: str, b: str) -> str:
    """Join neighbouring chunks, dropping the sentences b repeats from a's end (and the
    "(continued)" label that opens b when it carries on a's last speech)."""
    if _CONTINUED.match(b):
        b = _CONTINUED.sub("", b, count=1)
        sep = " "
    else:
        sep = "\n\n"
    first = b.split(" ", 1)[0]
    at = a.find(first) if first else -1
    while at != -1:
        if (at == 0 or a[at - 1].isspace()) and b.startswith(a[at:]):
            return a[:at] + b
        at = a.find(first, at + 1)
    return a + sep + b


class Searcher:
    def __init__(self, root: Path = config.INDEX, size: str = config.EMBEDDER, variant: str = config.VARIANT,
                 rerank_size: str | None = config.RERANKER, embedder=None, reranker=None):
        self.con = connect(db_path(root))
        self.root, self.size, self.variant = root, size, variant
        cols = list(zip(*self.con.execute(
            "SELECT kind = 'law', act, lang, REPLACE(date, '-', ''), parliament, chamber FROM chunks ORDER BY id")))
        cols = cols or [()] * 6
        self.is_law = np.array(cols[0], dtype=bool)
        self.act = np.array(cols[1], dtype=str)
        self.lang = np.array(cols[2], dtype=str)
        self.date = np.array([int(d or 0) for d in cols[3]], dtype=np.int64)
        self.parl = np.array(cols[4], dtype=np.int64)
        self.chamber = np.array(cols[5], dtype=str)
        self._vectors = None
        self._rows: dict[int, Row] = {}
        if embedder is None:
            from .models import Embedder
            embedder = Embedder(size)
        if reranker is None and rerank_size == "haiku":
            from .llm_rerank import HaikuReranker
            reranker = HaikuReranker()
        elif reranker is None and rerank_size:
            from .models import Reranker
            reranker = Reranker(rerank_size)
        self.embedder, self.reranker = embedder, reranker
        self.with_header, self.with_note = VARIANTS[variant]
        self.fts = FTS[variant]

    # ---------- rows and vectors ----------

    def row(self, i: int) -> Row:
        if i not in self._rows:
            self._rows.update({r.id: r for r in rows(self.con, [i])})
        return self._rows[i]

    def fetch(self, ids: Sequence[int]) -> list[Row]:
        missing = [i for i in ids if i not in self._rows]
        if missing:
            self._rows.update({r.id: r for r in rows(self.con, missing)})
        return [self._rows[i] for i in ids]

    @property
    def vectors(self) -> np.ndarray:
        if self._vectors is None:
            self._vectors = load_vectors(self.size, self.variant, self.root).astype(np.float32)
        return self._vectors

    def warm(self) -> None:
        _ = self.vectors
        self.embedder.query("warm up")
        if self.reranker is not None:
            self.reranker.scores("warm up", ["warm up"])

    # ---------- filters ----------

    def _sql_ids(self, f: Filters) -> np.ndarray | None:
        """Chunk ids passing the speaker, party and topic filters, or None when none is set."""
        if not f.needs_sql():
            return None
        ids = None
        if f.speaker or f.party:
            # An interjection ("Ya.") does not make a chunk the speaker's.
            sql, args = "SELECT DISTINCT chunk FROM speakers WHERE tokens >= ?", [MIN_SPEAKER_TOKENS]
            if f.speaker:
                sql += " AND name LIKE ?"
                args.append(f"%{f.speaker}%")
            if f.party:
                sql += " AND party = ?"
                args.append(f.party.upper())
            ids = {r[0] for r in self.con.execute(sql, args)}
        if f.topic:
            t = {r[0] for r in self.con.execute("SELECT chunk FROM topics WHERE topic = ?", (f.topic,))}
            ids = t if ids is None else ids & t
        return np.fromiter(ids or (), dtype=np.int64)

    def mask(self, f: Filters) -> np.ndarray:
        keep = np.ones(len(self.is_law), dtype=bool)
        if f.kind:
            keep &= self.is_law == (f.kind == "law")
        if f.act:
            keep &= self.act == f.act
        if f.lang:
            keep &= (self.lang == f.lang) | ~self.is_law
        if f.date_from or f.date_to:
            in_range = np.ones(len(keep), dtype=bool)
            if f.date_from:
                in_range &= self.date >= int(f.date_from.replace("-", ""))
            if f.date_to:
                in_range &= self.date <= int(f.date_to.replace("-", ""))
            # A date range picks sittings; it reads as a reprint date only when the search is law only.
            keep &= in_range if f.kind == "law" else in_range & ~self.is_law
        if f.parliament:
            keep &= self.parl == f.parliament
        if f.chamber:
            keep &= self.chamber == f.chamber
        ids = self._sql_ids(f)
        if ids is not None:
            only = np.zeros(len(keep), dtype=bool)
            only[ids[ids < len(keep)]] = True
            keep &= only
        return keep

    # ---------- stages ----------

    def bm25(self, question: str, f: Filters, k: int = config.CANDIDATES, keep: np.ndarray | None = None) -> list[Hit]:
        query = keyword_query(question)
        if not query:
            return []
        keep = self.mask(f) if keep is None else keep
        # Rank over the whole index, then filter: FTS5's own ranking ignores joined conditions,
        # and a narrow filter is served by a deeper read.
        depth = k if keep.all() else max(k * 20, 2000)
        cur = self.con.execute(f"SELECT rowid, bm25({self.fts}) FROM {self.fts} WHERE {self.fts} MATCH ? "
                               f"ORDER BY bm25({self.fts}) LIMIT ?", (query, depth))
        hits = [Hit(r[0], -r[1]) for r in cur if r[0] < len(keep) and keep[r[0]]]
        return hits[:k]

    def dense(self, question: str, f: Filters, k: int = config.CANDIDATES, keep: np.ndarray | None = None) -> list[Hit]:
        keep = self.mask(f) if keep is None else keep
        q = self.embedder.query(question, config.QUERY_TASK)
        vec = self.vectors
        scores = vec @ q
        scores[~keep[:len(scores)]] = -np.inf
        k = min(k, int(np.isfinite(scores).sum()))
        if k <= 0:
            return []
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top], kind="stable")]
        return [Hit(int(i), float(scores[i])) for i in top]

    def rerank(self, question: str, hits: Sequence[Hit], pool: int = config.RERANK_POOL) -> list[Hit]:
        pool_hits = list(hits[:pool])
        texts = [r.indexed_text(self.with_header, self.with_note) for r in self.fetch([h.id for h in pool_hits])]
        scores = self.reranker.scores(question, texts)
        return [Hit(h.id, s) for h, s in sorted(zip(pool_hits, scores), key=lambda p: -p[1])]

    def _passage(self, run: list[Row], score: float, via: str = "") -> Passage:
        text = run[0].text
        for r in run[1:]:
            text = merge_texts(text, r.text)
        f = run[0]
        return Passage([r.id for r in run], score, f.kind, f.key, f.header, text, f.act, f.lang, f.section,
                       f.chamber, f.date, f.unit, via)

    def expand(self, hits: Sequence[Hit], top_k: int = config.TOP_K, window: int = 1,
               xrefs: int = config.XREFS) -> list[Passage]:
        """Merge each top hit with its neighbours in the same section or extract; then add the
        sections the law passages name."""
        by_key: dict[str, dict[int, float]] = {}
        order: list[str] = []
        for h in hits[:top_k]:
            r = self.row(h.id)
            if r.key not in by_key:
                by_key[r.key] = {}
                order.append(r.key)
            for p in range(r.piece - window, r.piece + window + 1):
                prev = by_key[r.key].get(p, float("-inf"))
                by_key[r.key][p] = max(prev, h.score if p == r.piece else prev)
        passages: list[Passage] = []
        for key in order:
            pieces = {r[1]: r[0] for r in self.con.execute("SELECT id, piece FROM chunks WHERE key = ?", (key,))}
            runs: list[list[int]] = []
            for p in sorted(p for p in by_key[key] if p in pieces):
                if runs and p == runs[-1][-1] + 1:
                    runs[-1].append(p)
                else:
                    runs.append([p])
            for run in runs:
                score = max(by_key[key][p] for p in run)
                if score != float("-inf"):
                    passages.append(self._passage(self.fetch([pieces[p] for p in run]), score))
        passages.sort(key=lambda p: -p.score)
        if xrefs:
            passages += self.cross_references(passages, xrefs)
        return passages

    def cross_references(self, passages: Sequence[Passage], limit: int = config.XREFS) -> list[Passage]:
        """The sections the law passages name, whole, that are not passages already."""
        have = {p.key for p in passages}
        out: list[Passage] = []
        for p in passages:
            if p.kind != "law":
                continue
            for (to,) in self.con.execute("SELECT to_section FROM xrefs WHERE act = ? AND lang = ? AND section = ?",
                                          (p.act, p.lang, p.section)):
                key = f"law:{p.act}:{p.lang}:{to}"
                if key in have or len(out) >= limit:
                    continue
                ids = [r[0] for r in self.con.execute("SELECT id FROM chunks WHERE key = ? ORDER BY piece", (key,))]
                if ids:
                    out.append(self._passage(self.fetch(ids), p.score, f"cross-reference from section {p.section}"))
                    have.add(key)
        return out

    def debates_for_act(self, act: str) -> list[dict]:
        """The bill debates linked to an Act: one row per sitting extract, oldest first."""
        return [dict(r) for r in self.con.execute(
            "SELECT unit, chamber, date, MIN(header) AS header FROM chunks WHERE kind = 'debate' AND act = ? "
            "GROUP BY unit ORDER BY date, unit", (act,))]

    def search(self, question: str, f: Filters | None = None, mode: str = "full", top_k: int = config.TOP_K,
               candidates: int = config.CANDIDATES, xrefs: int = config.XREFS,
               pool: int = config.RERANK_POOL) -> Trace:
        f = f or Filters()
        trace = Trace(question, f, mode)
        keep = self.mask(f)

        def timed(name, fn, *args):
            t = time.perf_counter()
            hits = fn(*args)
            trace.stages.append(Stage(name, hits, (time.perf_counter() - t) * 1000))
            return hits

        lists = []
        if mode in ("bm25", "hybrid", "full"):
            lists.append(timed("bm25", self.bm25, question, f, candidates, keep))
        if mode in ("dense", "hybrid", "full"):
            lists.append(timed("dense", self.dense, question, f, candidates, keep))
        if mode in ("hybrid", "full"):
            fused = timed("fused", rrf, lists)
            if mode == "full" and self.reranker is not None:
                timed("reranked", self.rerank, question, fused, pool)
        trace.passages = self.expand(trace.stages[-1].hits, top_k, xrefs=xrefs) if trace.stages else []
        return trace


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("question")
    for name in ("kind", "act", "lang", "date-from", "date-to", "chamber", "speaker", "party", "topic"):
        ap.add_argument(f"--{name}")
    ap.add_argument("--parliament", type=int)
    ap.add_argument("--mode", default="full", choices=MODES)
    ap.add_argument("--variant", default=config.VARIANT, choices=list(VARIANTS))
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()
    f = Filters(a.kind, a.act, a.lang, a.date_from, a.date_to, a.parliament, a.chamber, a.speaker, a.party, a.topic)
    s = Searcher(variant=a.variant)
    t = s.search(a.question, f, a.mode)
    if a.trace:
        for st in t.stages:
            print(f"{st.name:9} {st.ms:8.1f} ms  top: {[h.id for h in st.hits[:8]]}")
    for p in t.passages:
        print(f"\n[{p.score:.3f}] {p.cite}{' - ' + p.via if p.via else ''}\n{p.header}\n{p.text[:600]}")


if __name__ == "__main__":
    main()
