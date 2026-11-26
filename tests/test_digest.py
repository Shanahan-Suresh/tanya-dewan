"""The weekly digest over the small records of test_records.py, with a fake client: no network."""
import json
from types import SimpleNamespace

from parlimen import config, digest

from tests.test_records import recs  # noqa: F401


class FakeStream:
    def __init__(self, text):
        self.msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)],
                                   usage=SimpleNamespace(input_tokens=1000, output_tokens=200,
                                                         cache_read_input_tokens=0, cache_creation_input_tokens=0))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    def __init__(self, result):
        self.params = None
        self.messages = self
        self.text = json.dumps(result)

    def stream(self, **params):
        self.params = params
        return FakeStream(self.text)


def week(recs):  # noqa: F811
    return digest.gather(recs, ["agriculture and food"], "2024-04-29", "2024-05-03")


def test_gather_keeps_the_sector_and_the_week(recs):  # noqa: F811
    units = week(recs)
    assert [u["id"] for u in units] == ["DR-2024-05-02-001"]
    assert units[0]["qa"] and units[0]["commitments"]
    assert digest.gather(recs, ["health"], "2024-04-29", "2024-05-03") == []
    assert digest.gather(recs, ["agriculture and food"], "2024-06-01", "2024-06-07") == []


def test_prompt_carries_every_record_id(recs):  # noqa: F811
    units = week(recs)
    text = digest.prompt(units, "Agriculture", "2024-04-29", "2024-05-03")
    for i in ["DR-2024-05-02-001", units[0]["qa"][0]["id"], units[0]["commitments"][0]["id"]]:
        assert f"[{i}]" in text
    assert "Summary (AI): A question on the rice subsidy." in text


def test_unknown_ids_are_dropped_and_quotes_come_from_the_record(recs, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(config, "USAGE_LOG", tmp_path / "usage.jsonl")
    units = week(recs)
    c = units[0]["commitments"][0]
    fake = FakeClient({
        "headline": "Rice subsidy money promised.", "intro": "One question on rice.",
        "items": [{"title": "Rice subsidy", "body": "The minister promised RM50 million.", "ids": [c["id"], "DR-1999-01-01-001"]},
                  {"title": "Invented", "body": "Not in the record.", "ids": ["DR-1999-01-01-002"]}],
        "watch": [{"text": "RM50 million before December 2024", "ids": [c["id"]]}],
    })
    ans = digest.write(fake, units, "Agriculture", "2024-04-29", "2024-05-03")
    assert fake.params["model"] == digest.MODEL
    assert fake.params["output_config"]["format"]["schema"] == digest.SCHEMA
    d, dropped = digest.check(ans["result"], units)
    assert [it["title"] for it in d["items"]] == ["Rice subsidy"]
    assert d["items"][0]["ids"] == [c["id"]]
    assert "DR-1999-01-01-001" in dropped and "items: Invented" in dropped
    page = digest.render(d, units, "Agriculture", "2024-04-29", "2024-05-03", "http://site")
    assert "menyalurkan RM50 juta sebelum Disember 2024" in page
    assert f'href="http://site/debate/DR-2024-05-02-001#seq-{c["seq"]}"' in page
    assert "Invented" not in page and "Written by AI (Claude)" in page
