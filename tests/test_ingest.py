import json

from parlimen import enrich, hansard, index, ingest, links
from parlimen.chunk import Chunk
from parlimen.sittings import Sitting

from test_search import FakeEmbedder


def sitting(date):
    return Sitting(date, "DR", 15, "Penggal Kedua", "Mesyuarat Pertama", f"/files/hindex/pdf/DR-{date}.pdf", "archive")


def speech(date, seq, label, name, seat, text, topic):
    return hansard.Speech("DR", date, 15, seq, 1, 1, "1010", topic, "", label, "", name, seat, False, text)


def parse(s):
    topic = "RANG UNDANG-UNDANG KERJA (PINDAAN) 2024 Bacaan Kali Yang Kedua"
    speeches = [speech(s.date, 1, "Menteri Sumber Manusia [Tuan A]", "Tuan A", "",
                       "Kerajaan akan menaikkan gaji minimum tahun depan. Akta ini sudah lama.", topic),
                speech(s.date, 2, "Tuan B [Bagan]", "Tuan B", "Bagan", "Saya menyokong rang undang-undang ini.", topic)]
    return speeches, hansard.Report("DR", s.date, speeches=len(speeches))


def call(params, job):
    if params["model"] == enrich.MODEL:
        result = {"summary_en": "The minister moved the employment bill.", "summary_ms": "Menteri membentangkan.",
                  "topics": ["labour and jobs"], "entities": [], "qa_pairs": [],
                  "commitments": [{"speech": "S1", "quote": "Kerajaan akan menaikkan gaji minimum tahun depan.",
                                   "promise": "Raise the minimum wage", "deadline": "next year", "amount": ""},
                                  {"speech": "S1", "quote": "Akta ini sudah lama.", "promise": "Old law",
                                   "deadline": "", "amount": ""}]}
    else:
        result = {"checks": [{"id": "C1", "verdict": "promise", "promise_fixed": "Raise the minimum wage next year",
                              "reason": "a dated pledge"},
                             {"id": "C2", "verdict": "past_or_existing", "promise_fixed": "", "reason": "a fact"}]}
    return {"result": result, "cost_usd": 0.001, "input_tokens": 10, "output_tokens": 10}


def test_a_new_sitting_ingests_with_no_manual_step(tmp_path, monkeypatch):
    for mod, name in [(hansard, "SPEECHES_OUT"), (hansard, "REPORT_OUT"), (enrich, "UNITS"), (enrich, "RAW"),
                      (enrich, "ENRICHED"), (enrich, "CHECKS"), (links, "OUT")]:
        monkeypatch.setattr(mod, name, tmp_path / getattr(mod, name).name)
    hansard.REPORT_OUT.write_text(",".join(hansard.REPORT_FIELDS) + "\nDR,2024-03-01,,,0,0,0,0,0,0,,\n", encoding="utf-8")
    old = Chunk("debate", "debate:DR-2024-03-01-001", 0, "Dewan Rakyat, 2024-03-01.", "Tuan C: Ya.", 3,
                chamber="DR", date="2024-03-01", parliament=15, unit="DR-2024-03-01-001")
    index.build([old], tmp_path / "index.db")
    for variant in ("h", "hn"):
        index.embed("0.6b", variant, tmp_path, embedder=FakeEmbedder())
    enrich.UNITS.write_text(json.dumps({"id": "DR-2024-03-01-001", "chamber": "DR", "date": "2024-03-01",
                                        "parliament": 15, "topic": "", "speeches": []}) + "\n", encoding="utf-8")
    by_name = {"KERJA": [{"number": "265", "title_bi": "*EMPLOYMENT ACT 1955", "title_bm": "*AKTA KERJA 1955",
                          "status": "in force"}]}
    listing = [sitting("2024-03-01"), sitting("2024-03-05")]
    run = lambda: ingest.ingest(listing, parse=parse, call=call, party=lambda p, seat, d: "DAP" if seat else "",  # noqa: E731
                                count=lambda texts: [len(t.split()) for t in texts], by_name=by_name,
                                root=tmp_path, embedder=FakeEmbedder())

    assert ingest.ingest(listing, dry_run=True) == "1 new sittings: DR 2024-03-05"
    summary = run()
    assert summary.startswith("1 new sittings (2 speeches); 1 extracts, 1 enriched; chunks 1 to 1 indexed")

    con = index.connect(tmp_path / "index.db")
    row = index.rows(con, [1])[0]
    assert row.unit == "DR-2024-03-05-001" and row.act == "265"
    assert row.note.startswith("Summary (AI): The minister moved the employment bill.")
    assert [tuple(r) for r in con.execute("SELECT name, party FROM speakers WHERE chunk = 1 ORDER BY name")] == \
        [("Tuan A", ""), ("Tuan B", "DAP")]
    for variant in ("h", "hn"):
        assert index.vector_count("0.6b", variant, tmp_path) == 2
    [record] = [json.loads(line) for line in open(enrich.ENRICHED, encoding="utf-8")]
    assert [c["promise"] for c in record["commitments"]] == ["Raise the minimum wage next year"]
    assert record["dropped"]["commitments_not_real"] == 1
    assert "DR,2024-03-05" in hansard.REPORT_OUT.read_text(encoding="utf-8")

    assert run() == "0 new sittings, nothing to index"
