from datetime import date

from parlimen.sittings import parse_current, parse_date, parse_tree

TREE = (
    b"<?xml version=\"1.0\" encoding=\"iso-8859-1\"?><tree id='0_15_5_2'>"
    b"<item child='0' id='0_15_5_2_0' text='22 Jun 2026' im0='book_titel.gif'>"
    b"<userdata name='myurl'>javascript:loadResult('/files/hindex/pdf/DR-22062026.pdf','DR-22062026.pdf')</userdata></item>"
    b"<item child='1' id='0_15_5_11' text='Mesyuarat Khas (11/08/2026 - 11/08/2026)'>"
    b"<userdata name='myurl'>#</userdata></item></tree>"
)

CURRENT = (
    '<span class="boxMesyuaratTextA"><strong>Mesyuarat Ketiga, Penggal Kelima Parlimen Kelima Belas (2026)</strong></span>'
    "<a href=\"javascript:loadResult('/files/hindex/pdf/DR-07102026.pdf','DR-07102026.pdf');\">7 Oktober 2026</a><br>"
    "<a href=\"javascript:loadResult('/files/hindex/pdf/DR-06102026..pdf','DR-06102026..pdf');\">6 Oktober 2026</a><br>"
)


def test_parse_tree_reads_leaf_and_branch():
    leaf, branch = parse_tree(TREE)
    assert leaf["pdf_path"] == "/files/hindex/pdf/DR-22062026.pdf"
    assert not leaf["has_children"]
    assert branch["has_children"] and branch["pdf_path"] == ""


def test_parse_current_keeps_irregular_file_names():
    title, days = parse_current(CURRENT)
    assert "Kelima Belas" in title
    assert days[1] == ("6 Oktober 2026", "/files/hindex/pdf/DR-06102026..pdf")


def test_parse_date_prefers_text_then_file_name():
    assert parse_date("6 Oktober 2026", "x") == date(2026, 10, 6)
    assert parse_date("22 Jun 2026", "x") == date(2026, 6, 22)
    assert parse_date("Ogos?", "/files/hindex/pdf/DR-11082026.pdf") == date(2026, 8, 11)
