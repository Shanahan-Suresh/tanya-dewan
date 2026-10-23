from parlimen import enrich


def speech(seq, text, topic="PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN", question_no="", label=None):
    return {"chamber": "DR", "date": "2025-10-29", "parliament": 15, "seq": seq, "topic": topic,
            "question_no": question_no, "label": label or f"Speaker {seq} [Seat {seq}]", "name": f"Speaker {seq}",
            "seat": f"Seat {seq}", "role": "", "senator": False, "text": text}


def test_question_stays_with_its_answers_and_items_do_not_mix():
    long = "x" * 4000
    units = enrich.make_units([
        speech(1, long, question_no="1"), speech(2, long, question_no="1"),
        speech(3, "y" * 100, question_no="2"),
        speech(4, "z" * 100, topic="RANG UNDANG-UNDANG KEWANGAN 2025"),
    ])
    assert [[s["seq"] for s in u["speeches"]] for u in units] == [[1, 2], [3], [4]]
    assert units[2]["topic"] == "RANG UNDANG-UNDANG KEWANGAN 2025"
    assert [s["id"] for s in units[0]["speeches"]] == ["S1", "S2"]


def test_long_speech_goes_in_parts_with_their_own_ids():
    text = "\n".join(["kata " * 400] * 8)  # 8 lines of 2,000 characters
    [unit, *rest] = enrich.make_units([speech(1, text, topic="BAJET")])
    parts = [s for u in [unit, *rest] for s in u["speeches"]]
    assert len(parts) == 2 and {s["seq"] for s in parts} == {1}
    assert parts[1]["label"].endswith("(continued, part 2 of 2)")


def test_schema_limits_speech_ids_to_the_extract():
    s = enrich.schema(["S1", "S2"])
    qa = s["properties"]["qa_pairs"]["items"]["properties"]
    assert qa["question_speech"]["enum"] == ["S1", "S2"]
    assert s["properties"]["commitments"]["items"]["properties"]["speech"]["enum"] == ["S1", "S2"]


def test_finish_drops_quotes_figures_and_entities_not_in_the_text():
    [unit] = enrich.make_units([
        speech(1, "Berapakah jumlah gelandangan?", question_no="1"),
        speech(2, "Seramai 1,200 orang. Kerajaan akan membina\npusat transit baharu pada tahun 2026.",
               question_no="1", label="Menteri [Datuk Seri Dr. Zaliha binti Mustafa]"),
    ])
    rec = enrich.finish(unit, {
        "summary_en": "s", "summary_ms": "s", "topics": ["housing"],
        "entities": [{"name": "Kuala Lumpur", "type": "place"}],
        "qa_pairs": [{"question_speech": "S1", "answer_speech": "S2", "question": "q", "answer": "a",
                      "figures": [{"value": "1,200", "meaning": "homeless"}, {"value": "1,300", "meaning": "x"}]}],
        "commitments": [
            {"speech": "S2", "quote": "akan membina pusat transit baharu", "promise": "p", "deadline": "2026", "amount": ""},
            {"speech": "S1", "quote": "akan membina pusat transit baharu", "promise": "p", "deadline": "", "amount": ""},
        ],
    })
    assert [c["speaker"]["seq"] for c in rec["commitments"]] == [2]
    assert rec["qa_pairs"][0]["answer_by"]["label"] == "Menteri [Datuk Seri Dr. Zaliha binti Mustafa]"
    assert [f["value"] for f in rec["qa_pairs"][0]["figures"]] == ["1,200"]
    assert rec["dropped"] == {"commitments": 1, "commitments_not_real": 0, "figures": 1, "entities": 1}
