"""Logo concepts for Tanya Dewan: each mark as SVG, shown big, in the site header (light and dark),
in a browser tab at real favicon size, and as a phone app icon. Writes index.html and one SVG per
mark beside this file.

Run:  python docs/design/logo/build.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAVY, GOLD, WHITE = "#0A1F5C", "#F5B800", "#FFFFFF"

# Each mark is drawn on a 64 x 64 grid.
MARKS = {
    "L1": ("The Dewan roof",
           "A speech bubble whose top is the pointed roof of Parliament's chamber building. A gold diamond sits inside. Catch: at small sizes the roof can read as a crown.",
           f'<path d="M8 27 L16 13 L24 27 L32 13 L40 27 L48 13 L56 27 V46 Q56 52 50 52 H27 L15 61 V52 H14 Q8 52 8 46 Z" fill="{NAVY}"/>'
           f'<path d="M32 33 L38 39 L32 45 L26 39 Z" fill="{GOLD}"/>'),
    "L2": ("The seats",
           "The chamber's curved rows of seats inside a speech bubble. The gold diamond is the question at the centre of the room. Catch: at 16 px the seats blur into a texture, but the bubble still reads.",
           f'<path d="M14 6 H50 Q58 6 58 14 V42 Q58 50 50 50 H28 L16 60 V50 H14 Q6 50 6 42 V14 Q6 6 14 6 Z" fill="{NAVY}"/>'
           f'<path d="M13.5 40 A18.5 18.5 0 0 1 50.5 40" fill="none" stroke="{WHITE}" stroke-width="7" stroke-dasharray="11.15 4.5"/>'
           f'<path d="M22 40 A10 10 0 0 1 42 40" fill="none" stroke="{WHITE}" stroke-width="7" stroke-dasharray="13.45 4.5"/>'
           f'<path d="M32 35 L36 39 L32 43 L28 39 Z" fill="{GOLD}"/>'),
    "L3": ("The receipt",
           "A torn receipt with a speech tail: every answer comes with proof. The gold line is the quote that backs it. Catch: the speech tail is hard to see, so it reads mostly as a receipt.",
           f'<rect width="64" height="64" rx="15" fill="{NAVY}"/>'
           f'<path d="M19 9 H47 Q49 9 49 11 V51 L45 55 L41 51 L37 55 L33 51 L29 55 L25 51 L21 55 L19 53 V31 L11 26 L19 21 V11 Q19 9 21 9 Z" fill="{WHITE}"/>'
           f'<rect x="25" y="17" width="18" height="4.5" rx="2.25" fill="{NAVY}"/>'
           f'<rect x="25" y="26" width="18" height="4.5" rx="2.25" fill="{NAVY}"/>'
           f'<rect x="25" y="35" width="11" height="4.5" rx="2.25" fill="{GOLD}"/>'),
    "L4": ("The diamond bubble",
           "The songket diamond turned into a speech bubble. Closest to the mark the site uses today. Catch: the change from today is small.",
           f'<path d="M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z" fill="{NAVY}" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round"/>'
           f'<path d="M32 19 L45 32 L32 45 L19 32 Z" fill="none" stroke="{WHITE}" stroke-width="3"/>'
           f'<path d="M32 26 L38 32 L32 38 L26 32 Z" fill="{GOLD}"/>'),
    "L5": ("The question mark",
           "A bold question mark whose dot is the gold songket diamond. It is the clearest at 16 px. Catch: a question mark in a box is common, and only the gold dot is ours.",
           f'<rect width="64" height="64" rx="15" fill="{NAVY}"/>'
           f'<path d="M21.5 23 Q21.5 11.5 32 11.5 Q42.5 11.5 42.5 21.5 Q42.5 27.5 36 30.5 Q32 32.5 32 37.5 V40" fill="none" stroke="{WHITE}" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>'
           f'<path d="M32 45 L38 51 L32 57 L26 51 Z" fill="{GOLD}"/>'),
    "L0": ("Today's mark (for comparison)",
           "The diamond tile the site shows now.",
           f'<rect width="64" height="64" rx="17" fill="{NAVY}"/>'
           f'<path d="M32 11.3 L49 32 L32 52.7 L15 32 Z" fill="none" stroke="{WHITE}" stroke-width="3.4" stroke-linejoin="round"/>'
           f'<path d="M32 24 L40.7 32 L32 40 L23.3 32 Z" fill="{GOLD}"/>'),
}
ORDER = ["L1", "L2", "L3", "L4", "L5", "L0"]


def svg(body: str, size: int) -> str:
    return f'<svg viewBox="0 0 64 64" width="{size}" height="{size}" aria-hidden="true">{body}</svg>'


def card(key: str, title: str, note: str, body: str) -> str:
    base = " base" if key == "L0" else ""
    nav = '<span class="nav">Ask &nbsp; Acts &nbsp; Sittings</span>'
    return f"""<article class="card{base}">
  <div class="big">{svg(body, 132)}</div>
  <div class="txt"><h2><span class="id">{key}</span> {title}</h2><p>{note}</p></div>
  <div class="uses">
    <div class="hdr light">{svg(body, 34)}<b>Tanya Dewan</b>{nav}</div>
    <div class="hdr dark"><span class="chip">{svg(body, 30)}</span><b>Tanya Dewan</b>{nav}</div>
    <div class="row">
      <div class="tab">{svg(body, 16)}<span>Tanya Dewan</span><i>&times;</i></div>
      <div class="home"><div class="app">{svg(body, 52)}</div><span>Tanya Dewan</span></div>
      <div class="tiny" title="Real size: 24 and 16 pixels">{svg(body, 24)}{svg(body, 16)}</div>
    </div>
  </div>
