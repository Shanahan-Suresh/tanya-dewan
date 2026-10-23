from parlimen import commit_check, enrich
from tests.test_enrich import speech


def test_window_marks_the_quote_across_line_breaks_and_case():
    text = "Mukadimah. " * 300 + "Kerajaan AKAN membina\npusat   transit baharu pada tahun 2026." + " Penutup." * 300
    w = commit_check.window(text, "akan membina pusat transit baharu")
    assert "<<AKAN membina\npusat   transit baharu>>" in w
    assert w.startswith("...") and w.endswith("...")
    assert len(w) < 2 * commit_check.WINDOW + 100


def test_window_keeps_a_short_speech_whole():
    w = commit_check.window("Kami akan mem-\nbina jambatan.", "akan mem-bina jambatan")
    assert w == "Kami <<akan mem-\nbina jambatan>>."


def test_finish_drops_commitments_judged_not_real_and_applies_fixes():
    [unit] = enrich.make_units([
        speech(1, "Kerajaan akan membina pusat transit pada 2026. Kami telah menyalurkan RM5 juta.",
               label="Menteri [Datuk A]"),
    ])
    res = {"summary_en": "s", "summary_ms": "s", "topics": [], "entities": [], "qa_pairs": [],
           "commitments": [
               {"speech": "S1", "quote": "akan membina pusat transit pada 2026", "promise": "build in 2025",
                "deadline": "2026", "amount": ""},
               {"speech": "S1", "quote": "telah menyalurkan RM5 juta", "promise": "give RM5 million",
                "deadline": "", "amount": "RM5 juta"},
           ]}
    record = {"commitments": [{"speaker": {"seq": 1}, "quote": c["quote"], "promise": c["promise"]}
                              for c in res["commitments"]]}
    its = commit_check.items(unit, record)
    checks = {its[0]["key"]: {"verdict": "promise", "promise_fixed": "build in 2026"},
              its[1]["key"]: {"verdict": "past_or_existing", "promise_fixed": ""}}
    rec = enrich.finish(unit, res, checks)
    assert [(c["promise"], c["check"]) for c in rec["commitments"]] == [("build in 2026", "promise")]
    assert rec["dropped"]["commitments_not_real"] == 1


def test_schema_limits_ids_to_the_request():
    s = commit_check.schema(["C1", "C2"])
    item = s["properties"]["checks"]["items"]["properties"]
    assert item["id"]["enum"] == ["C1", "C2"] and item["verdict"]["enum"] == commit_check.VERDICTS
