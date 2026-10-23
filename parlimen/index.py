"""The search index on disk, in data/index/.

`index.db` (SQLite):
- `chunks`: one row per chunk; id = row number in the vector matrix. Law chunks come first, then
  the debates in sitting order; `append` adds new sittings' chunks after them, so ids never move.
- `speakers` (chunk id, name, seat, party, role, tokens) and `topics` (chunk id, topic): the
  debate filters.
- `xrefs` (act, lang, section, to_section): the sections each Act section names.
- `fts_h`, `fts_hn`: FTS5 indexes ranked with BM25, one per variant (header + text; header +
  note + text). Each holds only its own columns: in novel-rag a column weighted 0 still moved
  BM25's statistics.
- `meta`: build facts.

`vectors-<size>-<variant>/part-NNNN.npy`: float16 unit vectors in id order, one file per embedding
run, so an embed that stops resumes at the next id and a new sitting appends a part.

A rebuild after a parser or chunk fix keeps the vector of every chunk whose indexed text is
unchanged, so only the changed chunks go to the GPU.

Run:  python -m parlimen.index build                 chunk everything into a fresh index.db
      python -m parlimen.index embed [--variant h hn]  embed the rows with no vector yet
      python -m parlimen.index rebuild [--variant h hn]  build afresh, keep unchanged vectors
      python -m parlimen.index stats
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from . import config, links
from .chunk import Chunk

SCHEMA = """
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL, piece INTEGER NOT NULL,
    act TEXT NOT NULL, lang TEXT NOT NULL, section TEXT NOT NULL, chamber TEXT NOT NULL,
    date TEXT NOT NULL, parliament INTEGER NOT NULL, unit TEXT NOT NULL,
    seq_first INTEGER NOT NULL, seq_last INTEGER NOT NULL, page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL, tokens INTEGER NOT NULL,
    header TEXT NOT NULL, note TEXT NOT NULL, text TEXT NOT NULL
);
CREATE INDEX chunks_key ON chunks (key, piece);
CREATE INDEX chunks_act ON chunks (act, kind);
CREATE INDEX chunks_date ON chunks (date);
CREATE TABLE speakers (chunk INTEGER NOT NULL, name TEXT NOT NULL, seat TEXT NOT NULL, party TEXT NOT NULL,
                       role TEXT NOT NULL, tokens INTEGER NOT NULL);
CREATE INDEX speakers_chunk ON speakers (chunk);
CREATE TABLE topics (chunk INTEGER NOT NULL, topic TEXT NOT NULL);
CREATE INDEX topics_chunk ON topics (chunk);
CREATE TABLE xrefs (act TEXT NOT NULL, lang TEXT NOT NULL, section TEXT NOT NULL, to_section TEXT NOT NULL);
CREATE INDEX xrefs_from ON xrefs (act, lang, section);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE fts_h USING fts5(header, text, content='chunks', content_rowid='id',
                                      tokenize='porter unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE fts_hn USING fts5(header, note, text, content='chunks', content_rowid='id',
                                       tokenize='porter unicode61 remove_diacritics 2');
