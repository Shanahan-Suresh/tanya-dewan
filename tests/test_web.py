"""The site over the small records of test_records.py and the index of test_search.py: no models,
no network."""
import json
import sqlite3

import fakeredis
import pytest
from fastapi.testclient import TestClient

from parlimen.answer import Answer, Source
from parlimen.index import db_path
from parlimen.web.app import create_app, question_lang
from parlimen.web.limits import Limits

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
    limits = Limits(fakeredis.FakeRedis(decode_responses=True), hourly=3, daily_usd=0.001)
    return TestClient(create_app(recs, usable_from_any_thread(s), fake_answer, tmp_path / "corrections.jsonl",
                                 limits=limits, question_log=tmp_path / "questions.jsonl", site_url="https://example.my"))


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


def test_a_visitor_past_the_hourly_limit_is_refused_with_a_reason(client):
    for _ in range(3):
        assert client.post("/api/ask", json={"question": "hours of employment"}).status_code == 200
    r = client.post("/api/ask", json={"question": "hours of employment"})
    assert r.status_code == 429 and "3 questions in the last hour" in r.json()["error"]
    client.cookies.set("hl", "ms")
    assert "3 soalan" in client.post("/api/ask", json={"question": "x"}).json()["error"]


def test_the_visitor_key_holds_no_address_and_expires_with_its_hour():
    r = fakeredis.FakeRedis(decode_responses=True)
    lim = Limits(r, hourly=1, clock=lambda: 1_800_000_000)
    assert lim.take("203.0.113.9") and not lim.take("203.0.113.9") and lim.take("198.51.100.1")
    keys = [k for k in r.keys("q:*")]
    assert keys and not any("203.0.113.9" in k for k in keys)
    assert all(0 < r.ttl(k) <= 3600 for k in keys)


def test_past_the_budget_the_page_gets_passages_and_no_answer(client, tmp_path):
    first = client.post("/api/ask", json={"question": "hours of employment"}).json()
    assert first["answer"] and not first["budget_out"]
    second = client.post("/api/ask", json={"question": "hours of employment"}).json()
    assert second["budget_out"] and second["answer"] == "" and second["sources"] == [] and second["passages"]
    log = [json.loads(line) for line in open(tmp_path / "questions.jsonl", encoding="utf-8")]
    assert [x["answered"] for x in log] == [True, False]
    assert set(log[0]) == {"at", "question", "lang", "filters", "answered", "usd", "ms"}


def test_a_draft_sitting_is_marked_on_its_pages(client):
    assert "Unrevised draft" in client.get("/hansard/DR/2024-05-02").text
    assert "Unrevised draft" in client.get("/debate/DR-2024-05-02-001").text
    assert "Unrevised draft" not in client.get("/hansard/DR/2022-03-01").text
    assert "unrevised draft" in client.get("/hansard?parliament=15").text


def test_robots_and_sitemaps_list_the_record_pages(client):
    robots = client.get("/robots.txt").text
    assert "Disallow: /api/" in robots and "Sitemap: https://example.my/sitemap.xml" in robots
    index = client.get("/sitemap.xml").text
    assert "https://example.my/sitemap-law.xml" in index and "https://example.my/sitemap-hansard-2024.xml" in index
    assert "<loc>https://example.my/law/265/BI</loc>" in client.get("/sitemap-law.xml").text
    year = client.get("/sitemap-hansard-2024.xml").text
    assert "/hansard/DR/2024-05-02</loc>" in year and "/debate/DR-2024-05-02-001</loc>" in year
    assert client.get("/sitemap-nothing.xml").status_code == 404


def test_pages_carry_share_previews_and_the_form_is_not_indexed(client):
    page = client.get("/law/265/BI").text
    assert '<meta property="og:title" content="' in page and 'content="https://example.my/static/og.png"' in page
    assert 'content="https://example.my/law/265/BI"' in page
    assert 'name="robots" content="noindex"' in client.get("/correction").text
    assert 'name="robots"' not in page


def test_a_question_while_the_index_loads_gets_a_wait_message(client):
    client.app.state.engine.warmed = False
    r = client.post("/api/ask", json={"question": "hours of employment"})
    assert r.status_code == 503 and r.headers["retry-after"] == "60" and "still loading" in r.json()["error"]
    assert client.app.state.limits.r.keys("q:*") == []  # a refused question does not count


