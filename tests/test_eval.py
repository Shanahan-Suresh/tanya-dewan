from parlimen import evalset, evaluate
from parlimen.index import Row


def row(i, kind, act="", section="", unit="", seqs=(0, 0), lang="BI"):
    return Row(i, kind, "", 0, act, lang, section, "DR", "", 15, unit, seqs[0], seqs[1], 0, 0, 100, "", "", "")


def test_gold_matches_either_language_and_overlapping_speeches():
    law_bi, law_bm = row(1, "law", "265", "60A"), row(2, "law", "265", "60A", lang="BM")
    g = evalset.gold_of(law_bi)
    assert evalset.matches(law_bm, g) and not evalset.matches(row(3, "law", "265", "60"), g)
    deb = row(4, "debate", unit="DR-2024-03-12-007", seqs=(40, 45))
    g = evalset.gold_of(deb)
    assert g == {"kind": "debate", "sitting": "DR-2024-03-12", "seqs": [40, 45]}
    assert evalset.matches(row(5, "debate", unit="DR-2024-03-12-008", seqs=(45, 50)), g)
    assert not evalset.matches(row(6, "debate", unit="DR-2024-03-12-008", seqs=(46, 50)), g)
    assert not evalset.matches(row(7, "debate", unit="KK-2024-03-12-001", seqs=(40, 45)), g)


def test_score_ranks_the_first_gold_hit():
    gold = [{"kind": "law", "act": "1", "section": "2"}]
    ranked = [row(1, "law", "1", "9"), row(2, "law", "1", "2"), row(3, "law", "1", "2", lang="BM")]
    m = evaluate.score(ranked, gold)
    assert m["recall@5"] == 1.0 and m["mrr@10"] == 0.5
    assert evaluate.score(ranked[:1], gold)["recall@10"] == 0.0
