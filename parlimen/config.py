"""Paths, crawl settings and search settings shared by every module.

Importing this module sets HF_HOME before any Hugging Face library loads, so model downloads land
on the D: drive (shared with novel-rag).
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
RAW = DATA / "raw"
ACTS = RAW / "acts"
USAGE_LOG = DATA / "api-usage.jsonl"

# parlimen.gov.my serves its leaf certificate without the Sectigo DV R36 intermediate, so the
# intermediate ships in certs/ and joins certifi's roots instead of turning verification off.
EXTRA_CA = ROOT / "certs" / "sectigo-dv-r36.pem"

USER_AGENT = "tanya-dewan/0.1 (civic research crawler; one request at a time, cached)"
MIN_INTERVAL_S = 1.5  # seconds between two requests to the same host
TIMEOUT_S = 60

# The site's public name, in one place: page titles, the header, share previews, the MCP server.
SITE_NAME = "Tanya Dewan"

PARLIAMENT_SITE = "https://www.parlimen.gov.my"
# Hansard archive per chamber: the Dewan Rakyat itself and its Special Chamber (Dewan Khas,
# file names KKDR-...). Both pages serve the same tree.
HANSARD_TREES = {
    "DR": PARLIAMENT_SITE + "/hansard-dewan-rakyat.html?uweb=dr&lang=bm&arkib=yes",
    "KK": PARLIAMENT_SITE + "/hansard-dewan-khas.html?uweb=dr&lang=bm&arkib=yes",
}
PARLIAMENTS = (14, 15)  # release 1 scope: July 2018 onwards

# Laws of Malaysia portal. Its listing only renders in a browser, so Act texts come through the
# installed Chrome (parlimen/acts.py), one PDF at a time.
LOM_SITE = "https://lom.agc.gov.my"
LOM_UPDATED = LOM_SITE + "/principal.php?type=updated"
ACT_INTERVAL_S = 5.0  # seconds between two Act PDF downloads

# ---------- search (phase 4, novel-rag's pipeline) ----------
os.environ.setdefault("HF_HOME", r"D:\hf-cache")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

INDEX = DATA / "index"
EMBEDDERS = {"0.6b": "Qwen/Qwen3-Embedding-0.6B", "4b": "Qwen/Qwen3-Embedding-4B"}
RERANKERS = {"0.6b": "Qwen/Qwen3-Reranker-0.6B", "4b": "Qwen/Qwen3-Reranker-4B"}
TOKENIZER = EMBEDDERS["0.6b"]  # chunk sizes are counted with it; every Qwen3 size shares it

CHUNK_TOKENS = 400   # target chunk size
OVERLAP_TOKENS = 60  # carried from the end of one chunk into the next inside a section or speech
MIN_TAIL_TOKENS = 80  # a shorter last piece joins the chunk before it

# The setup every front end searches with, chosen by the phase 5 eval: embedder size, what was
# embedded (h: header + text, hn: header + enrichment note + text), reranker. "haiku" reranks
# through the Messages API (parlimen/llm_rerank.py): the local Qwen3 reranker takes about 29 s a
# search on a 2-thread CPU container, against a 3 s target.
EMBEDDER = "0.6b"
VARIANT = "h"
RERANKER = "haiku"
LOCAL_RERANKER = "0.6b"  # the Qwen3 size the eval's local-rerank arms use

CANDIDATES = 100   # hits taken from each of BM25 and the vector search
RRF_K = 60         # Reciprocal Rank Fusion constant
RERANK_POOL = 20   # fused hits the reranker reads
TOP_K = 8          # passages handed to Claude
XREFS = 3          # sections a law passage's cross-references add, at most

QUERY_TASK = ("Given a question about Malaysian law or the Malaysian Parliament, in Malay or English, "
              "retrieve the Act sections or parliamentary debate passages that answer it")
