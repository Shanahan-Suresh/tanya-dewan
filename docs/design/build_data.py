"""Real records for the redesign mockups, written to docs/design/data.json.

Each mockup shows true content from data/site.db: one MP (Dzulkefly Ahmad, Kuala Selangor), one
agenda item from a draft sitting, one bill's timeline, the home page lists, topic trends by year,
and one real answer from the running site's /api/ask (one Haiku rerank and answer, about [amount removed]).

Run:  python docs/design/build_data.py [--no-ask]
"""
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("data.json")
MP = "dzulkefly-ahmad"
UNIT = "DR-2026-10-22-017"
QUESTION = "What has the government said about targeted diesel subsidies?"


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    c = sqlite3.connect(ROOT / "data" / "site.db")
    c.row_factory = sqlite3.Row
    meta = {r["key"]: json.loads(r["value"]) for r in c.execute("SELECT key, value FROM meta")}

    m = dict(c.execute("SELECT * FROM members WHERE slug = ?", (MP,)).fetchone())
    m["seats"] = rows(c, "SELECT parliament, seat, code FROM member_seats WHERE member = ? ORDER BY parliament", (MP,))
    m["parties"] = rows(c, "SELECT parliament, party, date_from, date_to FROM member_parties WHERE member = ?", (MP,))
    m["counts"] = {
        "items_spoken": c.execute("SELECT COUNT(DISTINCT unit) FROM speeches WHERE member = ? AND chars >= 200",
                                  (MP,)).fetchone()[0],
        "questions_answered": c.execute("SELECT COUNT(*) FROM qa WHERE answerer_member = ?", (MP,)).fetchone()[0],
        "questions_asked": c.execute("SELECT COUNT(*) FROM qa WHERE asker_member = ?", (MP,)).fetchone()[0],
        "commitments": c.execute("SELECT COUNT(*) FROM commitments WHERE member = ?", (MP,)).fetchone()[0],
    }
    m["activity_by_month"] = rows(c, "SELECT substr(u.date, 1, 7) AS month, COUNT(DISTINCT u.id) AS items "
                                     "FROM speeches s JOIN units u ON u.id = s.unit WHERE s.member = ? AND s.chars >= 200 "
                                     "GROUP BY month ORDER BY month", (MP,))
    m["offices"] = rows(c, "SELECT office, MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n FROM commitments "
                           "WHERE member = ? AND office != '' GROUP BY office ORDER BY first", (MP,))
    m["top_topics"] = rows(c, "SELECT t.name, COUNT(DISTINCT t.unit) AS n FROM unit_topics t WHERE t.unit IN "
                              "(SELECT DISTINCT unit FROM speeches WHERE member = ? AND chars >= 200) "
                              "GROUP BY t.topic ORDER BY n DESC LIMIT 8", (MP,))
    m["recent_commitments"] = rows(c, "SELECT id, unit, date, quote, promise, deadline, amount, kind, office "
                                      "FROM commitments WHERE member = ? ORDER BY date DESC LIMIT 6", (MP,))
    m["recent_answers"] = rows(c, "SELECT id, unit, date, asker, asker_seat, question, answer FROM qa "
                                  "WHERE answerer_member = ? ORDER BY date DESC LIMIT 5", (MP,))

    u = dict(c.execute("SELECT * FROM units WHERE id = ?", (UNIT,)).fetchone())
    u["sitting"] = dict(c.execute("SELECT * FROM sittings WHERE chamber = ? AND date = ?",
                                  (u["chamber"], u["date"])).fetchone())
    u["speech_rows"] = rows(c, "SELECT seq, label, name, seat, party, member, time, page_start, text FROM speeches "
                               "WHERE unit = ? ORDER BY seq", (UNIT,))
    u["qa"] = rows(c, "SELECT * FROM qa WHERE unit = ?", (UNIT,))
    u["commitment_rows"] = rows(c, "SELECT * FROM commitments WHERE unit = ?", (UNIT,))
    u["neighbours"] = rows(c, "SELECT id, business FROM units WHERE chamber = ? AND date = ? AND ord IN (?, ?) "
                              "ORDER BY ord", (u["chamber"], u["date"], u["ord"] - 1, u["ord"] + 1))

    bill = dict(c.execute("SELECT * FROM bills WHERE change = 'amend' AND act = '265'").fetchone() or
                c.execute("SELECT * FROM bills WHERE change = 'amend' ORDER BY slug DESC").fetchone())
    bill["timeline"] = rows(c, "SELECT u.id, u.date, u.business, u.summary_en, u.speeches FROM units u "
                               "WHERE u.bill = ? ORDER BY u.date, u.ord", (bill["slug"],))

    home = {
        "meta": {k: meta.get(k) for k in ("units", "speeches", "qa", "commitments", "members", "built")},
        "latest_sittings": rows(c, "SELECT s.chamber, s.date, s.draft, (SELECT COUNT(*) FROM units u WHERE "
                                   "u.chamber = s.chamber AND u.date = s.date) AS items FROM sittings s "
                                   "ORDER BY s.date DESC, s.chamber LIMIT 6"),
        "latest_commitments": rows(c, "SELECT id, unit, date, speaker, office, quote, promise FROM commitments "
                                      "WHERE kind = 'promise' ORDER BY date DESC LIMIT 6"),
        "topics": rows(c, "SELECT topic, MIN(name) AS name, COUNT(*) AS n FROM unit_topics GROUP BY topic "
                          "ORDER BY n DESC"),
        "topic_trend": rows(c, "SELECT name, substr(date, 1, 4) AS year, COUNT(*) AS n FROM unit_topics "
                               "WHERE topic IN (SELECT topic FROM unit_topics GROUP BY topic ORDER BY COUNT(*) DESC "
                               "LIMIT 6) GROUP BY name, year ORDER BY name, year"),
    }

    answer = None
    if "--no-ask" not in sys.argv:
        req = urllib.request.Request("http://127.0.0.1:8780/api/ask", json.dumps({"question": QUESTION}).encode(),
                                     {"Content-Type": "application/json"})
        answer = json.load(urllib.request.urlopen(req, timeout=120))
    elif OUT.exists():
        answer = json.loads(OUT.read_text(encoding="utf-8")).get("answer")

    OUT.write_text(json.dumps({"mp": m, "debate": u, "bill": bill, "home": home, "answer": answer},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT}: {OUT.stat().st_size // 1024} KB; answer {'yes' if answer else 'no'}")


if __name__ == "__main__":
    main()
