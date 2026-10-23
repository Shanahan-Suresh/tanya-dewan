"""Party membership with dates for each Dewan Rakyat member of the 14th and 15th Parliaments.

The attendance lists name each member's seat but print the party only in 2018, and MPs changed
party during both Parliaments. Two Wikipedia pages give the rest:
- "Members of the Dewan Rakyat, <N>th Malaysian Parliament": each seat with its member or
  members ("since 26 January 2019"), the party at the end of the term, and notes on each change
  ("sacked from the party on 28 May 2020 ... joined PEJUANG in August 2020").
- "Results of the 2022 Malaysian general election by parliamentary constituency": the party
  that won each seat at GE14 and at GE15.
Wikipedia refuses the crawler's user agent, so the wikitext comes through the installed Chrome,
once per page, into data/raw/wikipedia/.

A seat row with one member and no note gives the member's spells with no API call: the
election party for the whole term, or, when the party at the end differs, the election party
and the end party with the change date unknown ("?"). Claude Haiku 5.5 reads the other rows.
Code then settles each answer: a spell is kept only when the dates it cites and its party are in
the row's text; a member's "since" and "until" dates bound their spells; an election winner's
first spell takes the party that won the seat. A support declaration is not a change of party.

Run:  python -m parlimen.parties     ->  data/parties.csv (parliament, code, seat, member,
                                          party, from, to; "" is the start or end of the term,
                                          "?" a change on a date the sources do not give)
"""

import argparse
import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import anthropic

from . import config, enrich

MODEL = "claude-haiku-5-5"
RAW = config.RAW / "wikipedia"
OUT = config.DATA / "parties.csv"
LLM_ROWS = config.DATA / "parties-llm.jsonl"
WIKI = "https://en.wikipedia.org/w/index.php?title={title}&action=raw"
MEMBERS_PAGE = "Members_of_the_Dewan_Rakyat,_{n}th_Malaysian_Parliament"
RESULTS_PAGE = "Results_of_the_2022_Malaysian_general_election_by_parliamentary_constituency"

SYSTEM = """You read one row of Wikipedia's table of the members of Malaysia's Dewan Rakyat (the {n}th Parliament, {start} to {end}) and write each member's party membership as dated spells.

The row gives the seat, its member or members ("since" or "until" a date), the party shown at the end of the term, and notes. Write one spell per member per party, in order. A member who leaves a party and sits as an independent has a spell with party "IND". A member who is sacked, quits or has membership void becomes "IND" from that date unless the notes name the next party. A member may hold two memberships at once (for example a coalition's direct membership and a party's); write both spells.

Rules:
- party: the party's short name as the row writes it (UMNO, PKR, DAP, BERSATU, PAS, AMANAH, IND, ...). Use BERSATU for PPBM.
- from_text and to_text: the date of the change copied exactly as the row writes it ("28 May 2020", "August 2020"); "" for the start or the end of the term.
- from and to: the same dates in ISO form (YYYY-MM-DD, or YYYY-MM when the row gives no day); "" for the start or end of the term.
- A coalition (BN, PH, PN, GPS, GTA) is not a party: write the member's party inside it.
- A declaration of support for a Prime Minister or a coalition is not a change of party, and neither is the member's party joining or leaving a coalition.
- Never invent a date or a party. When the notes give a change with no date, leave it out."""

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["spells"],
    "properties": {"spells": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["member", "party", "from_text", "from", "to_text", "to"],
        "properties": {k: {"type": "string"} for k in ("member", "party", "from_text", "from", "to_text", "to")},
    }}},
}

TERMS = {14: ("2018-07-16", "2022-10-10"), 15: ("2022-12-19", "")}
# "BBB" is the results page's typo for PBB (Petra Jaya, Batang Sadong).
SAME_PARTY = {"PPBM": "BERSATU", "BERSATU SABAH": "BERSATU", "IND": "IND", "INDEPENDENT": "IND", "BBB": "PBB"}
COALITIONS = {"BN", "PH", "PN", "GPS", "GTA", "GS", "USA"}


