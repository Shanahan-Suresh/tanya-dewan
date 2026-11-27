"""Presentation helpers for the templates: tidy record labels for display. They change how a label
reads, never the record itself; links and ids keep the raw value."""
import re

# Words an all-capitals label keeps in capitals.
_KEEP = {"RM", "ICT", "DNA", "MCMC", "SOCSO", "KWSP", "FELDA", "FELCRA", "MARA", "PTPTN", "EPF", "UK", "US",
         "UN", "GST", "SST", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "KL", "LRT", "MRT"}
# Small words that stay lower case inside a title.
_SMALL = {"dan", "yang", "bagi", "atau", "di", "ke", "dari", "dalam", "untuk", "pada", "oleh", "of", "and",
          "the", "for", "on", "in", "to", "a", "an", "by", "under"}
_VOWEL = re.compile(r"[AEIOUY]")
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
_MONTHS = {
    "en": "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec".split(","),
    "ms": "Jan,Feb,Mac,Apr,Mei,Jun,Jul,Ogo,Sep,Okt,Nov,Dis".split(","),
}


def unstar(s: str) -> str:
    """Drop the leading asterisk the portal puts on amended Act titles."""
    return (s or "").lstrip("* ").strip()


def tcase(s: str) -> str:
    """Title-case the words a label prints in capitals; mixed-case words stay as they are."""
    s = unstar(s)
    words = _WORD.findall(s)
    if not words:
        return s
    caps = [w for w in words if len(w) > 1 and w.isupper()]
    if len(caps) * 2 < len(words):
        return s
    first = words[0]
    seen = [0]

    def fix(m: re.Match) -> str:
        w = m.group(0)
        seen[0] += 1
        # A word with no vowel (BNM, SPRM, PDRM, RMK) can only be an acronym.
        if not (len(w) > 1 and w.isupper()) or w in _KEEP or not _VOWEL.search(w):
            return w
        low = w.lower()
        if low in _SMALL and not (seen[0] == 1 and w == first):
            return low
        return low[:1].upper() + low[1:]

    return _WORD.sub(fix, s)


def cap(s: str) -> str:
    """Capitalise the first letter only."""
    return s[:1].upper() + s[1:] if s else s


def unnum(s: str) -> str:
    """Drop the order number the Hansard puts before an asker's name ("1. Puan ...")."""
    return re.sub(r"^\s*\d+\.\s*", "", s or "")


def stage(business: str, bill_title: str) -> str:
    """What is left of an agenda title once the bill's own name is taken out: the reading."""
    b = re.sub(re.escape(bill_title or ""), "", business or "", flags=re.I)
    b = re.sub(r"(?i)rang undang-undang", "", b)
    return b.strip(" ,-:()")