"""

VARIANTS = {"h": (True, False), "hn": (True, True)}
FTS = {"h": "fts_h", "hn": "fts_hn"}
COLS = ("id, kind, key, piece, act, lang, section, chamber, date, parliament, unit, seq_first, seq_last, "
        "page_start, page_end, tokens, header, note, text")


def db_path(root: Path = config.INDEX) -> Path:
    return root / "index.db"


def vectors_dir(size: str, variant: str, root: Path = config.INDEX) -> Path:
    return root / f"vectors-{size}-{variant}"


def connect(path: Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(path or db_path())
    con.row_factory = sqlite3.Row
    return con


def _insert(con: sqlite3.Connection, start: int, chunks: Iterable[Chunk], xref_seen: set) -> int:
    """Insert chunks with ids from `start`, their speakers, topics and a law section's
    cross-references; returns the next free id."""
    i = start
    for c in chunks:
        con.execute(f"INSERT INTO chunks ({COLS}) VALUES ({','.join('?' * 19)})",
                    (i, c.kind, c.key, c.piece, c.act, c.lang, c.section, c.chamber, c.date, c.parliament,
                     c.unit, c.seq_first, c.seq_last, c.page_start, c.page_end, c.tokens, c.header, c.note, c.text))
        con.executemany("INSERT INTO speakers VALUES (?,?,?,?,?,?)",
                        [(i, s["name"], s["seat"], s["party"], s["role"], s["tokens"]) for s in c.speakers])
        con.executemany("INSERT INTO topics VALUES (?,?)", [(i, t) for t in c.topics])
        if c.kind == "law":
            key = (c.act, c.lang, c.section)
            refs = links.xrefs(c.text, c.section)
            new = [r for r in refs if (*key, r) not in xref_seen]
            xref_seen.update((*key, r) for r in new)
            con.executemany("INSERT INTO xrefs VALUES (?,?,?,?)", [(*key, r) for r in new])
        for v in FTS.values():
            cols = "header, note, text" if v == "fts_hn" else "header, text"
            vals = (c.header, c.note, c.text) if v == "fts_hn" else (c.header, c.text)
            con.execute(f"INSERT INTO {v}(rowid, {cols}) VALUES (?, {','.join('?' * len(vals))})", (i, *vals))
        i += 1
        if i % 20000 == 0:
            con.commit()
            print(f"{i} chunks", flush=True)
    con.commit()
    return i


def build(chunks: Iterable[Chunk], path: Path | None = None) -> int:
    """Write a fresh index.db from the chunks; returns the chunk count."""
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    n = _insert(con, 0, chunks, set())
    _xref_clean(con)
    meta = {"chunk_tokens": config.CHUNK_TOKENS, "overlap_tokens": config.OVERLAP_TOKENS, "chunks": n,
            "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in meta.items()])
    con.commit()
    con.close()
    tmp.replace(path)
    return n


def _xref_clean(con: sqlite3.Connection) -> None:
    """Keep only cross-references to sections the Act has."""
    con.execute("DELETE FROM xrefs WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.kind = 'law' "
                "AND c.act = xrefs.act AND c.lang = xrefs.lang AND c.section = xrefs.to_section)")
    con.commit()


def append(chunks: Iterable[Chunk], path: Path | None = None) -> tuple[int, int]:
    """Add chunks after the last id (a new sitting); returns the first new id and the next free id."""
    con = connect(path)
    start = con.execute("SELECT COALESCE(MAX(id) + 1, 0) FROM chunks").fetchone()[0]
    end = _insert(con, start, chunks, set())
    con.execute("UPDATE meta SET value = ? WHERE key = 'chunks'", (json.dumps(end),))
    con.commit()
    con.close()
    return start, end


@dataclass
class Row:
    id: int
    kind: str
    key: str
    piece: int
    act: str
    lang: str
    section: str
    chamber: str
    date: str
    parliament: int
    unit: str
    seq_first: int
    seq_last: int
    page_start: int
    page_end: int
    tokens: int
    header: str
    note: str
    text: str

    def indexed_text(self, with_header: bool = True, with_note: bool = True) -> str:
        parts = [self.header] if with_header else []
        if with_note and self.note:
            parts.append(self.note)
        parts.append(self.text)
        return "\n".join(parts)


def rows(con: sqlite3.Connection, ids: Iterable[int] | None = None, start: int = 0, limit: int = -1) -> list[Row]:
    if ids is None:
        return [Row(*r) for r in con.execute(f"SELECT {COLS} FROM chunks WHERE id >= ? ORDER BY id LIMIT ?",
                                             (start, limit))]
    ids = list(ids)
    found: dict[int, Row] = {}
    for k in range(0, len(ids), 900):
        part = ids[k:k + 900]
        found.update({r[0]: Row(*r) for r in con.execute(
            f"SELECT {COLS} FROM chunks WHERE id IN ({','.join('?' * len(part))})", part)})
    return [found[i] for i in ids if i in found]


# ---------- vectors ----------

def load_vectors(size: str, variant: str, root: Path = config.INDEX) -> np.ndarray:
    parts = sorted(vectors_dir(size, variant, root).glob("part-*.npy"))
    if not parts:
        raise FileNotFoundError(f"no vectors in {vectors_dir(size, variant, root)}: run python -m parlimen.index embed")
    return np.concatenate([np.load(p) for p in parts])


def vector_count(size: str, variant: str, root: Path = config.INDEX) -> int:
    return sum(np.load(p, mmap_mode="r").shape[0] for p in vectors_dir(size, variant, root).glob("part-*.npy"))


def _write_part(vectors: np.ndarray, size: str, variant: str, root: Path) -> None:
    d = vectors_dir(size, variant, root)
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("part-*.npy")))
    tmp = d / f"part-{n:04d}.tmp.npy"
    np.save(tmp, vectors.astype(np.float16))
    tmp.replace(d / f"part-{n:04d}.npy")


def _digest(text: str) -> bytes:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).digest()


def _prev_ids(size: str, variant: str, prev: Path) -> dict[bytes, int]:
    """The id of each row of a previous build that has a vector, by its indexed text."""
    if not db_path(prev).exists() or not vectors_dir(size, variant, prev).exists():
        return {}
    con = connect(db_path(prev))
    n = vector_count(size, variant, prev)
    out: dict[bytes, int] = {}
    for start in range(0, n, 20000):
        for r in rows(con, start=start, limit=min(20000, n - start)):
            out[_digest(r.indexed_text(*VARIANTS[variant]))] = r.id
    con.close()
    return out


def embed(size: str = config.EMBEDDER, variant: str = config.VARIANT, root: Path = config.INDEX,
          block: int = 20000, embedder=None, batch_size: int = 32, prev: Path | None = None) -> int:
    """Give every chunk with no vector yet a vector, `block` rows per part file. A row whose text
    is the same in the previous build at `prev` keeps that build's vector. For "hn", a row with no
    note reads the same as in "h", so its "h" vector is copied when one exists. Returns the rows
    given a vector."""
    con = connect(db_path(root))
    total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    done = vector_count(size, variant, root) if vectors_dir(size, variant, root).exists() else 0
    h_vecs = None
    if variant == "hn" and vectors_dir(size, "h", root).exists():
        h_vecs = load_vectors(size, "h", root)
    prev_ids = _prev_ids(size, variant, prev) if prev else {}
    prev_vecs = load_vectors(size, variant, prev) if prev_ids else None
    if embedder is None:
        from .models import Embedder
        embedder = Embedder(size)
    with_header, with_note = VARIANTS[variant]
    t0 = time.time()
    for start in range(done, total, block):
        part = rows(con, start=start, limit=block)
        texts = [r.indexed_text(with_header, with_note) for r in part]
        kept = {k: prev_ids[d] for k, t in enumerate(texts) if (d := _digest(t)) in prev_ids}
        copy = [k for k, r in enumerate(part)
                if k not in kept and h_vecs is not None and not r.note and r.id < len(h_vecs)]
        need = sorted(set(range(len(part))) - set(kept) - set(copy))
        vecs = embedder.documents([texts[k] for k in need], batch_size=batch_size) if need else None
        dim = next(v.shape[1] for v in (vecs, prev_vecs, h_vecs) if v is not None)
        out = np.zeros((len(part), dim), dtype=np.float32)
        if need:
            out[need] = vecs
        if kept:
            out[list(kept)] = prev_vecs[list(kept.values())]
        if copy:
            out[copy] = h_vecs[[part[k].id for k in copy]]
        _write_part(out, size, variant, root)
        print(f"{start + len(part)}/{total} rows given a vector ({len(need)} embedded, {len(kept)} kept, "
              f"{time.time() - t0:.0f} s)", flush=True)
    con.close()
    return total - done


def rebuild(chunks: Iterable[Chunk], size: str = config.EMBEDDER, variants: Iterable[str] = ("h", "hn"),
            root: Path = config.INDEX, embedder=None, block: int = 20000) -> int:
    """Build a fresh index.db and give it vectors, embedding only the chunks whose text changed.
    The old build waits in `root/prev` until every variant it had is done, so a stopped rebuild
    resumes. Returns the rows embedded or kept."""
    prev = root / "prev"
    if not prev.exists():
        prev.mkdir(parents=True)
        if db_path(root).exists():
            db_path(root).replace(db_path(prev))
        for d in root.glob(f"vectors-{size}-*"):
            d.replace(prev / d.name)
    if not db_path(root).exists():
        build(chunks, db_path(root))
    had = {d.name.removeprefix(f"vectors-{size}-") for d in prev.glob(f"vectors-{size}-*")}
    order = [v for v in VARIANTS if v in set(variants) | had]  # "h" first, so "hn" can copy from it
    n = sum(embed(size, v, root, block=block, embedder=embedder, prev=prev) for v in order)
    shutil.rmtree(prev)
    return n


def stats(con: sqlite3.Connection) -> str:
    kinds = dict(con.execute("SELECT kind, COUNT(*) FROM chunks GROUP BY kind").fetchall())
    tok = con.execute("SELECT AVG(tokens), MAX(tokens) FROM chunks").fetchone()
    xr = con.execute("SELECT COUNT(*) FROM xrefs").fetchone()[0]
    linked = con.execute("SELECT COUNT(DISTINCT unit) FROM chunks WHERE kind = 'debate' AND act != ''").fetchone()[0]
    return (f"chunks {kinds}; tokens mean {tok[0]:.0f}, max {tok[1]}; {xr} cross-references; "
            f"{linked} debate extracts linked to an Act")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    for name in ("embed", "rebuild"):
        p = sub.add_parser(name)
        p.add_argument("--size", default=config.EMBEDDER, choices=list(config.EMBEDDERS))
        p.add_argument("--variant", nargs="+", default=[config.VARIANT], choices=list(VARIANTS),
                       help="several run in order; put h before hn so hn copies its rows with no note")
        p.add_argument("--batch-size", type=int, default=32)
    sub.add_parser("stats")
    args = ap.parse_args()
    if args.cmd == "build":
        from .chunk import all_chunks, qwen_counter
        t = time.time()
        n = build(all_chunks(qwen_counter()))
        print(f"{n} chunks in {time.time() - t:.0f} s")
        print(stats(connect()))
    elif args.cmd == "embed":
        from .models import Embedder
        embedder = Embedder(args.size)
        for variant in args.variant:
            print(f"{variant}: {embed(args.size, variant, embedder=embedder, batch_size=args.batch_size)} rows embedded")
    elif args.cmd == "rebuild":
        from .chunk import all_chunks, qwen_counter
        from .models import Embedder
        n = rebuild(all_chunks(qwen_counter()), args.size, args.variant, embedder=Embedder(args.size))
        print(f"{n} rows given a vector")
        print(stats(connect()))
    else:
        print(stats(connect()))


if __name__ == "__main__":
    main()
