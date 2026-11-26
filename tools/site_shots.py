"""Screenshots of a running site (python -m parlimen.web), through the installed Chrome, headless.

Each page is shot at desktop and phone width into data/shots/, with its load time and any width
past the window. `--ask` also asks one question on the home page and shoots the answer (and its
citation preview): against a real site that is one real search and answer (about [amount removed]); against
a site started with `--replay` it costs nothing. `--dark` shoots in the dark colour scheme.

Run:  .venv\\Scripts\\python.exe tools\\site_shots.py [--base http://127.0.0.1:8780] [--ask "question"]
      [--path /law/265/BI ...] [--dark] [--full]
"""
import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "shots"
PAGES = ["/", "/mp/dzulkefly-ahmad", "/debate/DR-2026-10-22-017", "/debate/DR-2026-10-05-005",
         "/hansard/DR/2026-10-22", "/questions", "/commitments", "/law/265/BI", "/mp", "/topics"]
SIZES = {"desktop": (1366, 900), "phone": (390, 844)}


def name(path: str) -> str:
    return (path.strip("/").replace("/", "_").replace("#", "_").replace("?", "_").replace("=", "_") or "home")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8780")
    ap.add_argument("--path", nargs="*", default=PAGES)
    ap.add_argument("--ask", default="")
    ap.add_argument("--dark", action="store_true", help="shoot in the dark colour scheme")
    ap.add_argument("--full", action="store_true", help="whole page, not just the first screen")
    ap.add_argument("--lang", choices=("en", "ms"), default="en")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "-dark" if a.dark else ""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for size, (w, h) in SIZES.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme="dark" if a.dark else "light")
            ctx.add_cookies([{"name": "hl", "value": a.lang, "url": a.base}])
            page = ctx.new_page()
            for path in a.path:
                t0 = time.perf_counter()
                page.goto(a.base + path, wait_until="networkidle", timeout=180000)
                ms = (time.perf_counter() - t0) * 1000
                over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                f = OUT / f"{name(path)}-{size}-{a.lang}{tag}.png"
                page.screenshot(path=str(f), full_page=a.full)
                print(f"{f.name}  {ms:,.0f} ms{'  (wider than the window by ' + str(over) + ' px)' if over > 0 else ''}")
            if a.ask:
                page.goto(a.base + "/", wait_until="networkidle")
                page.fill("#q", a.ask)
                page.click(".ask-go")
                page.wait_for_selector("#src-list .src[data-n]", timeout=120000)
                page.wait_for_timeout(300)
                f = OUT / f"ask-{size}-{a.lang}{tag}.png"
                page.screenshot(path=str(f), full_page=True)
                print(f.name)
                page.click("#answer-text .cite")
                page.wait_for_timeout(300)
                f = OUT / f"ask-peek-{size}-{a.lang}{tag}.png"
                page.screenshot(path=str(f))
                print(f.name)
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