</article>"""


PAGE = """<title>Tanya Dewan Logos</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;650;700&display=swap">
<style>
:root { --bg:#FBFAF6; --surface:#FFFFFF; --ink:#0C1433; --muted:#46506E; --line:#E4E1D5; --brand:#0A1F5C; --tab:#E9E7DF; --font:"Geist", system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#060A1C; --surface:#0D1430; --ink:#EEF0FA; --muted:#A8B1D0; --line:#1E2850; --brand:#9DB2FF; --tab:#1A2244; color-scheme: dark; } }
:root[data-theme="dark"] { --bg:#060A1C; --surface:#0D1430; --ink:#EEF0FA; --muted:#A8B1D0; --line:#1E2850; --brand:#9DB2FF; --tab:#1A2244; color-scheme: dark; }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 400 16px/1.55 var(--font); padding-block: 40px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.wrap { max-width: 1240px; margin: 0 auto; display: grid; gap: 28px }
h1 { font-size: clamp(28px, 4vw, 40px); line-height: 1.1; letter-spacing: -.03em; margin: 0; text-wrap: balance }
.intro p { color: var(--muted); max-width: 68ch; margin: 10px 0 0 }
.intro b { color: var(--ink) }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 540px), 1fr)); gap: 18px }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 22px; display: grid;
  grid-template-columns: 168px 1fr; gap: 18px 24px; align-items: start; min-width: 0 }
.card.base { opacity: .85 }
.big { width: 168px; height: 168px; background: #fff; border: 1px solid #E4E1D5; border-radius: 12px; display: grid; place-items: center }
h2 { margin: 0; font-size: 21px; letter-spacing: -.01em }
.id { display: inline-block; min-width: 2.2em; font-variant-numeric: tabular-nums; color: var(--brand) }
.txt p { margin: 6px 0 0; color: var(--muted); font-size: 15px }
.uses { grid-column: 1 / -1; display: grid; gap: 10px; min-width: 0 }
.hdr { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 10px; font-size: 18px; overflow: hidden; white-space: nowrap }
.hdr b { font-weight: 650; letter-spacing: -.02em }
.hdr svg, .tab svg, .tiny svg { flex: none }
.hdr .nav { margin-left: 18px; font-size: 14px; opacity: .75 }
.hdr.light { background: #FBFAF6; color: #0C1433; border: 1px solid #E4E1D5 }
.hdr.dark { background: #060A1C; color: #EEF0FA; border: 1px solid #1E2850 }
.chip { display: grid; place-items: center; width: 34px; height: 34px; background: #fff; border-radius: 9px; flex: none }
.row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center }
.tab { display: flex; align-items: center; gap: 8px; background: var(--tab); padding: 8px 12px; border-radius: 9px 9px 0 0; font-size: 13px; min-width: 190px }
.tab i { margin-left: auto; font-style: normal; opacity: .5 }
.home { display: grid; justify-items: center; gap: 4px; font-size: 11px; padding: 10px 12px; border-radius: 12px; background: linear-gradient(160deg, #6C7FB8, #2B3768) }
.home span { color: #fff }
.app { width: 60px; height: 60px; border-radius: 14px; background: #fff; display: grid; place-items: center }
.tiny { display: flex; gap: 10px; align-items: center; padding: 8px 12px; border: 1px dashed var(--line); border-radius: 9px; background: #fff }
@media (max-width: 560px) { .card { grid-template-columns: 1fr } }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px }
summary { cursor: pointer; font-weight: 650; min-height: 28px }
details p { color: var(--muted); max-width: 80ch }
</style>
<div class="wrap">
  <header class="intro">
    <h1>Which logo should Tanya Dewan use?</h1>
    <p>Here are five new marks. Today's mark is last, for comparison. Each card shows the mark large, in the site header in light and dark, in a browser tab at real size, and as a phone app icon.</p>
    <p>My pick is <b>L2, the seats</b>. It says "ask the chamber" in one shape. In a browser tab the seats blur, but the speech bubble still reads. L5 is the safe choice if the tab icon matters most. Tell me the code in chat, for example "L2", or ask for changes to one.</p>
  </header>
  <div class="grid">CARDS</div>
  <details><summary>How these were made</summary>
    <p>Each mark is a simple shape drawn in code, in the site's navy and gold. The pointed roof in L1 comes from the Dewan Rakyat chamber building in Kuala Lumpur. The curved rows in L2 follow the chamber's seating. The diamond is the songket motif the site already uses.</p>
    <p>The mark you pick goes into the site header, the browser-tab icon, the phone icon and the share image. I can still tune its details after you pick.</p>
  </details>
</div>
"""


def main() -> None:
    cards = "".join(card(k, *MARKS[k]) for k in ORDER)
    (HERE / "index.html").write_text(PAGE.replace("CARDS", cards), encoding="utf-8")
    for key, (_, _, body) in MARKS.items():
        (HERE / f"{key}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{body}</svg>', encoding="utf-8")
    print(HERE / "index.html")


if __name__ == "__main__":
    main()
