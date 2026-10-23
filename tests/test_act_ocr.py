from parlimen import act_ocr
from parlimen.act_text import ocr_pages


def test_gap_filled_from_the_one_fitting_word():
    check = "with any affidavit or statutory declaration which is executed"
    assert act_ocr.fill_gaps("statutory declar[?]tion which", check) == "statutory declaration which"


def test_gap_kept_when_no_word_or_two_words_fit():
    assert act_ocr.fill_gaps("the [?]ct", "nothing here") == "the [?]ct"
    assert act_ocr.fill_gaps("the [?]ct", "an act and a pact") == "the [?]ct"
    assert act_ocr.fill_gaps("[?] alone", "any word") == "[?] alone"


def test_ocr_pages_drop_specks_and_mark_the_closing_note(monkeypatch):
    page = "\n".join([
        "[?] [?]",
        "3. (1) Subject to subsection (3), the Attorney General may",
        "*NOTE—In its application to Sabah and Sarawak—see L.N. 98/1965.",
        "and Sarawak.",
    ])
    monkeypatch.setattr(act_ocr, "ocr_text", lambda path, n: [page])
    [lines] = ocr_pages(None, 1)
    assert [t for t, _ in lines][0].startswith("3. (1)")
    assert [size for _, size in lines] == [1.0, 0.5, 0.5]


def test_margin_note_split_from_the_section_line(monkeypatch):
    page = "\n".join([
        "Sharat² 4. (1) Pengerusi Majlis hendak-lah di-lantek atas sharat²",
        "Kewajipan Majlis memelihara Kumpulan-wang.\t11. Ada-lah menjadi kewajipan Majlis",
        "dibuat di bawah seksyen 4. (1) Tiada orang boleh",
    ])
    monkeypatch.setattr(act_ocr, "ocr_text", lambda path, n: [page])
    [lines] = ocr_pages(None, 1)
    assert [t for t, _ in lines] == [
        "Sharat²", "4. (1) Pengerusi Majlis hendak-lah di-lantek atas sharat²",
        "Kewajipan Majlis memelihara Kumpulan-wang.", "11. Ada-lah menjadi kewajipan Majlis",
        "dibuat di bawah seksyen 4. (1) Tiada orang boleh",
    ]


def test_ocr_pages_none_until_every_page_is_read(monkeypatch):
    monkeypatch.setattr(act_ocr, "ocr_text", lambda path, n: None)
    assert ocr_pages(None, 3) is None
