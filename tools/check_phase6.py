"""Phase 6 exit check: a reader finds a section, its debate, a minister's answer and a commitment on
the running site, by clicking links in the installed Chrome (headless), with no CLI and no model.

1. Acts page: search the Acts for a title, open the Act, find the section by its anchor.
2. From the Act page, open a debate on its bill: the verbatim speeches show with speaker labels
   beside the AI summary.
3. Questions page, filtered by a ministry: follow a card's "answered by" link to the speech; the
   speech it lands on is a minister's or a deputy minister's.
4. Commitments page, filtered by words: follow a card's speaker link to the speech; the verbatim
   quote is in that speech.

Each step is shot into data/shots/check-<n>.png. Start the site first (python -m parlimen.web).
Run:  python tools/check_phase6.py [--base http://127.0.0.1:8780] [--lang en|ms]
"""
import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parlimen.enrich import _norm  # noqa: E402

OUT = ROOT / "data" / "shots"
ACT_QUERY, ACT, SECTION = "gig workers", "872", "s-1"
MINISTRY = "Kewangan"
COMMITMENT_WORDS = "elektrik"
MINISTER = re.compile(r"Menteri|Minister", re.I)


def speech_at(page) -> tuple[str, str]:
    """The label and text of the speech the URL's #seq-N anchor names."""
    anchor = page.url.split("#", 1)[1]
    s = page.locator(f"article.speech#{anchor}")
    return s.locator(".speaker").inner_text(), s.locator(".verbatim-text").inner_text()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8780")
    ap.add_argument("--lang", choices=("en", "ms"), default="en")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    def step(n: int, page, passed: bool, note: str) -> None:
        page.screenshot(path=str(OUT / f"check-{n}-{a.lang}.png"))
        results.append(passed)
        print(f"{n}. {note} -> {'pass' if passed else 'FAIL'}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        ctx.add_cookies([{"name": "hl", "value": a.lang, "url": a.base}])
        page = ctx.new_page()
        page.set_default_timeout(60000)

        page.goto(f"{a.base}/law")
        page.fill("input[name=q]", ACT_QUERY)
        page.press("input[name=q]", "Enter")
        page.wait_for_load_state()
        page.locator(f"a[href^='/law/{ACT}']").first.click()
        page.wait_for_load_state()
        page.goto(page.url.split("#")[0] + f"#{SECTION}")
        found = page.locator(f"#{SECTION}").count() == 1
        step(1, page, found and f"/law/{ACT}/" in page.url,
             f"\"{ACT_QUERY}\" on the Acts page -> {page.url.removeprefix(a.base)}, section anchor #{SECTION}")

        page.locator(f"a[href^='/debate/']").first.click()
        page.wait_for_load_state()
        speeches = page.locator("article.speech").count()
        summary = page.locator(".beside").count() > 0
        step(2, page, speeches > 0 and summary,
             f"its bill debate {page.url.removeprefix(a.base)}: {speeches} verbatim speeches, AI summary beside")

        page.goto(f"{a.base}/questions?ministry={MINISTRY}")
        card = page.locator("article.card.qa").first
        card.locator("p.who").nth(1).locator("a").click()
        page.wait_for_load_state()
        label, _ = speech_at(page)
        step(3, page, bool(MINISTER.search(label)),
             f"a {MINISTRY} answer on the Questions page -> {page.url.removeprefix(a.base)}, speaker \"{label}\"")

        page.goto(f"{a.base}/commitments?q={COMMITMENT_WORDS}")
        card = page.locator("article.card.commit").first
        quote = card.locator("blockquote").inner_text().strip("“” ")
        card.locator("p.who a").first.click()
        page.wait_for_load_state()
        label, text = speech_at(page)
        inside = _norm(quote) in _norm(text)
        step(4, page, inside,
             f"a commitment on \"{COMMITMENT_WORDS}\" -> {page.url.removeprefix(a.base)}, \"{quote[:60]}\" "
             f"{'is' if inside else 'is NOT'} in the speech of {label}")
        browser.close()

    print(f"{sum(results)} of {len(results)} pass")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
