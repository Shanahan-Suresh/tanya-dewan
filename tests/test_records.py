import csv
import json

import pytest

from parlimen import records
from parlimen.records import Records, Sources


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def speech(seq, label, name, seat, text, role="", senator=False):
    return {"seq": seq, "label": label, "name": name, "seat": seat, "role": role, "senator": senator,
            "text": text, "topic": "", "id": seq}


def make_sources(tmp_path) -> Sources:
    """Two Acts, two sittings (one bill debate, one question time) and their records."""
    write_csv(tmp_path / "acts.csv", [
        {"number": "265", "title_bi": "EMPLOYMENT ACT 1955", "title_bm": "AKTA KERJA 1955", "status": "in force",
         "note": "", "as_at": "2023-01-01", "pdf_bi": "https://lom.example/265-bi.pdf", "pdf_bm": "https://lom.example/265-bm.pdf",
         "kind_bi": "printed", "kind_bm": "printed"},
        {"number": "999", "title_bi": "OLD ACT 1960", "title_bm": "AKTA LAMA 1960", "status": "repealed", "note": "",
         "as_at": "2001-01-01", "pdf_bi": "", "pdf_bm": "", "kind_bi": "", "kind_bm": ""},
    ])
    sec = {"part": "PART XII", "part_title": "HOURS OF WORK", "chapter": "", "chapter_title": "", "notes": "",
           "heading_source": "exact", "source": "text", "as_at": "2023-01-01"}
    write_jsonl(tmp_path / "act_sections.jsonl", [
        {**sec, "act": "265", "lang": "BI", "number": "60A", "heading": "Hours of work",
         "text": "60A. (1) An employee shall not work more than forty-five hours in one week.", "page_start": 80, "page_end": 81},
        {**sec, "act": "265", "lang": "BI", "number": "60C", "heading": "Shift work",
         "text": "60C. Shift work may exceed the hours in section 60A.", "page_start": 82, "page_end": 82},
        {**sec, "act": "265", "lang": "BM", "number": "60A", "heading": "Waktu kerja",
         "text": "60A. (1) Pekerja tidak boleh bekerja lebih daripada empat puluh lima jam.", "page_start": 80, "page_end": 81},
    ])
    write_csv(tmp_path / "sittings.csv", [
        {"date": "2022-03-01", "chamber": "DR", "parliament": "14", "term": "Penggal Kelima",
         "meeting": "Mesyuarat Pertama", "pdf_path": "/files/hindex/pdf/DR-01032022.pdf", "source": "archive"},
        {"date": "2024-05-02", "chamber": "DR", "parliament": "15", "term": "Penggal Ketiga",
         "meeting": "Mesyuarat Kedua", "pdf_path": "/files/hindex/pdf/DR-02052024.pdf", "source": "archive"},
    ])
    heading = "RANG UNDANG-UNDANG KERJA (PINDAAN) 2022 Bacaan Kali Yang Kedua dan Ketiga"
    minister = speech(1, "Menteri Sumber Manusia [Datuk Seri M. Saravanan]", "Datuk Seri M. Saravanan", "Tapah",
                      "Tuan Yang di-Pertua, saya mohon mencadangkan rang undang-undang ini.", role="Menteri Sumber Manusia")
    mp = speech(2, "Tuan Lim Guan Eng [Bagan]", "Tuan Lim Guan Eng", "Bagan", "Waktu kerja patut dikurangkan.")
    hannah14 = speech(3, "Puan Hannah Yeoh Tseow Suan [Segambut]", "Puan Hannah Yeoh Tseow Suan", "Segambut",
                      "Saya menyokong pindaan ini kerana pekerja wanita memerlukan cuti bersalin yang lebih panjang, "
                      "dan majikan perlu menyediakan waktu kerja yang anjal untuk ibu bapa yang bekerja di bandar besar. Itu sahaja.")
    asker = speech(1, "Puan Hannah Yeoh [Segambut]", "Puan Hannah Yeoh", "Segambut", "Bila subsidi beras sampai?")
    answer = speech(2, "Dato� Sri Mohamad Sabu", "Dato� Sri Mohamad Sabu", "Kota Raja",
                    "Kerajaan akan menyalurkan RM50 juta sebelum Disember 2024.")
    write_jsonl(tmp_path / "units.jsonl", [
        {"id": "DR-2022-03-01-001", "chamber": "DR", "date": "2022-03-01", "parliament": 14, "topic": heading,
         "speeches": [minister, mp, hannah14]},
        {"id": "DR-2024-05-02-001", "chamber": "DR", "date": "2024-05-02", "parliament": 15,
         "topic": "PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN", "speeches": [asker, answer]},
    ])
    write_jsonl(tmp_path / "speeches.jsonl", [
        {"chamber": "DR", "date": "2022-03-01", "seq": 1, "page_start": 10, "page_end": 11, "time": "1030",
         "question_no": "", "name": "Datuk Seri M. Saravanan", "role": "Menteri Sumber Manusia"},
        {"chamber": "DR", "date": "2022-03-01", "seq": 2, "page_start": 12, "page_end": 12, "time": "1100",
         "question_no": "", "name": "Tuan Lim Guan Eng", "role": ""},
        {"chamber": "DR", "date": "2022-03-01", "seq": 3, "page_start": 13, "page_end": 13, "time": "1110",
         "question_no": "", "name": "Puan Hannah Yeoh Tseow Suan", "role": ""},
        {"chamber": "DR", "date": "2024-05-02", "seq": 1, "page_start": 5, "page_end": 5, "time": "1010",
         "question_no": "3", "name": "Puan Hannah Yeoh", "role": ""},
        {"chamber": "DR", "date": "2024-05-02", "seq": 2, "page_start": 6, "page_end": 6, "time": "1012",
         "question_no": "3", "name": "Dato� Sri Mohamad Sabu", "role": ""},
        {"chamber": "DR", "date": "2024-04-01", "seq": 9, "page_start": 3, "page_end": 3, "time": "1000",
         "question_no": "", "name": "Dato' Sri Mohamad Sabu", "role": "Menteri Pertanian dan Keterjaminan Makanan"},
    ])
    by = lambda s: {k: s[k] for k in ("seq", "label", "name", "seat", "role", "senator")}  # noqa: E731
    write_jsonl(tmp_path / "enriched.jsonl", [
        {"unit": "DR-2022-03-01-001", "summary_en": "The minister moved the Employment (Amendment) Bill.",
         "summary_ms": "Menteri mencadangkan Rang Undang-undang Kerja (Pindaan).", "topics": ["labour and jobs"],
         "entities": [], "qa_pairs": [], "commitments": []},
        {"unit": "DR-2024-05-02-001", "summary_en": "A question on the rice subsidy.",
         "summary_ms": "Soalan tentang subsidi beras.", "topics": ["agriculture and food", "Sabah and Sarawak"],
         "entities": [],
         "qa_pairs": [{"question_by": by(asker), "answer_by": by(answer), "question": "When will the rice subsidy arrive?",
                       "answer": "RM50 million before December 2024.", "figures": [{"value": "RM50 juta", "meaning": "subsidy"}]}],
         "commitments": [{"speaker": by(answer), "quote": "menyalurkan RM50 juta sebelum Disember 2024",
                          "promise": "Pay RM50 million of rice subsidy", "deadline": "Disember 2024", "amount": "RM50 juta",
                          "check": "promise"}]},
    ])
    write_csv(tmp_path / "members.csv", [
        {"parliament": "14", "name_key": "m saravanan", "seat": "Tapah", "party": "", "senator": "0", "lists": "1"},
        {"parliament": "14", "name_key": "lim guan eng", "seat": "Bagan", "party": "", "senator": "0", "lists": "1"},
        {"parliament": "14", "name_key": "hannah yeoh tseow suan", "seat": "Segambut", "party": "", "senator": "0",
         "lists": "1"},
        {"parliament": "15", "name_key": "hannah yeoh", "seat": "Segambut", "party": "", "senator": "0", "lists": "1"},
        {"parliament": "15", "name_key": "lim guan eng", "seat": "Bagan", "party": "", "senator": "0", "lists": "1"},
        {"parliament": "15", "name_key": "mohamad sabu", "seat": "Kota Raja", "party": "", "senator": "0", "lists": "1"},
    ])
    write_csv(tmp_path / "parties.csv", [
        {"parliament": "14", "code": "P043", "seat": "Bagan", "member": "Lim Guan Eng", "party": "DAP", "from": "", "to": "",
         "from_text": "", "to_text": ""},
        {"parliament": "15", "code": "P043", "seat": "Bagan", "member": "Lim Guan Eng", "party": "DAP", "from": "", "to": "",
         "from_text": "", "to_text": ""},
        {"parliament": "15", "code": "P117", "seat": "Segambut", "member": "Hannah Yeoh", "party": "DAP", "from": "", "to": "",
         "from_text": "", "to_text": ""},
        {"parliament": "14", "code": "P070", "seat": "Tapah", "member": "M. Saravanan", "party": "MIC", "from": "", "to": "",
         "from_text": "", "to_text": ""},
    ])
    write_csv(tmp_path / "bill_links.csv", [
        {"heading": heading, "title": "KERJA (PINDAAN) 2022", "base": "KERJA", "year": "2022", "change": "amend",
         "act": "265", "act_title_bi": "EMPLOYMENT ACT 1955", "act_title_bm": "AKTA KERJA 1955", "result": "linked"},
    ])
    return Sources(acts=tmp_path / "acts.csv", sections=tmp_path / "act_sections.jsonl",
                   sittings=tmp_path / "sittings.csv", speeches=tmp_path / "speeches.jsonl",
                   units=tmp_path / "units.jsonl", enriched=tmp_path / "enriched.jsonl",
                   members=tmp_path / "members.csv", parties=tmp_path / "parties.csv", bills=tmp_path / "bill_links.csv")


