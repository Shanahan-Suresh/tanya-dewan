"""The answer step: Haiku 5.5, at effort high, answers from the retrieved passages, with citations.

Each passage goes in as a plain-text `document` block with citations switched on, titled with its
citation (Act, section, language and reprint date, or chamber, sitting date and extract). The
API splits the answer into text blocks, and every block that rests on a passage carries the exact
sentences it quotes, so a citation never points at text that is not there; a debate quote is
prefixed with the label of the speech it sits in (`speaker_at`). A sentence that no citation
reaches is dropped (`keep_cited`), so the answer shows only claims a reader can check. Every answer ends
with the not-legal-advice line, and the system prompt refuses advice on a reader's own case.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Sequence

from . import enrich
from .search import Passage

MODEL = "claude-haiku-5-5"
# Chosen by the phase 5 answer judging: high met both answer targets (77% correct, 82% backed)
# where Haiku's default, medium, gave 72% and 78%, for about 2.7 s more an answer.
EFFORT = "high"
NOT_ADVICE = "This is general information from the published record, not legal advice."
NOT_ADVICE_MS = "Ini maklumat umum daripada rekod yang diterbitkan, bukan nasihat undang-undang."

SYSTEM = """You answer questions about Malaysia's Acts of Parliament and the Dewan Rakyat Hansard, using only the documents provided.
Each document is an Act section (with its reprint date) or an extract of a sitting's record (with its date). Speeches are verbatim, mostly in Malay; a "Summary (AI)" line was written by a model and is less reliable than the speech text.
- Base every claim on the documents and cite them. If they do not answer the question, say so plainly and do not answer from memory.
- Say who said what in a debate, and when; never present an MP's claim as fact.
- Name the Act and section a legal point comes from, and its reprint date if the law may have changed since.
- Answer only what the question asks. Do not add other Acts, amendments, repeals or provisions the question does not ask about.
- Write only claims a cited sentence states. Leave out what the documents only suggest, and do not describe what the documents lack unless they do not answer the question.
- Do not advise on the reader's own case or tell them what to do; for that, say they should consult a lawyer.
- Answer in the language of the question. Keep answers short: two to five sentences, or a short list for a question with several parts."""

# A debate paragraph opens with its speaker label: "Name [Seat]: " or "Name [Seat] (continued): ".
LABEL = re.compile(r"([^\n:]{2,160}?)(?: \(continued[^)]*\))?: ")


@dataclass
class Source:
    n: int
    cite: str
    quotes: list[str] = field(default_factory=list)
    context: str = ""  # the passage header the model also read: agenda item, speakers and parties
    index: int = -1    # the passage's place in the list the answer read


@dataclass
class Answer:
    text: str
    sources: list[Source]
    stop_reason: str
    usd: float
    dropped: list[str] = field(default_factory=list)  # uncited sentences taken out of the text

    def render(self) -> str:
        return "\n".join([self.text, "", *(f"[{s.n}] {s.cite}" for s in self.sources)])


def documents(passages: Sequence[Passage]) -> list[dict]:
    return [{"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": p.text},
             "title": p.cite, "context": p.header + (f" ({p.via})" if p.via else ""),
             "citations": {"enabled": True}} for p in passages]


def speaker_at(text: str, at: int | None) -> str:
    """The speaker label of the debate paragraph holding character `at`, or ""."""
    if at is None or not 0 <= at < len(text):
        return ""
    start = text.rfind("\n\n", 0, at + 1)
    m = LABEL.match(text, 0 if start == -1 else start + 2)
    return m.group(1).strip() if m else ""


# A sentence ends at . ! ? or … (with any closing quote, bracket or bold mark) and the space after
# it, when the next word starts a sentence; or at a line break.
SENTENCE_GAP = re.compile(r"(?<=[.!?…])[\"'”’)\]*]*[ \t]+|\n+")
# The system prompt's referral for a reader's own case is not a claim, so it stays uncited.
LAWYER = re.compile(r"\b(lawyer|legal advice|peguam|nasihat undang-undang)", re.I)
ABBREVIATIONS = frozenset("s ss no dr mr mrs ms prof bhd sdn para paras subs cf vs st jr hj tn yb yab ym "
                          "e.g i.e art arts sek".split())


def sentence_cuts(text: str) -> list[int]:
    cuts = [0]
    for m in SENTENCE_GAP.finditer(text):
        if "\n" not in m.group():
            before = (text[:m.start()].rsplit(None, 1) or [""])[-1].strip("\"'”’)]*").rstrip(".").lower()
            after = text[m.end():m.end() + 1]
            if before in ABBREVIATIONS or len(before) == 1 or not after or not (after.isupper() or after in "*\"'“‘(["):
                continue
        cuts.append(m.end())
    return cuts + [len(text)]


def keep_cited(pieces: Sequence[tuple[str, list[int]]]) -> tuple[str, list[str]]:
    """Join the answer's text blocks, with [n] markers after the cited ones, and drop every
    sentence that no cited block reaches: those claims rest on nothing the reader can check (the
    model's memory, or a sentence it did not quote). A lead-in ending in ":", text with no
    letters and the referral to a lawyer stay. An answer with no citation at all (the documents do not answer) stays whole.
    Returns the text and the dropped sentences."""
    full, spans, marks_at = "", [], []
    for text, marks in pieces:
        start = len(full)
        full += text
        if marks:
            spans.append((start, len(full)))
            marks_at.append((len(full), "".join(f"[{n}]" for n in sorted(marks))))
    if not spans:
        return full.strip(), []
    cuts = sentence_cuts(full)
    out, dropped = [], []
    for a, b in zip(cuts, cuts[1:]):
        if a == b:
            continue
        seg = full[a:b]
        for at, mark in reversed([(at, mark) for at, mark in marks_at if a < at <= b]):
            seg = seg[:at - a] + mark + seg[at - a:]
        cited = any(s < b and e > a for s, e in spans)
        if (cited or not re.search(r"[^\W\d_]", seg) or seg.rstrip().rstrip("*").endswith(":")
                or LAWYER.search(seg)):
            out.append(seg)
        else:
            dropped.append(seg.strip())
    text = re.sub(r"\n{3,}", "\n\n", re.sub(r"(?m)^[ \t]*[-*][ \t]*$\n?", "", "".join(out)))
    return text.strip(), dropped


def parse(message, passages: Sequence[Passage]) -> tuple[str, list[Source], list[str]]:
    """Answer text with [n] markers, numbered in order of first citation, with uncited sentences
    dropped (`keep_cited`). A quote from a debate carries its speaker's label, so a reader (and
    the judge) sees who said it."""
    numbers: dict[int, Source] = {}
    pieces: list[tuple[str, list[int]]] = []
    for block in message.content:
        if block.type != "text":
            continue
        marks: list[int] = []
        pieces.append((block.text, marks))
        for c in getattr(block, "citations", None) or []:
            i = getattr(c, "document_index", None)
            if i is None or i >= len(passages):
                continue
            if i not in numbers:
                numbers[i] = Source(len(numbers) + 1, passages[i].cite, context=passages[i].header, index=i)
            quote = " ".join((getattr(c, "cited_text", "") or "").split())
            who = speaker_at(passages[i].text, getattr(c, "start_char_index", None)) if passages[i].kind == "debate" else ""
            if quote and who and not quote.startswith(who):
                quote = f"{who}: {quote}"
            if quote and quote not in numbers[i].quotes:
                numbers[i].quotes.append(quote)
            if numbers[i].n not in marks:
                marks.append(numbers[i].n)
    text, dropped = keep_cited(pieces)
    return text, sorted(numbers.values(), key=lambda s: s.n), dropped


def _streamed(client, request: dict, passages: Sequence[Passage], on_text: Callable[[str], None]):
    """Run the request as a stream and report the cited answer so far after each finished text block."""
    blocks, shown = [], ""
    with client.messages.stream(**request) as stream:
        for event in stream:
            if event.type == "content_block_stop" and getattr(event.content_block, "type", "") == "text":
                blocks.append(event.content_block)
                text = parse(SimpleNamespace(content=blocks), passages)[0]
                if text and text != shown:
                    shown = text
                    on_text(text)
        return stream.get_final_message()


def ask(question: str, passages: Sequence[Passage], lang: str = "en", client=None, job: str = "answer",
        effort: str | None = EFFORT, on_text: Callable[[str], None] | None = None) -> Answer:
    """`effort` sets Haiku's output_config effort (None leaves Haiku's own default, medium);
    thinking counts toward max_tokens, hence the 16,000 cap.

    With `on_text` the answer streams: after each finished text block, `on_text` gets the answer so
    far, already passed through `parse` (cited sentences only, with [n] marks). The returned Answer
    is the same as without streaming."""
    line = NOT_ADVICE_MS if lang == "ms" else NOT_ADVICE
    if not passages:
        return Answer(f"No passage matched the question, so there is nothing to answer from.\n\n{line}", [], "empty", 0.0)
    client = client or enrich._client()
    extra = {"output_config": {"effort": effort}} if effort else {}
    request = dict(model=MODEL, max_tokens=16000, system=SYSTEM, **extra,
                   messages=[{"role": "user", "content": documents(passages) + [{"type": "text", "text": question}]}])
    if on_text is None:
        message = client.messages.create(**request)
    else:
        message = _streamed(client, request, passages, on_text)
    usd = enrich._log(job, MODEL, "messages", message.usage)
    if message.stop_reason == "refusal":
        return Answer(f"Claude declined to answer from these passages.\n\n{line}", [], "refusal", usd)
    text, sources, dropped = parse(message, passages)
    return Answer(f"{text}\n\n{line}", sources, message.stop_reason or "", usd, dropped)
