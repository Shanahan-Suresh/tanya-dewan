"""Re-parse some sittings after a parser fix and put the result in place in data/speeches.jsonl and
data/enrich/units.jsonl, so the rest of the corpus and its enrichment stay as they are.

The enrichment is keyed by extract id and the debate eval by speech seq, so the tool refuses to
write when a re-parsed sitting's extract ids or seqs differ from the old ones: that change needs a
full `python -m parlimen.hansard` run and a fresh enrichment of the sitting. It prints each field
that changed. After it, rebuild the index (`python -m parlimen.index rebuild`).

Run:  python tools/reparse.py --dates 2023-10-18 [--chamber DR] [--dry-run]
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parlimen import enrich, hansard, sittings  # noqa: E402
from parlimen.drafts import replace_rows as replace  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dates", nargs="+", required=True, metavar="ISO")
    ap.add_argument("--chamber", choices=["DR", "KK"], default="DR")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    every = sittings.read_csv()
    registers = hansard.build_registers(every)
    targets = {(s.chamber, s.date): s for s in every if s.chamber == args.chamber and s.date in args.dates}
    old_sp: dict[tuple, list[dict]] = {k: [] for k in targets}
    for line in open(hansard.SPEECHES_OUT, encoding="utf-8"):
        r = json.loads(line)
        if (r["chamber"], r["date"]) in old_sp:
            old_sp[r["chamber"], r["date"]].append(r)
    old_units: dict[tuple, list[dict]] = {k: [] for k in targets}
    for u in enrich._read(enrich.UNITS):
        if (u["chamber"], u["date"]) in old_units:
            old_units[u["chamber"], u["date"]].append(u)

    for key, s in sorted(targets.items()):
        speeches, rep = hansard.parse_one(s, registers)
        new_sp = [asdict(sp) for sp in speeches]
        new_units = enrich.make_units(new_sp) if new_sp else []
        old = old_sp[key]
        if [r["seq"] for r in new_sp] != [r["seq"] for r in old] or \
                [u["id"] for u in new_units] != [u["id"] for u in old_units[key]] or \
                [[p["seq"] for p in u["speeches"]] for u in new_units] != \
                [[p["seq"] for p in u["speeches"]] for u in old_units[key]]:
            sys.exit(f"{key}: speech seqs or extract ids changed ({len(old)} -> {len(new_sp)} speeches, "
                     f"{len(old_units[key])} -> {len(new_units)} extracts); nothing written")
        changed: dict[str, int] = {}
        for a, b in zip(old, new_sp):
            for f in b:
                if a.get(f) != b[f]:
                    changed[f] = changed.get(f, 0) + 1
        units_changed = sum(1 for a, b in zip(old_units[key], new_units) if a != b)
        print(f"{key[0]} {key[1]}: {len(new_sp)} speeches, fields changed {changed or 'none'}; "
              f"{units_changed} of {len(new_units)} extracts changed {rep.note}")
        if args.dry_run or (not changed and not units_changed):
            continue
        replace(hansard.SPEECHES_OUT, lambda r, k=key: (r["chamber"], r["date"]) != k, new_sp)
        replace(enrich.UNITS, lambda u, k=key: (u["chamber"], u["date"]) != k, new_units)


if __name__ == "__main__":
    main()
