from types import SimpleNamespace as NS

from parlimen import answer
from parlimen.search import Passage


def passage(cite_act):
    return Passage([1], 1.0, "law", f"law:{cite_act}:BI:2", "header", "text", act=cite_act, lang="BI",
                   section="2", date="2023-01-01")


def test_citations_number_in_order_of_first_use():
    ps = [passage("1"), passage("2")]
    cite = lambda i, t: NS(document_index=i, cited_text=t)  # noqa: E731
    msg = NS(content=[NS(type="text", text="A holds.", citations=[cite(1, "  quote   b ")]),
                      NS(type="text", text=" B holds.", citations=[cite(0, "quote a"), cite(1, "quote b")]),
                      NS(type="text", text=" Done.", citations=None)])
    text, sources, dropped = answer.parse(msg, ps)
    assert text == "A holds.[1] B holds.[1][2]" and dropped == ["Done."]
    assert [(s.n, s.cite, s.quotes) for s in sources] == [
        (1, "Act 2, s. 2 (BI, as at 2023-01-01)", ["quote b"]), (2, "Act 1, s. 2 (BI, as at 2023-01-01)", ["quote a"])]


def test_a_debate_quote_carries_its_speakers_label():
    text = ("Tuan A [Seri Kembangan]: Bila jalan itu siap?\n\n"
            "Menteri Kerja Raya [Dato' Sri Alexander Nanta Linggi] (continued): Jalan itu siap pada 2026.")
    p = Passage([1], 1.0, "debate", "debate:DR-2024-01-01-001", "header", text, chamber="DR",
                date="2024-01-01", unit="DR-2024-01-01-001")
    at = text.index("Jalan itu")
    msg = NS(content=[NS(type="text", text="It opens in 2026.",
                         citations=[NS(document_index=0, cited_text="Jalan itu siap pada 2026.", start_char_index=at)])])
    _, sources, _ = answer.parse(msg, [p])
    assert sources[0].quotes == ["Menteri Kerja Raya [Dato' Sri Alexander Nanta Linggi]: Jalan itu siap pada 2026."]
    assert answer.speaker_at(text, 3) == "Tuan A [Seri Kembangan]"


def test_uncited_sentences_drop_but_lead_ins_and_abbreviations_stay():
    pieces = [("Under s. 60D of Act 265, ", []), ("the worker gets two days' wages", [1]),
              (". The same rule is in the Criminal Procedure Code. Overtime:\n- ", []),
              ("twice the hourly rate.", [2]), ("\n- Dr. Wee said otherwise.", [])]
    text, dropped = answer.keep_cited(pieces)
    assert text == "Under s. 60D of Act 265, the worker gets two days' wages[1]. Overtime:\n- twice the hourly rate.[2]"
    assert dropped == ["The same rule is in the Criminal Procedure Code.", "- Dr. Wee said otherwise."]


def test_the_referral_to_a_lawyer_stays_uncited():
    text, dropped = answer.keep_cited([("Rule.", [1]), (" Untuk kes anda sendiri, sila rujuk peguam.", [])])
    assert text == "Rule.[1] Untuk kes anda sendiri, sila rujuk peguam." and dropped == []


def test_an_answer_with_no_citation_stays_whole():
    assert answer.keep_cited([("The documents do not answer this.", [])]) == ("The documents do not answer this.", [])


def test_no_passages_still_carries_the_not_advice_line():
    a = answer.ask("Bolehkah saya?", [], lang="ms")
    assert a.text.endswith(answer.NOT_ADVICE_MS) and a.usd == 0.0
