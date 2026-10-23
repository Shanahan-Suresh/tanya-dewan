"""Cut the law and the debates into chunks of about CHUNK_TOKENS tokens for search.

Law: one Act section in one language is one unit. A long section is cut at sentence ends, and the
next chunk repeats the last sentences of the one before, up to OVERLAP_TOKENS.

Debates: one enrichment extract (one agenda item, a question kept with its answers) is one unit,
and its speeches are packed in order until the next sentence would pass CHUNK_TOKENS. Half of all
speeches are under 61 characters ("Ya.", "Terima kasih"), so a chunk holds a run of speeches, each
paragraph opened by its speaker label; a speech cut across two chunks opens the second with
"<label> (continued):", and only that speech's sentences repeat as overlap. A chunk keeps every
speaker in it, with seat, party on the sitting's date, role and token count, for the filters.

The header names what the chunk is; the note (index variant "hn") is the extract's English
summary and topics from the enrichment. A last piece under MIN_TAIL_TOKENS joins the chunk before
it. Token counts come from a `count` function (the Qwen3 tokenizer in production, a word count in
the tests).
"""

import csv
import json
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Iterator, Sequence

from . import config, links

Counter = Callable[[Sequence[str]], list[int]]
SENTENCE_END = re.compile(r"[.!?…;:]+[\"'”’)\]]*(?=\s)")
CHAMBERS = {"DR": ("Dewan Rakyat", "Dewan Rakyat"), "KK": ("Special Chamber of the Dewan Rakyat", "Dewan Khas")}
MIN_SPEAKER_TOKENS = 20  # a speaker below this in a chunk (an interjection) is not named in the header


@dataclass
class Chunk:
    kind: str                 # "law" or "debate"
    key: str                  # the unit: "law:265:BI:60A" or "debate:DR-2024-03-12-007"
    piece: int                # position of the chunk inside its unit
    header: str
    text: str
    tokens: int
    note: str = ""
    act: str = ""             # law: the Act; debate: the Act a bill debate is linked to
    lang: str = ""            # law: BI or BM
    section: str = ""
    chamber: str = ""
    date: str = ""            # debate: sitting date; law: reprint date
    parliament: int = 0
    unit: str = ""
    seq_first: int = 0        # debate: first and last speech covered (data/speeches.jsonl seq)
    seq_last: int = 0
    page_start: int = 0
    page_end: int = 0
    speakers: list[dict] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def indexed_text(self, with_header: bool = True, with_note: bool = True) -> str:
        """What the embedder, BM25 and the reranker read."""
        parts = [self.header] if with_header else []
        if with_note and self.note:
            parts.append(self.note)
        parts.append(self.text)
        return "\n".join(parts)


@dataclass
class Item:
    text: str
    tokens: int
    owner: int                # the speech (or section) the sentence belongs to
    first: bool               # the owner's first sentence
    label: str = ""


def sentences(text: str) -> list[str]:
    out, cur = [], 0
    for m in SENTENCE_END.finditer(text):
        piece = text[cur:m.end()].strip()
        if piece:
            out.append(piece)
        cur = m.end()
    tail = text[cur:].strip()
    return out + [tail] if tail else out


def split_long(text: str, tokens: int, limit: int) -> list[str]:
    """One over-long sentence cut at spaces into pieces of about equal length."""
    parts = math.ceil(tokens / (limit * 0.9))
    size = len(text) / parts
    cuts = [0]
    for i in range(1, parts):
        space = text.find(" ", int(i * size))
        if space > cuts[-1]:
            cuts.append(space + 1)
    cuts.append(len(text))
    return [text[a:b].strip() for a, b in zip(cuts, cuts[1:]) if text[a:b].strip()]


