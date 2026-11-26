"""Screenshots of one design direction's prototypes, in light and dark.

Writes docs/design/<direction>/shots/<page>-<width>[-dark].png: each page at 1440 px wide (full
page) and 390 px wide (first screen, 844 px tall). home.html is also shot after its demo answer
has streamed, when the page exposes window.demoAnswer() (a function that runs the demo and
returns a promise that resolves once the answer and its sources are on screen).

Run:  python docs/design/shoot.py <direction> [--dark]
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
PAGES = ("home", "mp", "debate")


async def main(direction: str, dark: bool) -> None:
    folder = HERE / direction
    out = folder / "shots"
    out.mkdir(exist_ok=True)
    scheme = "dark" if dark else "light"
    tag = "-dark" if dark else ""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height, full in ((1440, 900, True), (390, 844, False)):
            ctx = await browser.new_context(viewport={"width": width, "height": height},
                                            color_scheme=scheme, device_scale_factor=1)
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for name in PAGES:
                await page.goto((folder / f"{name}.html").as_uri(), wait_until="networkidle")
                await page.wait_for_timeout(600)
                await page.screenshot(path=str(out / f"{name}-{width}{tag}.png"), full_page=full)
                overflow = await page.evaluate("document.documentElement.scrollWidth - innerWidth")
                if overflow > 0:
                    print(f"{name} at {width}: page scrolls sideways by {overflow} px")
                if name == "home" and await page.evaluate("typeof window.demoAnswer === 'function'"):
                    await page.evaluate("window.demoAnswer()")
                    await page.wait_for_timeout(400)
                    await page.screenshot(path=str(out / f"home-answer-{width}{tag}.png"), full_page=full)
            for e in errors:
                print(f"page error at {width}: {e}")
            await ctx.close()
        await browser.close()
    print(f"shots in {out}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--dark" in sys.argv))