def hdate(iso: str, lang: str = "en") -> str:
    """2026-10-22 as 22 Oct 2026 (22 Okt 2026 in Malay); anything else comes back unchanged."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m or not 1 <= int(m.group(2)) <= 12:
        return iso
    return f"{int(m.group(3))} {_MONTHS.get(lang, _MONTHS['en'])[int(m.group(2)) - 1]} {m.group(1)}"


# ---------- coalitions, the seat map and the debate timeline ----------

# Each party's coalition in the 15th Parliament; a party not listed counts as Other.
COALITION = {
    "PKR": "PH", "DAP": "PH", "AMANAH": "PH", "UPKO": "PH",
    "UMNO": "BN", "MCA": "BN", "MIC": "BN", "PBRS": "BN",
    "PBB": "GPS", "PRS": "GPS", "SUPP": "GPS", "PDP": "GPS",
    "GRS": "GRS", "STAR": "GRS", "PBS": "GRS",
    "PAS": "PN", "BERSATU": "PN",
}
# Blocs in the order the seat map draws them, left to right.
BLOCS = [("PH", "Pakatan Harapan"), ("BN", "Barisan Nasional"), ("GPS", "Gabungan Parti Sarawak"),
         ("GRS", "Gabungan Rakyat Sabah"), ("Other", ""), ("PN", "Perikatan Nasional")]


def bloc(party: str | None, member: str | None = "x") -> str:
    """The coalition of a party. A speaker with no party and no member record is the Chair."""
    if party:
        return COALITION.get(party, "Other")
    return "Other" if member else "Chair"


def seat_layout(seats: list[dict], rows: int = 8) -> dict:
    """Place seats in a half circle, grouped by bloc from left to right, as SVG coordinates in a
    1000 x 515 box: {"r": dot radius, "seats": [{...seat, bloc, x, y}], "blocs": [(key, name, n)]}.
    A diagram only: the real chamber seats members differently."""
    import math

    order = {k: i for i, (k, _) in enumerate(BLOCS)}
    rows_in = sorted(({**s, "bloc": bloc(s["party"])} for s in seats),
                     key=lambda s: (order[s["bloc"]], s["party"] or "", s["code"]))
    n = len(rows_in)
    if not n:
        return {"r": 0, "seats": [], "blocs": []}
    big, small, cx, cy = 470, 0.38, 500, 500
    radii = [big * (small + (1 - small) * i / (rows - 1)) for i in range(rows)]
    counts = [round(n * r / sum(radii)) for r in radii]
    counts[-1] += n - sum(counts)
    pos = []
    for r, c in zip(radii, counts):
        for k in range(c):
            a = math.pi - math.pi * k / max(1, c - 1)
            pos.append((a, r))
    pos.sort(key=lambda p: (-p[0], p[1]))
    for s, (a, r) in zip(rows_in, pos):
        s["x"], s["y"] = round(cx + r * math.cos(a), 1), round(cy - r * math.sin(a), 1)
    dot = round(min(13.5, (radii[1] - radii[0]) * 0.42), 1)
    blocs = [(k, name, sum(s["bloc"] == k for s in rows_in)) for k, name in BLOCS]
    return {"r": dot, "seats": rows_in, "blocs": [b for b in blocs if b[2]]}


def hhmm(t: str | None) -> str:
    """The Hansard's 1650 as 16.50, as the speech headers print it; anything else comes back empty."""
    return f"{t[:2]}.{t[2:]}" if t and len(t) == 4 and t.isdigit() else ""


def timeline(speeches: list[dict], by_party: bool = False) -> dict:
    """Speeches as bars in lanes, each placed by its share of the debate's characters:
    {"lanes": [(lane, css class, [bar])], "start", "end", "n"}; a bar is {seq, x, w, label, time, i}.
    Lanes are the 15th Parliament's coalitions, or with `by_party` the five parties that spoke most
    (coalitions changed between Parliaments), then Other and the Chair."""
    total = sum(max(1, s.get("chars") or len(s.get("text") or "")) for s in speeches) or 1
    acc, bars = 0, []
    for i, s in enumerate(speeches):
        c = max(1, s.get("chars") or len(s.get("text") or ""))
        bars.append({"seq": s["seq"], "x": round(acc / total * 100, 3), "w": round(c / total * 100, 3),
                     "label": s.get("name") or s.get("label") or s.get("role") or "",
                     "time": hhmm(s.get("time")), "bloc": bloc(s.get("party"), s.get("member")),
                     "party": s.get("party") or "", "i": i})
        acc += c
    if by_party:
        from collections import Counter
        top = [p for p, _ in Counter(b["party"] for b in bars if b["party"]).most_common(5)]
        for b in bars:
            b["lane"] = b["party"] if b["party"] in top else ("Chair" if b["bloc"] == "Chair" else "Other")
        order = [(p, f"p{k}") for k, p in enumerate(top)] + [("Other", "b-Other"), ("Chair", "b-Chair")]
    else:
        for b in bars:
            b["lane"] = b["bloc"]
        order = [(k, f"b-{k}") for k, _ in BLOCS] + [("Chair", "b-Chair")]
    lanes = [(k, cls, [b for b in bars if b["lane"] == k]) for k, cls in order]
    times = [b["time"] for b in bars if b["time"]]
    return {"lanes": [ln for ln in lanes if ln[2]], "start": times[0] if times else "",
            "end": times[-1] if times else "", "n": len(bars)}
