"""The site's icon set from the L4 mark (docs/design/logo/): favicon.svg (light and dark tab bars),
favicon.ico (16, 32, 48 px), apple-touch-icon.png (180 px) and icon-512.png, into static/.

Run:  .venv\\Scripts\\python.exe tools\\make_icons.py
"""
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "parlimen" / "web" / "static"
NAVY, GOLD, WHITE = "#0A1F5C", "#F5B800", "#FFFFFF"

# The mark on a 64 x 64 grid: a songket diamond with a speech tail, a white ring, a gold centre.
SHAPE = "M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z"
RING = "M32 19 L45 32 L32 45 L19 32 Z"
CORE = "M32 26 L38 32 L32 38 L26 32 Z"

FAVICON = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<style>.o{{fill:{NAVY};stroke:{NAVY}}}.r{{stroke:{WHITE}}}
@media (prefers-color-scheme: dark){{.o{{fill:#EEF0FA;stroke:#EEF0FA}}.r{{stroke:{NAVY}}}}}</style>
<path class="o" d="{SHAPE}" stroke-width="3" stroke-linejoin="round"/>
<path class="r" d="{RING}" fill="none" stroke-width="3"/>
<path d="{CORE}" fill="{GOLD}"/></svg>"""


def tile(px: int, pad: float) -> str:
    """The mark centred on a white square, for app icons."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {64 + 2 * pad} {64 + 2 * pad}" '
            f'width="{px}" height="{px}"><rect x="{-pad}" y="{-pad}" width="{64 + 2 * pad}" height="{64 + 2 * pad}" fill="{WHITE}"/>'
            f'<path d="{SHAPE}" fill="{NAVY}" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round"/>'
            f'<path d="{RING}" fill="none" stroke="{WHITE}" stroke-width="3"/><path d="{CORE}" fill="{GOLD}"/></svg>')


def bare(px: int) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{px}" height="{px}">'
            f'<path d="{SHAPE}" fill="{NAVY}" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round"/>'
            f'<path d="{RING}" fill="none" stroke="{WHITE}" stroke-width="3"/><path d="{CORE}" fill="{GOLD}"/></svg>')


def shoot(page, svg: str, px: int, transparent: bool) -> Image.Image:
    page.set_viewport_size({"width": px, "height": px})
    page.set_content(f"<body style='margin:0;background:transparent'>{svg}</body>")
    return Image.open(io.BytesIO(page.screenshot(omit_background=transparent))).convert("RGBA")


def main() -> None:
    (STATIC / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        shoot(page, tile(180, 9), 180, False).convert("RGB").save(STATIC / "apple-touch-icon.png")
        shoot(page, tile(512, 9), 512, False).convert("RGB").save(STATIC / "icon-512.png")
        big = shoot(page, bare(256), 256, True)
        browser.close()
    big.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons written to", STATIC)


if __name__ == "__main__":
    main()
