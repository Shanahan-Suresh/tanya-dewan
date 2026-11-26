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
