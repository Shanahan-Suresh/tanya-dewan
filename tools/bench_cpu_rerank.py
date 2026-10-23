"""Time the reranker and the query embedding on the CPU, in bfloat16 and float32, with torch held
to a few threads like the demo's container. It decides the number format of the CPU path.

Run:  python tools/bench_cpu_rerank.py [--threads 2] [--passages 10]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402

from parlimen import index, models  # noqa: E402

QUESTION = "Berapakah peruntukan untuk membaiki bangunan sekolah daif dalam Belanjawan 2025?"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--passages", type=int, default=10)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    con = index.connect()
    texts = [r.indexed_text(True, False) for r in index.rows(con, start=200000, limit=a.passages)]
    for name, dtype in (("bfloat16", torch.bfloat16), ("float32", torch.float32)):
        models._model_kwargs = lambda device, dt=dtype: {"dtype": dt}
        rr = models.Reranker("0.6b", device="cpu")
        rr.scores(QUESTION, texts[:1])  # load and warm
        t = time.perf_counter()
        rr.scores(QUESTION, texts)
        rerank_s = time.perf_counter() - t
        rr.unload()
        em = models.Embedder("0.6b", device="cpu")
        em.query(QUESTION)
        t = time.perf_counter()
        em.query(QUESTION)
        embed_s = time.perf_counter() - t
        print(f"{name}: rerank {a.passages} passages {rerank_s:.1f} s ({rerank_s / a.passages * 1000:.0f} ms each); "
              f"query embedding {embed_s * 1000:.0f} ms; {a.threads} threads", flush=True)


if __name__ == "__main__":
    main()