@pytest.fixture
def recs(tmp_path) -> Records:
    path = tmp_path / "site.db"
    records.build(make_sources(tmp_path), path, log=lambda *_: None)
    return Records(path)


def test_ministry_names_the_ministry_of_an_office():
    assert records.ministry("Timbalan Menteri Kewangan II") == "Kewangan"
    assert records.ministry("Menteri di Jabatan Perdana Menteri (Undang-undang)") == "Jabatan Perdana Menteri"
    assert records.ministry("Perdana Menteri dan Menteri Kewangan") == "Perdana Menteri"
    assert records.ministry("") == ""


def test_tidy_puts_back_the_apostrophe_the_pdf_lost():
    assert records.tidy("Dato� Sri") == "Dato’ Sri"
    assert records.tidy("�PROKLAMASI") == "PROKLAMASI"


def test_heading_says_the_joined_section_header_once():
    assert records.heading("RANG UNDANG-UNDANG RANG UNDANG-UNDANG PEKERJA GIG 2025") == "RANG UNDANG-UNDANG PEKERJA GIG 2025"
    assert records.heading("USUL USUL MENJUNJUNG KASIH") == "USUL MENJUNJUNG KASIH"
    assert records.heading("WAKTU PERTANYAAN-PERTANYAAN MENTERI") == "WAKTU PERTANYAAN-PERTANYAAN MENTERI"
    assert records.heading(None) == ""


