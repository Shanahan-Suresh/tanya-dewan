"""The share image (static/og.png, 1200 x 630) in the site's look, drawn as HTML and shot headless.

It reads the name from config.SITE_NAME and the site's own fonts, so a rename is one rerun.

Run:  .venv\\Scripts\\python.exe tools\\make_og.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from parlimen import config  # noqa: E402

STATIC = ROOT / "parlimen" / "web" / "static"
OUT = STATIC / "og.png"

PAGE = """<!doctype html><meta charset="utf-8"><style>
@font-face { font-family: Geist; src: url("fonts/geist-latin.woff2") format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0 }
body { width: 1200px; height: 630px; background: #0A1F5C; color: #fff; font-family: Geist, sans-serif;
  padding: 72px 80px; display: flex; flex-direction: column; justify-content: space-between; position: relative; overflow: hidden }
body::after { content: ""; position: absolute; inset: 0; opacity: .14;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='48'%3E%3Cpath d='M24 4l20 20-20 20L4 24z' fill='none' stroke='%23F5B800' stroke-width='1.5'/%3E%3Cpath d='M24 16l8 8-8 8-8-8z' fill='%23F5B800'/%3E%3C/svg%3E") }
.top, .bottom { position: relative; z-index: 1 }
.lock { display: flex; align-items: center; gap: 22px }
.mark svg { width: 96px; height: 96px; display: block }
.name { font-size: 92px; font-weight: 700; letter-spacing: -.035em }
h1 { margin-top: 44px; font-size: 54px; line-height: 1.1; font-weight: 650; letter-spacing: -.025em; max-width: 900px }
h1 span { color: #F5B800 }
.bottom { display: flex; justify-content: space-between; font-size: 26px; color: #C9D3F2; border-top: 2px solid rgba(245,184,0,.5); padding-top: 26px }
</style>
<div class="top">
  <div class="lock"><div class="mark"><svg viewBox="0 0 64 64"><path d="M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="3" stroke-linejoin="round"/><path d="M32 19 L45 32 L32 45 L19 32 Z" fill="none" stroke="#0A1F5C" stroke-width="3"/><path d="M32 26 L38 32 L32 38 L26 32 Z" fill="#F5B800"/></svg></div>
  <div class="name">NAME</div></div>
  <h1>Ask about Malaysian law and Parliament. <span>Every answer cites its source.</span></h1>
</div>
<div class="bottom"><span>Malaysia's Acts and Dewan Rakyat debates</span><span>English &middot; Bahasa Melayu</span></div>
"""


def main() -> None:
    html = STATIC / "_og.html"
    html.write_text(PAGE.replace("NAME", config.SITE_NAME), encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(html.as_uri())
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(OUT))
            browser.close()
    finally:
        html.unlink(missing_ok=True)
    print(OUT)


if __name__ == "__main__":
    main()
