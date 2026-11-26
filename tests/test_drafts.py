"""The draft flag and the re-check of draft sittings: fake downloads, parses and processing, a small
index; no network, no model."""
import json
from dataclasses import asdict

import pytest

from parlimen import drafts, enrich, fetch, hansard, index
from parlimen.chunk import Chunk
from parlimen.search import Filters, Searcher

from test_search import FakeEmbedder


def sitting(date, chamber="DR"):
    from parlimen.sittings import Sitting
    return Sitting(date, chamber, 15, "Penggal Kelima", "Mesyuarat Ketiga", f"/files/hindex/pdf/{chamber}-{date}.pdf",
                   "archive")


def speech(date, seq, text):
    return hansard.Speech("DR", date, 15, seq, 1, 1, "1010", "SUBSIDI DIESEL", "", "Tuan A [Bagan]", "", "Tuan A",
                          "Bagan", False, text)


def chunk(date, text):
    return Chunk("debate", f"debate:DR-{date}-001", 0, f"Dewan Rakyat, {date}.", text, 3, chamber="DR", date=date,
                 parliament=15, unit=f"DR-{date}-001", topics=["energy"],
                 speakers=[{"name": "Tuan A", "seat": "Bagan", "party": "DAP", "role": "", "tokens": 30}])


@pytest.fixture
def files(tmp_path, monkeypatch):
    for mod, name in [(hansard, "SPEECHES_OUT"), (hansard, "REPORT_OUT"), (enrich, "UNITS"), (enrich, "RAW"),
                      (enrich, "ENRICHED"), (drafts, "OUT")]:
        monkeypatch.setattr(mod, name, tmp_path / getattr(mod, name).name)
    monkeypatch.setattr(fetch, "cache_path", lambda url: tmp_path / "cache" / (url.rsplit("/", 1)[-1]))
    monkeypatch.setattr(fetch, "_wait_turn", lambda host: None)
    monkeypatch.setattr(drafts, "is_draft", lambda data: b"belum disemak" in (data if isinstance(data, bytes)
                                                                              else data.read_bytes()))
    (tmp_path / "cache").mkdir()
    return tmp_path


def test_the_marker_is_read_from_page_one_text():
    assert drafts.MARK.search("Naskhah belum disemak\n\nBil. 50")
    assert drafts.MARK.search("NASKHAH BELUM  DISEMAK")
    assert not drafts.MARK.search("Naskhah yang telah disemak")


def test_scan_flags_only_the_draft_pdfs(files):
    old, new = sitting("2024-03-05"), sitting("2026-10-22")
    fetch.cache_path(old.url).write_bytes(b"%PDF revised text")
    fetch.cache_path(new.url).write_bytes(b"%PDF Naskhah belum disemak")
    assert drafts.scan([old, new, sitting("2026-10-23")], today="2026-11-26") == {"sittings": 2, "drafts": 1}
    rows = drafts.read()
    assert rows[("DR", "2026-10-22")]["draft"] == "1" and rows[("DR", "2024-03-05")]["draft"] == "0"