def party_name(cell: str) -> str:
    """The party in a cell such as "PH ( PKR )", "GRS (BERSATU Sabah)", "PAS" or "Ind"."""
    m = re.search(r"\(\s*([^()]+?)\s*\)\s*$", cell)
    name = (m.group(1) if m else cell).strip()
    return SAME_PARTY.get(name.upper(), name)


# ---------- the pages ----------

def page(title: str, name: str) -> str:
    """A page's wikitext, from data/raw/wikipedia/<name>.wikitext or once through Chrome."""
    path = RAW / f"{name}.wikitext"
    if path.exists():
        return path.read_text(encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        resp = browser.new_page().goto(WIKI.format(title=title))
        if resp is None or resp.status != 200:
            raise RuntimeError(f"Wikipedia {title}: status {resp and resp.status}")
        text = resp.text()
        browser.close()
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def pendulum(n: int) -> dict[str, str]:
    """Seat name -> the winner's party, from the members page's election pendulum."""
    pattern = r'^\|\s*([^|\n]+?)\s*\|\|\s*[^|\n]+?\s*\|\|\s*([^|\n]+?)\s*\|\|\s*style="text-align:center;"\|\s*[\d.]+\s*$'
    return {m.group(1): party_name(m.group(2))
            for m in re.finditer(pattern, page(MEMBERS_PAGE.format(n=n), f"members-{n}"), re.M)}


# The results page has GE15 Jeli as PAS; Zahari Kechik won it for BERSATU (Malaysiakini,
# 2023-11-08, "Another Bersatu MP backs Anwar", cited on the members page).
ELECTED_FIXES = {(15, "P030"): "BERSATU"}


def elected() -> dict[tuple[int, str], str]:
    """(Parliament, seat code) -> the party that won the seat at the general election. The
    results summary table's party cells are GE14, at dissolution, and GE15. It gives the logo a
    candidate stood under, and DAP candidates stood under the PKR logo in GE14 (and in a few
    seats in GE15), so where the members page's pendulum says DAP for a PKR result, DAP wins."""
    out = {}
    pend = {n: pendulum(n) for n in config.PARLIAMENTS}
    seats = {(n, r["code"]): r["seat"] for n in config.PARLIAMENTS for r in rows(n)}
    for line in page(RESULTS_PAGE, "results-2022").split("\n"):
        m = re.match(r'\|\s*style="text-align:left;"\s*\|\s*(P\d{3})\b', line)
        if not m or (14, m.group(1)) in out:
            continue
        cells = [re.sub(r'^style="[^"]*"\s*\|', "", c.strip()).strip() for c in line[1:].split("||")
                 if re.match(r'\s*style="text-align:left;?"\s*\|', c)]
        if len(cells) >= 5:  # seat, state, GE14, dissolution, GE15
            for n, cell in ((14, cells[2]), (15, cells[4])):
                if cell != "Vacant":
                    party = party_name(cell)
                    if party == "PKR" and pend[n].get(seats.get((n, m.group(1)), "")) == "DAP":
                        party = "DAP"
                    out[(n, m.group(1))] = party
    return {**out, **ELECTED_FIXES}


def _notes(text: str) -> dict[str, str]:
    """Named notes defined anywhere on the page, by name."""
    out = {}
    for m in re.finditer(r'<ref\s+(?=[^>]*group="?N"?)(?=[^>]*name="?([^">/]+)"?)[^>/]*>(.*?)</ref>', text, re.S):
        out[m.group(1).strip()] = m.group(2)
    return out


def clean(cell: str, notes: dict[str, str]) -> str:
    """A cell as plain text: named notes resolved, citations and markup removed."""
    # Names are per group: a citation may share a name with a note.
    cell = re.sub(r'<ref\s+(?=[^>]*group="?N"?)(?=[^>]*name="?([^">/]+)"?)[^>]*/>',
                  lambda m: f" (Note: {notes[m.group(1).strip()]})" if m.group(1).strip() in notes else "", cell)
    cell = re.sub(r'<ref[^>/]*group="?N"?[^>/]*>(.*?)</ref>', r" (Note: \1)", cell, flags=re.S)
    cell = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", cell, flags=re.S)
    cell = re.sub(r"\{\{[Cc]ite[^{}]*\}\}", "", cell)
    cell = re.sub(r"\{\{(?:party color\|[^{}]*|[^{}|]*/meta/shading)\}\}", "", cell)  # inside a colour attribute
    cell = re.sub(r"\{\{(?:small|Font color\|[^|]*)\|([^{}]*)\}\}", r"\1", cell)
    cell = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", cell)
    cell = re.sub(r'^\s*(?:bgcolor|style|rowspan)="?[^|]*\|', "", cell)
    cell = re.sub(r"<small>.*?</small>", "", cell)  # an office: "(First Deputy Speaker)"
    cell = re.sub(r"'''|''|<br\s*/?>|<nowiki>.*?</nowiki>|</?[a-z]+[^>]*>", " ", cell)
    cell = re.sub(r"\{\{[^{}]*\}\}", "", cell)
    return re.sub(r"\s+", " ", cell).strip()


def rows(n: int) -> list[dict]:
    """One row per seat: code, seat, and its members' cells as plain text ("name | party")."""
    text = page(MEMBERS_PAGE.format(n=n), f"members-{n}")
    notes = _notes(text)
    body = text[text.index("Elected members by state"):]
    body = body[:body.index("== Notes ==")] if "== Notes ==" in body else body
    out: list[dict] = []
    for chunk in re.split(r"\n\|-\s*\n", body):
        cells: list[str] = []
        for ln in chunk.split("\n"):
            if ln.startswith("|}"):
                break
            if ln.startswith("|"):
                cells.append(ln[1:])
            elif cells:  # a cell that runs on to the next line
                cells[-1] += " " + ln
        if not cells:
            continue
        m = re.match(r'\s*(?:rowspan="?\d+"?\s*\|)?\s*(P\d{3})\s*$', cells[0])
        if m:  # a seat row: code, seat, member, party
            out.append({"parliament": n, "code": m.group(1), "seat": clean(cells[1], notes),
                        "members": [" | ".join(clean(c, notes) for c in cells[2:])]})
        elif out and len(cells) >= 2 and not cells[0].lstrip().startswith(("colspan", "!")):
            out[-1]["members"].append(" | ".join(clean(c, notes) for c in cells))  # a by-election member
    return out


def member_rows(row: dict) -> list[dict]:
    """Each member of a seat row: name, the "since" and "until" dates, the party at the end."""
    out = []
    for m in row["members"]:
        who, _, party = m.rpartition(" | ")
        span = {k: re.search(rf"\b{k} (\d{{1,2}} \w+ \d{{4}})", who) for k in ("since", "until", "from")}
        since = span["since"] or span["from"]
        name = re.split(r" (?:since|until|from) \d| \(Note:", who)[0].strip()
        out.append({"name": name, "party": party_name(party) if party.strip() else "",
                    "since": since.group(1) if since else "", "until": span["until"].group(1) if span["until"] else ""})
    return out


def _iso(date_text: str) -> str:
    return datetime.strptime(date_text, "%d %B %Y").date().isoformat()


def spell(member: str, party: str, frm: str = "", to: str = "", frm_text: str = "", to_text: str = "") -> dict:
    return {"member": member, "party": party, "from_text": frm_text, "from": frm, "to_text": to_text, "to": to}


def simple(row: dict, won: str | None) -> list[dict] | None:
    """The spells of a row with one member and no note, or None."""
    if len(row["members"]) != 1 or "(Note:" in row["members"][0]:
        return None
    [m] = member_rows(row)
    if won is None or won == m["party"] or not m["party"]:
        return [spell(m["name"], m["party"] or won or "")]
    return [spell(m["name"], won, to="?"), spell(m["name"], m["party"], frm="?")]


# ---------- the model's answer, settled ----------

def checked(row: dict, spells: list[dict]) -> tuple[list[dict], int]:
    """Spells whose cited dates and party are in the row's text, and whose party is not a
    coalition: a fixed one, or the "X" of an end-of-term cell "X ( Y )". Returns the spells and
    the count dropped."""
    text = " ".join(row["members"]).lower().replace(",", "")
    coalitions = COALITIONS | {m.group(1).strip() for c in row["members"]
                               if (m := re.search(r"\|\s*([^|()]+?)\s*\([^()]*\)\s*$", c))}
    keep = [s for s in spells
            if s["party"] not in coalitions and s["member"] != "Vacant"
            and all(s[k].lower().replace(",", "") in text for k in ("from_text", "to_text"))
            and (s["party"] == "IND" or s["party"].lower() in text
                 or (s["party"] == "BERSATU" and "ppbm" in text))]
    return keep, len(spells) - len(keep)


def settle(row: dict, spells: list[dict], won: str | None) -> tuple[list[dict], int]:
    """Bound each member's spells by their "since" and "until" dates, give an election winner's
    first spell the party that won the seat, and end an open spell where a later one starts (two
    spells from the start of the term stay: a member may hold two memberships). Returns the
    spells and the fix count."""
    members = [m for m in member_rows(row) if m["name"] != "Vacant"]
    fixes = 0

    def owner(s: dict) -> dict:
        words = set(s["member"].lower().split())
        return max(members, key=lambda m: len(words & set(m["name"].lower().split())))

    out = []
    for m in members:
        mine = [dict(s) for s in spells if owner(s) is m]
        if not mine:
            continue
        mine.sort(key=lambda s: s["from"])
        if m["since"] and not mine[0]["from"]:
            mine[0].update({"from": _iso(m["since"]), "from_text": m["since"]})
            fixes += 1
        if m["until"] and not mine[-1]["to"]:
            mine[-1].update({"to": _iso(m["until"]), "to_text": m["until"]})
            fixes += 1
        if not m["since"] and won:
            first = [s for s in mine if not s["from"]]
            if not first:  # nothing from the start of the term: the election party fills the gap
                mine.insert(0, spell(m["name"], won, to=mine[0]["from"], to_text=mine[0]["from_text"]))
                fixes += 1
            elif won not in {s["party"] for s in first}:
                first[0]["party"] = won
                fixes += 1
        # IND while another membership stays open is a misreading: drop it.
        open_at = lambda s, d: s["party"] != "IND" and s["from"] <= d and (not s["to"] or s["to"] > d)  # noqa: E731
        kept = [s for s in mine if not (s["party"] == "IND" and s["from"] and any(open_at(t, s["from"]) for t in mine))]
        # X, then IND, then X again is the party moving between coalitions: one spell of X.
        merged: list[dict] = []
        for s in kept:
            if (len(merged) >= 2 and merged[-1]["party"] == "IND" and merged[-2]["party"] == s["party"]
                    and merged[-2]["to"] == merged[-1]["from"] and merged[-1]["to"] == s["from"]):
                merged.pop()
                merged[-1].update({"to": s["to"], "to_text": s["to_text"]})
            else:
                merged.append(s)
        fixes += len(mine) - len(merged)
        mine = merged
        for s in mine:
            later = [t for t in mine if t["from"] > s["from"]]
            if not s["to"] and later:
                nxt = min(later, key=lambda t: t["from"])
                s.update({"to": nxt["from"], "to_text": nxt["from_text"]})
                fixes += 1
        out += mine
    return out, fixes


SEAT_SPELLINGS = [(r"tanjung", "tanjong"), (r"timur", "timor"), (r"datok", "datuk"), (r"ba?ha?ru", "bharu"),
                  (r"^silam$", "lahad datu")]  # Silam took the name Lahad Datu; the record keeps both


def _seat_key(seat: str) -> str:
    """Seat names differ in spelling between the record and Wikipedia ("Tanjong", "Tanjung")."""
    key = seat.lower().strip()
    for pattern, spelling in SEAT_SPELLINGS:
        key = re.sub(pattern, spelling, key)
    return re.sub(r"[^a-z]", "", key)


def lookup(path=OUT):
    """party(parliament, seat, date) -> the party or parties ("BERSATU", "GRS+BERSATU") of the
    seat's member on that date; "" when the record holds none or the date falls in an undated
    change."""
    spells: dict[tuple[int, str], list[dict]] = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        spells.setdefault((int(r["parliament"]), _seat_key(r["seat"])), []).append(r)

    def party(parliament: int, seat: str, date: str) -> str:
        found = [s["party"] for s in spells.get((parliament, _seat_key(seat)), [])
                 if "?" not in (s["from"], s["to"]) and s["from"][:len(date)] <= date
                 and (not s["to"] or date < s["to"])]
        return "+".join(dict.fromkeys(found))
    return party


def ask(client, row: dict) -> dict:
    start, end = TERMS[row["parliament"]]
    params = {"model": MODEL, "max_tokens": 8000,
              "system": SYSTEM.format(n=row["parliament"], start=start, end=end or "now"),
              "messages": [{"role": "user", "content": f"Seat {row['code']} {row['seat']}\n" + "\n".join(
                  f"Member row {i + 1}: {m}" for i, m in enumerate(row["members"]))}],
              "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    try:
        return enrich.call(client, params, "parties")
    except anthropic.APIError as e:
        return {"error": str(e)[:300], "cost_usd": 0.0}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    won = elected()
    seats = [r for n in config.PARLIAMENTS for r in rows(n)]
    key = lambda r: (r["parliament"], r["code"])  # noqa: E731
    done = {key(r): r for r in enrich._read(LLM_ROWS) if "result" in r}
    easy = {key(r): s for r in seats if (s := simple(r, won.get(key(r)))) is not None}
    hard = [r for r in seats if key(r) not in easy and key(r) not in done]
    print(f"{len(seats)} seats; {len(easy)} simple; {len(hard)} to read with {MODEL}", flush=True)
    client = enrich._client() if hard else None

    def one(row: dict) -> None:
        out = ask(client, row)
        enrich._append(LLM_ROWS, [{"parliament": row["parliament"], "code": row["code"], **out}])
        print(f"{row['parliament']} {row['code']} {row['seat']}: {'ok' if 'result' in out else out['error']}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, hard))
    done = {key(r): r for r in enrich._read(LLM_ROWS) if "result" in r}

    out, dropped, fixes, missing = [], 0, 0, []
    for r in seats:
        spells = easy.get(key(r))
        if spells is None:
            got = done.get(key(r))
            if got is None:
                missing.append(f"{r['parliament']} {r['code']}")
                continue
            spells, d = checked(r, got["result"]["spells"])
            spells, f = settle(r, spells, won.get(key(r)))
            dropped, fixes = dropped + d, fixes + f
        out += [{"parliament": r["parliament"], "code": r["code"], "seat": r["seat"], **s} for s in spells]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["parliament", "code", "seat", "member", "party", "from", "to",
                                          "from_text", "to_text"])
        w.writeheader()
        w.writerows(out)
    undated = sum(s["to"] == "?" for s in out)
    cost = sum(r["cost_usd"] for r in enrich._read(LLM_ROWS))
    print(f"{len(out)} spells for {len(seats)} seats; {dropped} spells dropped by the check; {fixes} "
          f"settled by the row's dates or the election result; {undated} changes with no date; "
          f"no answer for {missing or 'none'}; US${cost:.2f}")


if __name__ == "__main__":
    main()
