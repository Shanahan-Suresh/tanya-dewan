import numpy as np

from parlimen import index, search
from parlimen.chunk import Chunk


class FakeEmbedder:
    """Bag of words over a tiny vocabulary, so dense search ranks by shared words."""
    vocab = ["employment", "wages", "hours", "rice", "subsidy", "flood", "section", "kerja"]

    def _vec(self, text):
        words = text.lower().split()
        v = np.array([sum(w.strip(".,:") == t for w in words) for t in self.vocab], dtype=np.float32) + 0.01
        return v / np.linalg.norm(v)

    def documents(self, texts, batch_size=32):
        return np.stack([self._vec(t) for t in texts])

    def query(self, question, task=""):
        return self._vec(question)


def speaker(name, party, tokens=40):
    return {"name": name, "seat": "S", "party": party, "role": "", "tokens": tokens}


def build(tmp_path):
    chunks = [
        Chunk("law", "law:265:BI:60A", 0, "EMPLOYMENT ACT 1955 (Act 265), section 60A: Hours of work.",
              "60A. Employment hours are limited, subject to section 60C.", 10, act="265", lang="BI",
              section="60A", date="2023-01-01"),
        Chunk("law", "law:265:BI:60C", 0, "EMPLOYMENT ACT 1955 (Act 265), section 60C: Shift work.",
              "60C. Shift work may pass the hours.", 8, act="265", lang="BI", section="60C", date="2023-01-01"),
        Chunk("debate", "debate:DR-2022-03-01-001", 0, "Dewan Rakyat, 2022-03-01. Bill for the EMPLOYMENT ACT 1955 (Act 265).",
              "Menteri: The employment bill raises wages and cuts hours.", 10, note="Summary (AI): wages.",
              act="265", chamber="DR", date="2022-03-01", parliament=14, unit="DR-2022-03-01-001",
              speakers=[speaker("Menteri A", "PKR")], topics=["labour and jobs"]),
        Chunk("debate", "debate:DR-2024-05-02-003", 0, "Dewan Rakyat, 2024-05-02.",
              "Tuan B: The rice subsidy must reach flood victims.", 9, chamber="DR", date="2024-05-02",
              parliament=15, unit="DR-2024-05-02-003",
              speakers=[speaker("Tuan B", "DAP"), speaker("Tuan C", "PAS", tokens=2)], topics=["food prices"]),
        Chunk("debate", "debate:DR-2024-05-02-003", 1, "Dewan Rakyat, 2024-05-02.",
              "Tuan B (continued): Flood victims wait for the rice subsidy.", 9, chamber="DR", date="2024-05-02",
              parliament=15, unit="DR-2024-05-02-003", speakers=[speaker("Tuan B", "DAP")], topics=["food prices"]),
    ]
    index.build(chunks, tmp_path / "index.db")
    index.embed("0.6b", "hn", tmp_path, embedder=FakeEmbedder())
    return search.Searcher(tmp_path, variant="hn", embedder=FakeEmbedder(), reranker=None, rerank_size=None)


def test_keyword_query_drops_question_words_in_both_languages():
    assert search.keyword_query("Apakah hukuman bagi the employer?") == '"hukuman" OR "employer"'


def test_merge_drops_overlap_and_the_continued_label():
    a = "Tuan B: One. Two. Three."
    assert search.merge_texts(a, "Tuan B (continued): Three. Four.") == "Tuan B: One. Two. Three. Four."
    assert search.merge_texts("Para one.", "Para two.") == "Para one.\n\nPara two."
    part = "Tuan B (continued, part 2 of 2): "
    assert search.merge_texts(part + "One. Two.", part + "Two. Three.") == part + "One. Two. Three."


def test_search_ranks_merges_neighbours_and_follows_cross_references(tmp_path):
    s = build(tmp_path)
    t = s.search("hours of employment", search.Filters(kind="law"), mode="hybrid")
    assert t.ranked[0] == 0
    first, *rest = t.passages
    assert first.section == "60A" and first.cite.startswith("Act 265, s. 60A")
    assert any(p.section == "60C" for p in rest)
    t = s.search("rice subsidy flood", mode="hybrid", xrefs=0)
    [p] = [p for p in t.passages if p.unit == "DR-2024-05-02-003"]
    assert p.ids == [3, 4] and p.text == ("Tuan B: The rice subsidy must reach flood victims. "
                                          "Flood victims wait for the rice subsidy.")


def test_filters(tmp_path):
    s = build(tmp_path)
    ids = lambda f: set(np.flatnonzero(s.mask(f)).tolist())
    assert ids(search.Filters(party="dap")) == {3, 4}
    assert ids(search.Filters(party="PAS")) == set()  # an interjection does not count
    assert ids(search.Filters(speaker="Menteri")) == {2}
    assert ids(search.Filters(topic="food prices", parliament=15)) == {3, 4}
    assert ids(search.Filters(date_from="2022-01-01", date_to="2022-12-31")) == {2}  # law is not dated by sitting
    assert ids(search.Filters(kind="law", date_from="2023-01-01")) == {0, 1}
    assert [d["unit"] for d in s.debates_for_act("265")] == ["DR-2022-03-01-001"]
