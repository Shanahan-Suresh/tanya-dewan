import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import static_demo as sd  # noqa: E402

PAGES = {"/": "index.html", "/mp": "mp.html", "/debate/DR-1": "debate/DR-1.html", "/law/265": "law/265/BI.html",
         "/law/265/BI": "law/265/BI.html"}


def test_file_for_maps_paths_to_html_files():
    assert sd.file_for("/") == "index.html"
    assert sd.file_for("/debate/DR-2024-03-18-006") == "debate/DR-2024-03-18-006.html"
    assert sd.file_for("/law/265/BI") == "law/265/BI.html"


def test_rewrite_makes_site_links_relative_from_a_nested_page():
    page = ('<a href="/">a</a><a href="/debate/DR-1#seq-4">b</a><a href="/mp/someone">c</a>'
            '<a href="/hansard?parliament=14">d</a><link href="/static/site.css?v=1">'
            '<a href="https://www.parlimen.gov.my/x.pdf">e</a><a href="#top">f</a>'
            '<form hx-get="/mp" hx-target="#results" action="/mp">')
    out = sd.rewrite(page, "debate/DR-1.html", "en", PAGES)
    assert 'href="../index.html"' in out
    assert 'href="../debate/DR-1.html#seq-4"' in out
    assert 'href="../not-in-demo.html"' in out           # an MP outside the sample, and a query
    assert out.count("not-in-demo.html") == 2
    assert 'href="../static/site.css"' in out
    assert 'href="https://www.parlimen.gov.my/x.pdf"' in out and 'href="#top"' in out
    assert "hx-" not in out and 'action="../mp.html"' in out


def test_rewrite_sends_the_language_switch_to_the_same_page_in_the_other_tree():
    page = '<a href="/hl/ms?next=%2Fdebate%2FDR-1">BM</a><a href="/debate/DR-1">x</a>'
    out = sd.rewrite(page, "debate/DR-1.html", "en", PAGES)
    assert 'href="../ms/debate/DR-1.html"' in out
    back = sd.rewrite('<a href="/hl/en?next=%2Fmp">EN</a><a href="/mp">MPs</a>', "ms/mp.html", "ms", PAGES)
    assert 'href="../mp.html"' in back and 'href="../ms/mp.html"' in back


def test_check_finds_broken_links_in_pages_and_answers(tmp_path):
    (tmp_path / "debate").mkdir()
    (tmp_path / "index.html").write_text('<a href="debate/DR-1.html#seq-2">x</a><a href="gone.html">y</a>', encoding="utf-8")
    (tmp_path / "debate" / "DR-1.html").write_text('<a href="../index.html">home</a>', encoding="utf-8")
    (tmp_path / "answers").mkdir()
    done = {"sources": [{"url": "debate/DR-1.html#seq-2"}, {"url": "law/1/BI.html"}]}
    (tmp_path / "answers" / "a.json").write_text(json.dumps({"events": [{"event": "done", "data": done}]}),
                                                 encoding="utf-8")
    bad = sd.check(tmp_path)
    assert sorted(bad) == ["answers\\a.json: law/1/BI.html" if sys.platform == "win32" else "answers/a.json: law/1/BI.html",
                           "index.html: gone.html"]