def items(owners: list[tuple[str, str]], count: Counter, size: int) -> list[Item]:
    """Sentence items of each (label, text) owner, over-long sentences cut."""
    out: list[Item] = []
    for o, (label, text) in enumerate(owners):
        sents = sentences(text)
        first = True
        for s, t in zip(sents, count(sents)):
            pieces = [(s, t)] if t <= size else list(zip(p := split_long(s, t, size), count(p)))
            for ptext, ptok in pieces:
                out.append(Item(ptext, ptok, o, first, label))
                first = False
    return out


def pack(its: list[Item], size: int = config.CHUNK_TOKENS, overlap: int = config.OVERLAP_TOKENS,
         min_tail: int = config.MIN_TAIL_TOKENS) -> list[list[Item]]:
    """Items packed into chunks; overlap repeats only sentences of the owner the next chunk opens in."""
    chunks: list[list[Item]] = []
    cur: list[Item] = []
    n_back = 0
    for it in its:
        if cur and sum(i.tokens for i in cur) + it.tokens > size:
            chunks.append(cur)
            back: list[Item] = []
            for i in reversed(cur):
                if i.owner != it.owner or sum(b.tokens for b in back) + i.tokens > overlap:
                    break
                back.insert(0, i)
            cur, n_back = back, len(back)
        cur.append(it)
    fresh = cur[n_back:]
    if fresh:
        ft = sum(i.tokens for i in fresh)
        if chunks and ft < min_tail and sum(i.tokens for i in chunks[-1]) + ft <= size + min_tail:
            chunks[-1] = chunks[-1] + fresh
        else:
            chunks.append(cur)
    return chunks


def render(chunk: list[Item]) -> str:
    """The chunk's text: one paragraph per owner, opened by its label when it has one."""
    paras: list[str] = []
    prev = None
    for i in chunk:
        if i.owner != prev:
            # A label from a speech the parser split already reads "X (continued, part 2 of 2)".
            more = "" if i.first or "(continued" in i.label else " (continued)"
            lead = f"{i.label}{more}: " if i.label else ""
            paras.append(lead + i.text)
            prev = i.owner
        else:
            paras[-1] += " " + i.text
    return "\n\n".join(paras)


# ---------- law ----------

def act_title(title: str) -> str:
    return re.sub(r"\s*\((?:Revised|Disemak)[^)]*\)\s*$", "", title.strip(" *"))


# What the reprint PDFs' text layer gives for a line-end hyphen (U+FFFE), and Symbol-font
# characters in the private use area: a rule (U+F0BE), an asterisk, a dash.
_LAW_CHARS = str.maketrans({"￾": "-", "": "*", "": "-", "­": None, "": None})


def clean_law(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.translate(_LAW_CHARS))


def law_chunks(sections: Iterator[dict], acts: dict[str, dict], count: Counter) -> Iterator[Chunk]:
    for s in sections:
        a = acts.get(s["act"], {})
        bi = s["lang"] == "BI"
        title = act_title(a.get("title_bi" if bi else "title_bm", "") or a.get("title_bi", ""))
        word = ("section", "Part", "Act", "reprint as at") if bi else ("seksyen", "Bahagian", "Akta", "cetakan semula pada")
        head = f"{title} ({word[2]} {s['act']}), {word[0]} {s['number']}"
        if s["heading"]:
            head += f": {s['heading']}"
        if s["part"]:
            part = re.sub(r"^(?:Part|Bahagian)\s+", "", s["part"], flags=re.I)
            head += f". {word[1]} {part}" + (f": {s['part_title']}" if s["part_title"] else "")
        status = "" if a.get("status", "in force") == "in force" else f" ({a['status']})"
        head += f". {word[3]} {s['as_at']}{status}."
        its = items([("", clean_law(s["text"]))], count, config.CHUNK_TOKENS)
        for k, c in enumerate(pack(its)):
            yield Chunk("law", f"law:{s['act']}:{s['lang']}:{s['number']}", k, head, render(c),
                        sum(i.tokens for i in c), act=s["act"], lang=s["lang"], section=s["number"],
                        date=s["as_at"], page_start=s["page_start"], page_end=s["page_end"])