def test_reflow_joins_wrapped_lines_and_keeps_clauses():
    text = ("60A. (1) An employee shall not\nbe required to work—\n(a) more than five\nhours;\n(b) more than"
            " eight hours.\nThe Ahli-\nahli Yang\nBerhormat\n\nNext paragraph")
    assert records.reflow(text) == ("60A. (1) An employee shall not be required to work—\n(a) more than five hours;\n"
                                    "(b) more than eight hours.\nThe Ahli-ahli Yang Berhormat\n\nNext paragraph")


def test_who_names_the_office_once():
    assert records.who("Menteri Digital [Tuan Gobind Singh Deo]", "Menteri Digital") == "Menteri Digital [Tuan Gobind Singh Deo]"
    assert records.who("Tuan Gobind Singh Deo", "Menteri Digital") == "Tuan Gobind Singh Deo, Menteri Digital"
    assert records.who("Tuan Gobind Singh Deo", "") == "Tuan Gobind Singh Deo"


def test_the_law_keeps_section_order_languages_and_bill_debates(recs):
    assert recs.act("265")["langs"] == "BI,BM"
    assert [s["number"] for s in recs.sections("265", "BI")] == ["60A", "60C"]
    assert recs.section("265", "60A", "BM")["heading"] == "Waktu kerja"
    assert [a["number"] for a in recs.acts()] == ["265"]  # an Act with no text is not listed
    assert [d["id"] for d in recs.act_debates("265")] == ["DR-2022-03-01-001"]