def stream_events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_ask_stream_sends_stages_then_the_answer_so_far_then_the_whole_body(recs, tmp_path):  # noqa: F811
    s = build(tmp_path / "index")
    s.search = lambda q, f=None, **kw: type(s).search(s, q, f, mode="hybrid", on_stage=kw.get("on_stage"))

    def streaming_answer(question, passages, lang, on_text=None):
        if on_text:
            on_text("Forty-five hours a week.[1]")
        return fake_answer(question, passages, lang)

    limits = Limits(fakeredis.FakeRedis(decode_responses=True), hourly=3, daily_usd=1)
    c = TestClient(create_app(recs, usable_from_any_thread(s), streaming_answer, tmp_path / "c.jsonl",
                              limits=limits, question_log=tmp_path / "q.jsonl"))
    r = c.post("/api/ask/stream", json={"question": "hours of employment", "kind": "law"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = stream_events(r.text)
    stages = [(d["name"], d["hits"] is None) for n, d in events if n == "stage"]
    assert stages == [("bm25", True), ("bm25", False), ("dense", True), ("dense", False),
                      ("fused", True), ("fused", False), ("answer", True)]
    assert ("text", {"text": "Forty-five hours a week.[1]"}) in events
    name, body = events[-1]
    assert name == "done" and body["answer"].startswith("Forty-five hours") and body["sources"][0]["n"] == 1


def test_ask_stream_reports_refusals_as_an_error_event(client):
    events = stream_events(client.post("/api/ask/stream", json={"question": " "}).text)
    assert events == [("error", {"error": "empty question", "status": 400})]


def test_replay_serves_a_saved_answer_with_no_model(recs, tmp_path):  # noqa: F811
    saved = {"answer": {"question": "q", "answer": "Line one.[1]\n\nLine two.[1]", "sources": [], "passages": [],
                        "stages": [{"name": "bm25", "hits": 3, "ms": 1}], "budget_out": False}}
    path = tmp_path / "saved.json"
    path.write_text(json.dumps(saved), encoding="utf-8")
    c = TestClient(create_app(recs, replay=path, question_log=tmp_path / "q.jsonl"))
    assert c.post("/api/ask", json={"question": "anything"}).json()["answer"].startswith("Line one")
    events = stream_events(c.post("/api/ask/stream", json={"question": "anything"}).text)
    assert [n for n, _ in events] == ["stage", "stage", "stage", "text", "done"]


def test_a_list_page_asked_by_htmx_returns_only_its_results_block(client):
    full = client.get("/questions?q=rice")
    part = client.get("/questions?q=rice", headers={"HX-Request": "true"})
    assert "<html" in full.text and 'id="results"' in full.text and 'hx-target="#results"' in full.text
    assert "<html" not in part.text and "<form" not in part.text and "When will the rice subsidy arrive?" in part.text
    assert part.headers["vary"] == "HX-Request"
    for path in ("/commitments", "/law?q=employment", "/topic/sabah-and-sarawak"):
        assert "<html" not in client.get(path, headers={"HX-Request": "true"}).text, path
        assert "<html" in client.get(path).text, path
    # Without the header every filter form is a plain GET form.
    assert 'method="get"' in full.text and 'action="/questions"' in full.text


def test_every_page_loads_only_its_own_assets_and_carries_the_shell(client):
    import re
    for path in ("/", "/law/265/BI", "/debate/DR-2024-05-02-001", "/mp/hannah-yeoh-tseow-suan", "/questions"):
        text = client.get(path).text
        assert not re.findall(r'(?:src|href)="https?://(?!lom\.example|www\.parlimen)[^"]*\.(?:js|css|woff2?)"', text), path
        assert 'class="skip"' in text and 'id="more-sheet"' in text and "Not legal advice." in text, path
        assert 'href="/about"' in text and "/correction?back=" in text, path
    assert 'src="/static/htmx.min.js"' in client.get("/").text


def test_the_debate_page_has_a_speaker_map_and_the_member_page_a_heat_grid(client):
    d = client.get("/debate/DR-2024-05-02-001").text
    assert 'id="smap"' in d and 'src="/static/debate.js"' in d and 'data-seq="2"' in d
    assert 'class="stepper"' not in d
    m = client.get("/mp/hannah-yeoh-tseow-suan").text
    assert "heat-grid-missing" not in m  # the heat grid shows only with activity; its markup is the table.hm
    assert 'class="avatar"' in m


def test_the_ask_page_prefills_q_and_never_runs_it(client):
    page = client.get("/?q=rice+prices").text
    assert 'value="rice prices"' in page and 'id="answer" hidden' in page
    assert 'name="parliament"' in page and 'name="date_from"' in page and "Copy link" in page