def test_replace_rows_keeps_order_and_appends_when_nothing_matched(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text("".join(json.dumps({"k": k}) + "\n" for k in "abc"), encoding="utf-8")
    drafts.replace_rows(p, lambda r: r["k"] != "b", [{"k": "B1"}, {"k": "B2"}])
    assert [json.loads(line)["k"] for line in open(p)] == ["a", "B1", "B2", "c"]
    drafts.replace_rows(p, lambda r: True, [{"k": "d"}])
    assert [json.loads(line)["k"] for line in open(p)][-1] == "d"


def test_retire_takes_a_sitting_out_of_search_without_moving_ids(tmp_path):
    index.build([chunk("2026-10-21", "harga diesel naik"), chunk("2026-10-22", "subsidi diesel bersasar")],
                tmp_path / "index.db")
    index.embed("0.6b", "h", tmp_path, embedder=FakeEmbedder())
    assert index.retire("DR", "2026-10-22", tmp_path / "index.db") == 1
    s = Searcher(tmp_path, embedder=FakeEmbedder(), rerank_size=None)
    assert list(s.live) == [True, False]
    assert all(h.id == 0 for h in s.bm25("diesel", Filters()))
    assert all(h.id == 0 for h in s.dense("subsidi diesel", Filters()))
    assert s.con.execute("SELECT COUNT(*) FROM speakers WHERE chunk = 1").fetchone()[0] == 0
    start, end = index.append([chunk("2026-10-22", "subsidi diesel bersasar, teks disemak")], tmp_path / "index.db")
    assert (start, end) == (2, 3)


def test_recheck_processes_only_a_changed_draft_and_resumes_from_its_mark(files):
    same, changed, old = sitting("2026-10-21"), sitting("2026-10-22"), sitting("2025-01-10")
    for s in (same, changed, old):
        fetch.cache_path(s.url).write_bytes(b"%PDF Naskhah belum disemak " + s.date.encode())
    drafts.scan([same, changed, old], today="2026-11-19")
    index.build([chunk("2026-10-21", "harga diesel"), chunk("2026-10-22", "subsidi diesel")], files / "index.db")
    enrich._append(hansard.SPEECHES_OUT, [asdict(speech("2026-10-21", 1, "Harga diesel.")),
                                          asdict(speech("2026-10-22", 1, "Lama."))])
    enrich._append(enrich.UNITS, enrich.make_units([asdict(speech("2026-10-21", 1, "Harga diesel."))]) +
                   enrich.make_units([asdict(speech("2026-10-22", 1, "Lama."))]))
    enrich._append(enrich.RAW, [{"unit": "DR-2026-10-22-001", "prompt": enrich.PROMPT_VERSION, "result": {}}])
    enrich._append(enrich.ENRICHED, [{"unit": "DR-2026-10-21-001"}, {"unit": "DR-2026-10-22-001"}])
    hansard.REPORT_OUT.write_text(",".join(hansard.REPORT_FIELDS) + "\nDR,2026-10-21,,,1,,,,,,,\nDR,2026-10-22,,,1,,,,,,,\n",
                                  encoding="utf-8")
    fetched, processed = [], []

    def download(url):
        fetched.append(url)
        if "2026-10-22" in url:
            return b"%PDF revised"
        return fetch.cache_path(url).read_bytes()

    def parse(s):
        sp = [speech(s.date, 1, "Teks disemak."), speech(s.date, 2, "Ya.")]
        return sp, hansard.Report("DR", s.date, speeches=2)

    def process(fresh):
        processed.append(fresh)
        return "1 extracts, 1 enriched"

    summary = drafts.recheck([same, changed, old], download, process, parse, today="2026-11-26", root=files)
    assert summary == "2 draft sittings fetched again: 1 changed (DR 2026-10-22 (now revised)); 1 extracts, 1 enriched"
    assert len(fetched) == 2  # the 2025 draft is past RECHECK_DAYS
    assert processed == [{"DR-2026-10-22-001": 1}]  # only answers after raw line 1 count
    assert fetch.cache_path(changed.url).read_bytes() == b"%PDF revised"
    rows = drafts.read()
    assert rows[("DR", "2026-10-22")]["draft"] == "0" and rows[("DR", "2026-10-22")]["redo_from"] == ""
    assert rows[("DR", "2026-10-21")]["checked"] == "2026-11-26"
    texts = [json.loads(line)["text"] for line in open(hansard.SPEECHES_OUT, encoding="utf-8")]
    assert texts == ["Harga diesel.", "Teks disemak.", "Ya."]
    assert [json.loads(line)["unit"] for line in open(enrich.ENRICHED)] == ["DR-2026-10-21-001"]
    assert "DR,2026-10-22,0,,2," in hansard.REPORT_OUT.read_text(encoding="utf-8")
    con = index.connect(files / "index.db")
    assert [r[0] for r in con.execute("SELECT kind FROM chunks ORDER BY id")] == ["debate", "retired"]


def test_a_stopped_recheck_resumes_without_fetching_again(files):
    s = sitting("2026-10-22")
    fetch.cache_path(s.url).write_bytes(b"%PDF revised")
    drafts.write({("DR", "2026-10-22"): {"chamber": "DR", "date": "2026-10-22", "draft": "0", "sha1": "x",
                                         "checked": "2026-11-26", "redo_from": "7"}})
    enrich._append(enrich.UNITS, [{"id": "DR-2026-10-22-001", "chamber": "DR", "date": "2026-10-22"}])
    processed = []
    out = drafts.recheck([s], download=lambda url: pytest.fail("fetched again"),
                         process=lambda fresh: processed.append(fresh) or "done", today="2026-11-27", root=files)
    assert out.endswith("; done") and processed == [{"DR-2026-10-22-001": 7}]
    assert drafts.read()[("DR", "2026-10-22")]["redo_from"] == ""


def test_fresh_from_makes_an_old_answer_not_count(files):
    enrich._append(enrich.RAW, [{"unit": "DR-2026-10-22-001", "prompt": enrich.PROMPT_VERSION, "result": {"a": 1}},
                                {"unit": "DR-2026-10-21-001", "prompt": enrich.PROMPT_VERSION, "result": {"a": 2}}])
    assert set(enrich._done()) == {"DR-2026-10-22-001", "DR-2026-10-21-001"}
    assert set(enrich._done({"DR-2026-10-22-001": 2})) == {"DR-2026-10-21-001"}