def test_speeches_carry_page_party_and_member(recs):
    sp = recs.speeches("DR-2022-03-01-001")
    assert sp[1]["page_start"] == 12 and sp[1]["party"] == "DAP" and sp[1]["member"] == "lim-guan-eng"
    assert recs.unit("DR-2022-03-01-001")["bill"] == "kerja-pindaan-2022"
    assert recs.sitting("DR", "2022-03-01")["pdf"] == "https://www.parlimen.gov.my/files/hindex/pdf/DR-01032022.pdf"


def test_an_office_missing_from_the_label_comes_from_the_nearest_sitting(recs):
    c = recs.unit_commitments("DR-2024-05-02-001")[0]
    assert c["office"] == "Menteri Pertanian dan Keterjaminan Makanan" and c["office_inferred"] == 1
    assert c["ministry"] == "Pertanian dan Keterjaminan Makanan"
    assert c["speaker"] == "Dato’ Sri Mohamad Sabu"
    assert c["member"] == "mohamad-sabu"


def test_commitment_and_question_filters(recs):
    assert recs.commitments(q="rice subsidy").total == 1
    assert recs.commitments(q="hours").total == 0
    assert recs.commitments(year="2024", ministry="Pertanian dan Keterjaminan Makanan").total == 1
    assert recs.commitments(topic="sabah-and-sarawak").total == 1
    assert recs.commitments(kind="routine").total == 0
    assert recs.questions(member="hannah-yeoh-tseow-suan").rows[0]["question"] == "When will the rice subsidy arrive?"
    assert recs.questions(q='beras "OR" x').total == 0  # FTS syntax in a reader's words stays words


def test_members_seats_and_party_spells(recs):
    m = recs.member("lim-guan-eng")
    assert [(s["parliament"], s["seat"], s["code"]) for s in m["seats"]] == [(14, "Bagan", "P043"), (15, "Bagan", "P043")]
    assert {p["party"] for p in m["parties"]} == {"DAP"}
    assert recs.member_units("lim-guan-eng").total == 0  # a 30-character speech is not a debate spoken in
    assert {x["slug"] for x in recs.members(15)} == {"lim-guan-eng", "hannah-yeoh-tseow-suan", "mohamad-sabu"}


def test_one_person_under_two_name_keys_is_one_mp(recs):
    assert recs.member("hannah-yeoh") is None
    m = recs.member("hannah-yeoh-tseow-suan")
    assert [(s["parliament"], s["seat"]) for s in m["seats"]] == [(14, "Segambut"), (15, "Segambut")]
    assert {u["id"] for u in recs.member_units("hannah-yeoh-tseow-suan").rows} == {"DR-2022-03-01-001"}
    assert recs.speeches("DR-2024-05-02-001")[0]["member"] == "hannah-yeoh-tseow-suan"


def test_bills_and_topics(recs):
    b = recs.bill("kerja-pindaan-2022")
    assert b["act"] == "265" and [u["id"] for u in b["units"]] == ["DR-2022-03-01-001"]
    assert {t["topic"]: t["name"] for t in recs.topics()}["sabah-and-sarawak"] == "Sabah and Sarawak"
    assert recs.topic_units("labour-and-jobs").total == 1
    assert [u["id"] for u in recs.units_between("2024-01-01", "2024-12-31", ["agriculture-and-food"])] == ["DR-2024-05-02-001"]
