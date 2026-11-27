"""Screenshots of one restyle direction, light and dark, with a defect report.

Writes docs/design/restyle/<direction>/shots/<page>-<view>-<scheme>.png:
  desk  = 1828 x 1029 (the owner's window), first screen; deskfull = the same, full page;
  phone = 390 x 844, first screen.
Pages: home, home-answer (home after window.demoAnswer() resolves), home-reader (after
window.demoReader() resolves, when the page defines it), mp, debate.
Prints each shot's document scrollWidth (a value wider than the viewport is a defect) and every
page error or console error.

Run:  python docs/design/restyle/shoot.py <direction>
"""
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
folder = HERE / sys.argv[1]
out = folder / "shots"
out.mkdir(exist_ok=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
H.log_message = lambda *a: None
srv = socketserver.TCPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/"

SHOTS = [("home", "home.html", None), ("home-answer", "home.html", "demoAnswer"),
         ("home-reader", "home.html", "demoReader"), ("mp", "mp.html", None),
         ("debate", "debate.html", None)]
VIEWS = [("desk", 1828, 1029, False), ("deskfull", 1828, 1029, True), ("phone", 390, 844, False)]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, path, fn in SHOTS:
        for view, w, h, full in VIEWS:
            for scheme in ("light", "dark"):
                pg = b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
                pg.on("pageerror", lambda e, n=name: errs.append(f"{n}: {e}"))
                pg.on("console", lambda m, n=name: m.type == "error" and errs.append(f"{n}: {m.text}"))
                pg.goto(base + path, wait_until="networkidle")
                pg.wait_for_timeout(500)
                if fn:
                    if not pg.evaluate(f"typeof window.{fn} === 'function'"):
                        pg.close()
                        continue
                    try:
                        pg.evaluate(f"window.{fn}()")
                        pg.wait_for_timeout(400)
                    except Exception as e:  # noqa: BLE001
                        errs.append(f"{name} {view}: {str(e)[:160]}")
                sw = pg.evaluate("document.documentElement.scrollWidth")
                pg.screenshot(path=str(out / f"{name}-{view}-{scheme}.png"), full_page=full)
                flag = "  WIDER THAN THE VIEWPORT" if sw > w else ""
                print(f"{name}-{view}-{scheme} scrollWidth {sw}{flag}", flush=True)
                pg.close()
    b.close()
srv.shutdown()
print("errors:", errs or "none")
