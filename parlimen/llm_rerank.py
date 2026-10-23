"""Haiku 5.5 as a listwise reranker through the Messages API, in place of the local Qwen3 reranker.

The local reranker needs about 29 s per question on a 2-thread CPU container (pool 20), against a
3 s target. Here one Messages call reads the question and the numbered pool of passages and returns
the passage numbers, most relevant first, as structured output. Thinking is off and effort is low,
for speed. `scores` turns the order into descending scores, so `Searcher.rerank` sorts by it
unchanged. Numbers the model leaves out or repeats keep their fused order below the ranked ones;
a failed call (API error, refusal, cut-off answer) keeps the fused order whole and is counted in
`failures`. Every call logs its usage.
"""

import json
import time
from typing import Sequence

import anthropic

from . import enrich

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 1024

SYSTEM = """You rank search results for a search engine over Malaysia's Acts of Parliament and the Dewan Rakyat Hansard.
You get a question, in Malay or English, and numbered passages: Act sections (English or Malay text) and extracts of sitting records (speeches, mostly in Malay).
Rank the passages by how well each one answers the question, the best first. A passage in the other language that answers the question ranks as high as one in the question's language. When the question names an Act, a section, a date, a Parliament or a person, passages that match it rank above passages on the same topic that do not.
Return every passage number exactly once."""

SCHEMA = {
    "type": "object",
    "properties": {"ranking": {"type": "array", "items": {"type": "integer"}}},
    "required": ["ranking"],
    "additionalProperties": False,
}


def order(ranking: Sequence, n: int) -> list[int]:
    """0-based passage order from the model's 1-based ranking: valid numbers once each, in the
    model's order, then the numbers it left out, in their fused order."""
    seen: list[int] = []
    for r in ranking:
        if isinstance(r, int) and not isinstance(r, bool) and 1 <= r <= n and r - 1 not in seen:
            seen.append(r - 1)
    return seen + [i for i in range(n) if i not in seen]


def prompt(question: str, passages: Sequence[str]) -> str:
    body = "\n\n".join(f"[{i}]\n{p}" for i, p in enumerate(passages, start=1))
    return f"Question: {question}\n\nPassages:\n\n{body}\n\nRank all {len(passages)} passages."


class HaikuReranker:
    """Same `scores` interface as `models.Reranker`."""

    def __init__(self, client=None, job: str = "rerank"):
        self.client, self.job = client, job
        self.calls = self.failures = 0
        self.usd = 0.0
        self.last_ms = 0.0

    def scores(self, question: str, passages: Sequence[str]) -> list[float]:
        n = len(passages)
        if n <= 1:
            return [0.0] * n  # nothing to order, so no call
        self.client = self.client or enrich._client()
        t = time.perf_counter()
        self.calls += 1
        idx = list(range(n))
        try:
            msg = self.client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM, thinking={"type": "disabled"},
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": prompt(question, passages)}])
            self.usd += enrich._log(self.job, MODEL, "messages", msg.usage)
            text = next((b.text for b in msg.content if b.type == "text"), "")
            if msg.stop_reason != "end_turn":
                raise ValueError(f"stop_reason {msg.stop_reason}")
            idx = order(json.loads(text)["ranking"], n)
        except (anthropic.APIError, ValueError, KeyError, TypeError) as e:  # the fused order stands
            self.failures += 1
            print(f"  rerank failed ({type(e).__name__}: {e}); fused order kept", flush=True)
        self.last_ms = (time.perf_counter() - t) * 1000
        out = [0.0] * n
        for rank, i in enumerate(idx):
            out[i] = float(n - rank)
        return out
