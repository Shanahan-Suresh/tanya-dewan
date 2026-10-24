"""The site over the small records of test_records.py and the index of test_search.py: no models,
no network."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from parlimen.answer import Answer, Source
from parlimen.index import db_path
from parlimen.web.app import create_app, question_lang

from tests.test_records import recs  # noqa: F401
from tests.test_search import build


def usable_from_any_thread(searcher):
    searcher.con = sqlite3.connect(db_path(searcher.root), check_same_thread=False)
    searcher.con.row_factory = sqlite3.Row
    return searcher


def fake_answer(question, passages, lang):
    return Answer(f"Forty-five hours a week.[1]\n\nnot advice ({lang})",
                  [Source(1, passages[0].cite, ["An employee shall not work more than forty-five hours."], index=0)],
                  "end_turn", 0.0012)


@pytest.fixture
def client(recs, tmp_path):  # noqa: F811
    s = build(tmp_path / "index")
    s.con.execute("UPDATE chunks SET seq_first = 1, seq_last = 2 WHERE unit = 'DR-2022-03-01-001'")
    s.con.commit()
    s.search = lambda q, f=None, **kw: type(s).search(s, q, f, mode="hybrid")
    return TestClient(create_app(recs, usable_from_any_thread(s), fake_answer, tmp_path / "corrections.jsonl"))


def test_question_language():
    assert question_lang("Bolehkah majikan memotong gaji saya?") == "ms"
    assert question_lang("Can my employer cut my salary?") == "en"


def test_ask_returns_the_answer_with_linked_sources_and_stages(client):
    r = client.post("/api/ask", json={"question": "hours of employment", "kind": "law"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].startswith("Forty-five hours") and body["lang"] == "en"
    [src] = body["sources"]
    assert src["url"] == "/law/265/BI#s-60a"
    assert src["pdf"] == "https://lom.example/265-bi.pdf#page=80"
    assert [s["name"] for s in body["stages"]] == ["bm25", "dense", "fused"]
    assert body["filters"] == "kind=law"


def test_ask_links_a_debate_passage_to_its_speech(client):
    body = client.post("/api/ask", json={"question": "employment bill wages", "kind": "debate"}).json()
    p = body["passages"][0]
    assert p["url"] == "/debate/DR-2022-03-01-001#seq-1"
    assert p["pdf"] == "https://www.parlimen.gov.my/files/hindex/pdf/DR-01032022.pdf#page=10"


def test_ask_refuses_an_empty_or_long_question(client):
    assert client.post("/api/ask", json={"question": " "}).status_code == 400
    assert client.post("/api/ask", json={"question": "x" * 501}).status_code == 400


def test_act_page_has_anchored_sections_both_languages_and_its_bill_debates(client):
    r = client.get("/law/265/BI")
    assert r.status_code == 200
    assert 'id="s-60a"' in r.text and "Hours of work" in r.text
    assert 'href="/law/265/BM"' in r.text
    assert 'href="/debate/DR-2022-03-01-001"' in r.text
    assert "not legal advice" in r.text
    assert client.get("/law/265", follow_redirects=False).headers["location"] == "/law/265/BI"
    assert client.get("/law/265/XX").status_code == 404


def test_debate_page_shows_summary_beside_verbatim_with_labels(client):
    r = client.get("/debate/DR-2024-05-02-001")
    assert r.status_code == 200
    assert "Summary (AI)" in r.text and "A question on the rice subsidy." in r.text
    assert 'id="seq-2"' in r.text and "Kerajaan akan menyalurkan RM50 juta" in r.text
    assert "When will the rice subsidy arrive?" in r.text  # the question-answer card
    assert "menyalurkan RM50 juta sebelum Disember 2024" in r.text  # the commitment quote
    assert 'href="/mp/hannah-yeoh-tseow-suan"' in r.text
    assert "DR-02052024.pdf#page=5" in r.text
    assert "Report a mistake" in r.text


def test_malay_interface_follows_the_cookie(client):
    r = client.get("/hl/ms?next=/debate/DR-2024-05-02-001", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/debate/DR-2024-05-02-001"
    client.cookies.set("hl", "ms")
    r = client.get("/debate/DR-2024-05-02-001")
    assert "Ringkasan (AI)" in r.text and "Soalan tentang subsidi beras." in r.text


def test_record_lists_and_filters(client):
    assert "Pay RM50 million of rice subsidy" in client.get("/commitments?ministry=Pertanian dan Keterjaminan Makanan").text
    assert "Pay RM50 million" not in client.get("/commitments?year=2022").text
    assert "When will the rice subsidy arrive?" in client.get("/questions?q=rice").text
    assert "Hannah Yeoh" in client.get("/mp/hannah-yeoh-tseow-suan").text
    assert "DAP" in client.get("/mp/lim-guan-eng").text
    assert "KERJA (PINDAAN) 2022" in client.get("/bill/kerja-pindaan-2022").text
    assert "Sabah and Sarawak" in client.get("/topic/sabah-and-sarawak").text
    assert "EMPLOYMENT ACT 1955" in client.get("/law?q=employment").text
    for path in ("/", "/hansard", "/hansard/DR/2022-03-01", "/mp", "/bills", "/topics", "/about", "/law"):
        assert client.get(path).status_code == 200, path
    for path in ("/debate/nope", "/mp/nope", "/bill/nope", "/topic/nope", "/hansard/DR/1999-01-01"):
        assert client.get(path).status_code == 404, path


def test_a_correction_is_saved(client, tmp_path):
    r = client.post("/correction", data={"record": "DR-2024-05-02-001-c1", "back": "/debate/DR-2024-05-02-001",
                                         "text": "The amount is RM5 million.", "contact": ""})
    assert r.status_code == 200 and "Thank you" in r.text
    [row] = [json.loads(x) for x in (tmp_path / "corrections.jsonl").read_text(encoding="utf-8").splitlines()]
    assert row["record"] == "DR-2024-05-02-001-c1" and row["text"] == "The amount is RM5 million."


class CountingEmbedder:
    def __init__(self):
        self.queries = self.unloads = 0

    def query(self, question):
        self.queries += 1

    def unload(self):
        self.unloads += 1


def test_a_cpu_engine_warms_the_embedder_and_keeps_it(client):
    engine = client.app.state.engine
    assert engine.device == "cpu"
    engine.searcher._vectors = None
    engine.searcher.embedder = emb = CountingEmbedder()
    engine.warm()
    engine.run(lambda s: None)  # the worker runs one job at a time, so the warm is done
    assert engine.warmed and engine.searcher._vectors is not None and emb.queries == 1
    assert client.get("/api/health").json() == {"ok": True, "searcher": True, "warmed": True}
    assert not engine.unload_if_idle(engine.last_used + 10_000) and emb.unloads == 0


def test_a_gpu_engine_leaves_the_embedder_cold_and_unloads_it_when_idle(client):
    engine = client.app.state.engine
    engine.device = "cuda"
    engine.searcher.embedder = emb = CountingEmbedder()
    engine.warm()
    engine.run(lambda s: None)
    assert engine.warmed and emb.queries == 0
    assert not engine.unload_if_idle(engine.last_used + 1)
    assert engine.unload_if_idle(engine.last_used + 10_000) and emb.unloads == 1
