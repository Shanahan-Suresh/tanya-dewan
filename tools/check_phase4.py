"""Phase 4 exit checks on the built index, with the full search pipeline:

1. A search for a known Act returns its debates: the Act's bill, named as a reader would name it,
   searched over the debates with no Act filter, finds debates linked to that Act in the top
   passages; `debates_for_act` lists them, and the Act filter keeps only them.
2. A search inside an Act follows its cross-references: a section's own heading, searched inside
   its Act, brings the sections it names as added passages.

Run:  python tools/check_phase4.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parlimen.search import Filters, Searcher  # noqa: E402

BILLS = {"265": "pindaan Akta Kerja waktu bekerja dan cuti bersalin",
         "574": "Rang Undang-Undang Kanun Keseksaan (Pindaan)",
         "333": "Road Transport (Amendment) Bill, penalties for drink driving"}
XREF_ACTS = ["265", "136", "574"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    s = Searcher()
    ok = True

    for act, question in BILLS.items():
        debates = s.debates_for_act(act)
        t = s.search(question, Filters(kind="debate"))
        linked = [p for p in t.passages if p.act == act]
        only = s.search(question, Filters(kind="debate", act=act))
        passed = bool(debates) and bool(linked) and all(p.act == act for p in only.passages)
        ok &= passed
        print(f"1. Act {act}: {len(debates)} bill debates listed; \"{question}\" -> {len(linked)} of "
              f"{len(t.passages)} top passages are its bill debates -> {'pass' if passed else 'FAIL'}")
        for p in (linked or t.passages)[:2]:
            print(f"   {p.cite}: {p.header[:150]}")

    for act in XREF_ACTS:
        row = s.con.execute(
            "SELECT x.section, c.header FROM xrefs x JOIN chunks c ON c.kind = 'law' AND c.act = x.act "
            "AND c.lang = x.lang AND c.section = x.section AND c.piece = 0 WHERE x.act = ? AND x.lang = 'BI' "
            "GROUP BY x.section ORDER BY COUNT(*) DESC LIMIT 1", (act,)).fetchone()
        if row is None:
            print(f"2. Act {act}: no section names another -> skipped")
            continue
        section, header = row
        heading = header.split(f"section {section}: ", 1)[-1].split(". ", 1)[0]
        t = s.search(heading, Filters(kind="law", act=act, lang="BI"))
        hit = next((p for p in t.passages if not p.via and p.section == section), None)
        added = [p.section for p in t.passages if p.via == f"cross-reference from section {section}"]
        passed = hit is not None and bool(added)
        ok &= passed
        print(f"2. Act {act}: \"{heading}\" -> s. {section} {'found' if hit else 'NOT found'}; "
              f"sections added from it: {', '.join(added) or 'none'} -> {'pass' if passed else 'FAIL'}")

    print("all pass" if ok else "a check failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
