import json
from types import SimpleNamespace as NS

from parlimen import enrich, llm_rerank


class FakeClient:
    def __init__(self, text, stop_reason="end_turn"):
        self.text, self.stop_reason, self.sent = text, stop_reason, []
        self.messages = self

    def create(self, **kw):
        self.sent.append(kw)
        return NS(content=[NS(type="text", text=self.text)], stop_reason=self.stop_reason,
                  usage=NS(input_tokens=100, output_tokens=10))


def test_order_keeps_valid_numbers_once_then_the_rest_in_fused_order():
    assert llm_rerank.order([3, 3, 9, 0, True, 1], 4) == [2, 0, 1, 3]


def test_scores_follow_the_model_ranking(monkeypatch):
    monkeypatch.setattr(enrich, "_log", lambda *a: 0.001)
    client = FakeClient(json.dumps({"ranking": [2, 3, 1]}))
    r = llm_rerank.HaikuReranker(client=client)
    scores = r.scores("Apakah hukuman?", ["a", "b", "c"])
    assert sorted(range(3), key=lambda i: -scores[i]) == [1, 2, 0]
    assert "[3]\nc" in client.sent[0]["messages"][0]["content"] and r.usd == 0.001


def test_a_cut_off_answer_keeps_the_fused_order(monkeypatch):
    monkeypatch.setattr(enrich, "_log", lambda *a: 0.0)
    r = llm_rerank.HaikuReranker(client=FakeClient('{"ranking": [2', stop_reason="max_tokens"))
    assert r.scores("q", ["a", "b"]) == [2.0, 1.0] and r.failures == 1


def test_one_passage_needs_no_call():
    assert llm_rerank.HaikuReranker(client=None).scores("q", ["a"]) == [0.0]