# ---------- debates ----------

def debate_chunks(units: Iterator[dict], enriched: dict[str, dict], party, bills: dict[str, dict],
                  count: Counter) -> Iterator[Chunk]:
    """`party(parliament, seat, date)` gives a speaker's party; `bills` maps an agenda heading to
    its bill_links.csv row."""
    for u in units:
        rec = enriched.get(u["id"], {})
        speeches = u["speeches"]
        owners = [(s["label"], s["text"]) for s in speeches]
        bill = bills.get(u["topic"] or "")
        place = CHAMBERS[u["chamber"]][0]
        head = f"{place}, {u['date']}, Parliament {u['parliament']}."
        if u["topic"]:
            head += " " + re.sub(r"^(?:RANG UNDANG-UNDANG\s+){2,}", "RANG UNDANG-UNDANG ", u["topic"].strip()) + "."
        if bill and bill.get("act"):
            head += f" Bill for the {act_title(bill['act_title_bi'])} (Act {bill['act']})."
        note = ""
        if rec:
            note = f"Summary (AI): {rec['summary_en']} Topics: {', '.join(rec['topics'])}."
        for k, c in enumerate(pack(items(owners, count, config.CHUNK_TOKENS))):
            who: dict[int, int] = {}
            for i in c:
                who[i.owner] = who.get(i.owner, 0) + i.tokens
            spk: dict[tuple, dict] = {}
            for o, t in who.items():
                s = speeches[o]
                key = (s["name"], s["seat"])
                p = party(u["parliament"], s["seat"], u["date"]) if s["seat"] and not s["senator"] else ""
                d = spk.setdefault(key, {"name": s["name"], "seat": s["seat"], "party": p, "role": s["role"],
                                         "label": s["label"].split(" (continued")[0], "tokens": 0})
                d["tokens"] += t
            named = [d for d in sorted(spk.values(), key=lambda d: -d["tokens"]) if d["tokens"] >= MIN_SPEAKER_TOKENS][:4]
            h = head
            if named:
                h += " Speakers: " + "; ".join(d["label"] + (f" ({d['party']})" if d["party"] else "") for d in named) + "."
            seqs = [speeches[o]["seq"] for o in who]
            yield Chunk("debate", f"debate:{u['id']}", k, h, render(c), sum(i.tokens for i in c), note=note,
                        act=bill["act"] if bill else "", chamber=u["chamber"], date=u["date"],
                        parliament=u["parliament"], unit=u["id"], seq_first=min(seqs), seq_last=max(seqs),
                        speakers=list(spk.values()), topics=list(rec.get("topics", [])))


# ---------- sources ----------

def read_jsonl(path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def all_chunks(count: Counter) -> Iterator[Chunk]:
    """Every chunk: the law first, then the debates in sitting order."""
    from . import enrich, parties

    acts = {a["number"]: a for a in csv.DictReader(open(config.DATA / "acts.csv", encoding="utf-8"))}
    yield from law_chunks(read_jsonl(config.DATA / "act_sections.jsonl"), acts, count)
    enriched = {r["unit"]: {"summary_en": r["summary_en"], "topics": r["topics"]} for r in read_jsonl(enrich.ENRICHED)}
    bills = {r["heading"]: r for r in csv.DictReader(open(links.OUT, encoding="utf-8")) if r["act"]}
    yield from debate_chunks(read_jsonl(enrich.UNITS), enriched, parties.lookup(), bills, count)


def qwen_counter() -> Counter:
    """Token counts from the Qwen3 tokenizer (the same for every Qwen3 embedding size)."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(config.TOKENIZER)

    def count(texts: Sequence[str]) -> list[int]:
        if not texts:
            return []
        return [len(ids) for ids in tok(list(texts), add_special_tokens=False)["input_ids"]]

    return count
