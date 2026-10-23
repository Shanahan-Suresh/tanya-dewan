import pytest

from parlimen.acts import parse_row


def _pdf(token: str, icon: str, kind: str = "printed") -> str:
    return (
        f'<a href="processFile.php?token={token}" target="_blank" class="event_kira_download_updated">'
        f'<img src="images/icons/pdf/{icon}-{kind}.png" title="Download PDF" alt="Download PDF"></a>'
    )


# Rows as the portal draws them (tokens shortened). Row 879 lists English first, row 878 Malay first.
ENGLISH_FIRST = [
    "879",
    '<a href="processFile.php?isDirect=1&amp;token=d1">AUCTIONEERS ACT 1914\n(REVISED—2026)</a> '
    "<i>As At </i><i>25-03-2026</i><br>"
    '<a href="processFile.php?isDirect=1&amp;token=d2">AKTA PELELONG 1914\n(DISEMAK─2026)</a> '
    "<i>Sebagaimana Pada </i><i>25-03-2026</i>",
    _pdf("en879", "pdf-en") + "<br>" + _pdf("ms879", "pdf-ms"),
]

MALAY_FIRST = [
    "878",
    '<a href="processFile.php?isDirect=1&amp;token=d3">AKTA BANTUAN GUAMAN DAN PEMBELAAN\nAWAM 2026</a> '
    "<i>Sebagaimana Pada </i><i>13-02-2026</i><br>"
    '<a href="processFile.php?isDirect=1&amp;token=d4">LEGAL AID AND PUBLIC DEFENCE ACT 2026</a> '
    "<i>As At </i><i>13-02-2026</i>",
    _pdf("ms878", "pdf-ms") + "<br>" + _pdf("en878", "pdf-en"),
]


REPEALED = [
    "762",
    '<a href="processFile.php?isDirect=1&amp;token=d5">GOODS AND SERVICES TAX ACT 2014</a><i> (Repealed by Act 805)</i><br>'
    '<a href="processFile.php?isDirect=1&amp;token=d6">AKTA CUKAI BARANG DAN PERKHIDMATAN 2014</a>'
    "<i> (Dimansuhkan oleh Akta 805)</i>",
    _pdf("en762", "pdf-en") + "<br>" + _pdf("ms762", "pdf-ms"),
]

# An English-only Act: the Malay title has no label and no PDF.
ENGLISH_ONLY = [
    "265",
    '<a href="processFile.php?isDirect=1&amp;token=d7">EMPLOYMENT ACT 1955</a> <i>As At </i><i>01-08-2023</i><br>'
    '<a href="processFile.php?isDirect=1&amp;token=d8">AKTA KERJA 1955</a>',
    _pdf("en265", "pdf-en"),
]

# Act 26 lists two versions; the later one, and its online reprint, win.
TWO_VERSIONS = [
    "26",
    '<a href="processFile.php?isDirect=1&amp;token=a">LEGAL AID ACT 1971</a> <i>As At </i><i>29-06-1947</i><br>'
    '<a href="processFile.php?isDirect=1&amp;token=b">AKTA BANTUAN GUAMAN 1971 </a><br>'
    '<a href="processFile.php?isDirect=1&amp;token=c">*LEGAL AID ACT 1971</a> <i>As At </i><i>05-09-2022</i><br>'
    '<a href="processFile.php?isDirect=1&amp;token=d">*AKTA BANTUAN GUAMAN 1971 </a> <i>Sebagaimana Pada </i><i>05-09-2022</i>',
    _pdf("p26", "pdf-en") + "<br>" + _pdf("o26", "pdf-en", "online")
    + '<br><a href="processFile.php?token=e" target="_blank"></a>',
]


def test_parse_row_english_first():
    act = parse_row(ENGLISH_FIRST)
    assert act.number == "879"
    assert act.title_bi == "AUCTIONEERS ACT 1914 (REVISED—2026)"
    assert act.title_bm.startswith("AKTA PELELONG")
    assert act.as_at == "2026-03-25"
    assert act.pdf_bi.endswith("token=en879") and act.pdf_bm.endswith("token=ms879")


def test_parse_row_malay_first_keeps_languages_apart():
    act = parse_row(MALAY_FIRST)
    assert act.title_bi == "LEGAL AID AND PUBLIC DEFENCE ACT 2026"
    assert act.title_bm == "AKTA BANTUAN GUAMAN DAN PEMBELAAN AWAM 2026"
    assert act.pdf_bi.endswith("token=en878") and act.pdf_bm.endswith("token=ms878")


def test_parse_row_repealed_act_keeps_its_note():
    act = parse_row(REPEALED)
    assert act.status == "repealed" and act.note == "Repealed by Act 805"
    assert act.as_at == "" and act.pdf_path("BI").name == "BI-repealed.pdf"


def test_parse_row_unlabelled_title_takes_the_other_language():
    act = parse_row(ENGLISH_ONLY)
    assert act.title_bm == "AKTA KERJA 1955" and act.pdf_bm == ""
    assert act.status == "in force" and act.as_at == "2023-08-01"


def test_parse_row_two_versions_keeps_the_later():
    act = parse_row(TWO_VERSIONS)
    assert act.title_bi == "*LEGAL AID ACT 1971" and act.as_at == "2022-09-05"
    assert act.pdf_bi.endswith("token=o26") and act.kind_bi == "online"


def test_parse_row_rejects_an_unknown_icon():
    row = ENGLISH_FIRST[:2] + [_pdf("x", "pdf-xx")]
    with pytest.raises(ValueError):
        parse_row(row)
