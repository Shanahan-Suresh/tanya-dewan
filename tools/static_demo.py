"""Build the static demo: a sample of the site's real pages plus the recorded answers, as plain files
for GitHub Pages. No server runs behind it, so visitors cannot ask new questions.

The pages render through the app itself (FastAPI's TestClient) from data/site.db, with no model
loaded, in English at the root and in Malay under ms/. Every site link becomes a relative file path;
a link to a page outside the sample goes to not-in-demo.html. The answers come from
tools/record_answers.py (docs/demo/answers/).

Run:  .venv\\Scripts\\python.exe tools\\static_demo.py [--out build/demo] [--base /tanya-dewan/]
Then check:  .venv\\Scripts\\python.exe tools\\static_demo.py --check-only
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ANSWERS = ROOT / "docs" / "demo" / "answers"
STATIC = ROOT / "parlimen" / "web" / "static"
REPO = "https://github.com/Shanahan-Suresh/tanya-dewan"
PAGES_URL = "https://shanahan-suresh.github.io/tanya-dewan"
MISSING = "not-in-demo.html"
LANG_DIR = {"en": "", "ms": "ms/"}

# Pages every visitor reaches from the menu; the rest come from the answers and the home page.
MENU = ["/", "/about", "/how-it-works", "/law", "/hansard", "/questions", "/commitments", "/mp", "/bills", "/topics",
        "/not-in-demo"]
ATTR = re.compile(r'\b(href|src|action)="([^"]*)"')
HX = re.compile(r'\s+hx-[a-z-]+="[^"]*"')
MISSES: Counter = Counter()  # site paths that went to not-in-demo.html, for the build report


def file_for(path: str) -> str:
    """The output file of a site path, relative to a language root: "/" is index.html, "/a/b" is a/b.html."""
    p = unquote(path).strip("/")
    if not p:
        return "index.html"
    p = re.sub(r"[^A-Za-z0-9._/-]+", "-", p)
    return p + ".html"


def rewrite(page_html: str, here: str, lang: str, pages: dict[str, str]) -> str:
    """Turn every site link in one rendered page into a relative file path.

    `here` is the page's own output file (with its language folder), `pages` maps a site path (with
    its query, if any) to its output file inside a language root.
    """
    up = "../" * here.count("/")
    root = up + LANG_DIR[lang]

    def one(m: re.Match) -> str:
        attr, raw = m.group(1), m.group(2)
        url = html.unescape(raw)
        if not url.startswith("/") or url.startswith("//"):
            return m.group(0)                      # external, mailto, #fragment, already relative
        if url.startswith("/static/"):
            return f'{attr}="{up}static/{url[8:].split("?")[0]}"'
        if url == "/favicon.ico":
            return f'{attr}="{up}favicon.ico"'
        parts = urlsplit(url)
        if parts.path.startswith("/hl/"):          # the language switch: the same page, other tree
            other = parts.path[4:]
            nxt = parse_qs(parts.query).get("next", ["/"])[0]
            target = pages.get(nxt.split("#")[0])
            dest = (target if target else MISSING) if other in LANG_DIR else MISSING
            return f'{attr}="{html.escape(up + LANG_DIR.get(other, "") + dest)}"'
        key = parts.path + (f"?{parts.query}" if parts.query else "")
        target = pages.get(key) or pages.get(parts.path if not parts.query else "\0")
        frag = f"#{parts.fragment}" if parts.fragment and target else ""
        if not target:
            MISSES[key] += 1
        return f'{attr}="{html.escape(root + (target or MISSING) + frag)}"'

    out = ATTR.sub(one, page_html)
    out = HX.sub("", out)
    return out.replace('<script src="' + up + 'static/htmx.min.js" defer></script>', "")


def links_in(page_html: str) -> list[str]:
    return [html.unescape(v) for a, v in ATTR.findall(page_html)]


def check(out: Path) -> list[str]:
    """Every relative link in every page and answer file must name a file that exists."""
    bad = []
    for f in out.rglob("*.html"):
        if f.name == "404.html":
            continue
        for url in links_in(f.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+:|^//|^#", url) or not url:
                continue
            target = (f.parent / url.split("#")[0].split("?")[0]).resolve()
            if not target.exists():
                bad.append(f"{f.relative_to(out)}: {url}")
    jump = out / "jump.json"
    for x in json.loads(jump.read_text(encoding="utf-8")) if jump.exists() else []:
        for lang_dir in LANG_DIR.values():
            if not (out / lang_dir / x["u"]).exists():
                bad.append(f"jump.json: {lang_dir}{x['u']}")
    for f in out.rglob("answers/*.json"):
        home = f.parent.parent
        done = json.loads(f.read_text(encoding="utf-8"))["events"][-1]["data"]
        for item in (done.get("sources") or []) + (done.get("passages") or []):
            url = item.get("url") or ""
            if url and not (home / url.split("#")[0]).exists():
                bad.append(f"{f.relative_to(out)}: {url}")
    return bad


def answer_paths(done: dict) -> list[str]:
    return [x["url"].split("#")[0] for x in (done.get("sources") or []) + (done.get("passages") or []) if x.get("url")]


def clear(out: Path) -> None:
    """Move the last build to the Recycle Bin through the author's trash.py; elsewhere, ask for it gone."""
    if not out.exists():
        return
    trash = Path.home() / ".claude" / "hooks" / "trash.py"
    if trash.exists():
        subprocess.run([sys.executable, str(trash), str(out)], check=True)
    if out.exists():
        sys.exit(f"{out} exists; delete it, then build again")


def build(out: Path, base: str) -> None:
    from fastapi.testclient import TestClient

    from parlimen.web.app import create_app

    recorded = sorted(ANSWERS.glob("*.json"))
    if not recorded:
        sys.exit("no recorded answers in docs/demo/answers; run tools/record_answers.py first")
    answers = [json.loads(f.read_text(encoding="utf-8")) for f in recorded]
    demo = {"repo": REPO, "recorded": max(a["recorded"] for a in answers),
            "answers": [{"q": a["question"], "lang": a["lang"], "file": f"answers/{f.name}"}
                        for a, f in zip(answers, recorded)]}
    app = create_app(demo=demo, site_url=PAGES_URL)
    clients = {}
    for lang in LANG_DIR:
        c = TestClient(app)
        c.cookies.set("hl", lang)
        clients[lang] = c

    def get(path: str) -> tuple[str, str] | None:
        r = clients["en"].get(path, follow_redirects=True)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            print(f"skip {path}: {r.status_code}", flush=True)
            return None
        final = r.url.path + (f"?{r.url.query.decode() if isinstance(r.url.query, bytes) else r.url.query}"
                              if r.url.query else "")
        return final, r.text

    # The page set: the menu, every page an answer cites, the home page's sittings, debates and
    # topics, every MP on the MPs list, two bills, then the sittings the debates link most.
    wanted = list(MENU)
    for a in answers:
        wanted += answer_paths(a["events"][-1]["data"])
    pages: dict[str, str] = {}
    redirect: dict[str, str] = {}
    texts: dict[str, str] = {}

    def add(path: str) -> None:
        if path in pages or path in redirect:
            return
        got = get(path)
        if not got:
            return
        final, text = got
        if final != path:
            redirect[path] = final
        pages[final] = file_for(final.split("?")[0])
        texts[final] = text

    for p in wanted:
        add(p)
    home_links = links_in(texts["/"])
    for u in home_links:
        if re.match(r"^/(hansard/(DR|KK)/|debate/|topic/)", u):
            add(u.split("#")[0])
    for u in links_in(texts["/mp"]):                 # every MP of the current Parliament
        if u.startswith("/mp/"):
            add(u.split("#")[0])
    for u in links_in(texts["/topics"]):             # every topic, for the topics chart and the jump box
        if u.startswith("/topic/"):
            add(u.split("#")[0])
    for u in links_in(texts["/bills"]):
        if u.startswith("/bill/") and sum(p.startswith("/bill/") for p in pages) < 2:
            add(u.split("#")[0])
    debate_links = Counter(u.split("#")[0] for p, t in texts.items() if p.startswith("/debate/") for u in links_in(t))
    for u, _ in [x for x in debate_links.most_common() if x[0].startswith("/mp/")][:3]:
        add(u)
    for u, _ in [x for x in debate_links.most_common() if x[0].startswith("/hansard/")][:6]:
        add(u)
    for src, final in redirect.items():
        pages[src] = pages[final]

    clear(out)
    out.mkdir(parents=True)
    rendered = 0
    for lang, prefix in LANG_DIR.items():
        for path, file in sorted(set((p, f) for p, f in pages.items() if p not in redirect)):
            r = clients[lang].get(path)
            here = prefix + file
            dest = out / here
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rewrite(r.text, here, lang, pages), encoding="utf-8")
            rendered += 1
        (out / prefix / "answers").mkdir(parents=True, exist_ok=True)
        for a, f in zip(answers, recorded):
            for e in a["events"]:
                if e["event"] == "done":
                    for item in (e["data"].get("sources") or []) + (e["data"].get("passages") or []):
                        if item.get("url", "").startswith("/"):
                            path, _, frag = item["url"].partition("#")
                            target = pages.get(path)
                            item["url"] = (target + (f"#{frag}" if frag else "")) if target else MISSING
            (out / prefix / "answers" / f.name).write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")

    # The jump box's index: only the pages the demo holds, as file paths inside a language root.
    jump = [dict(x, u=pages[x["u"]]) for x in clients["en"].get("/jump.json").json() if x["u"] in pages]
    (out / "jump.json").write_text(json.dumps(jump, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    shutil.copytree(STATIC, out / "static")
    css = out / "static" / "site.css"
    css.write_text(css.read_text(encoding="utf-8").replace('url("/static/fonts/', 'url("fonts/'), encoding="utf-8")
    shutil.copy(STATIC / "favicon.ico", out / "favicon.ico")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    missing = (out / MISSING).read_text(encoding="utf-8")
    (out / "404.html").write_text(missing.replace("<head>", f'<head>\n<base href="{base}">', 1), encoding="utf-8")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    kinds = Counter()
    for k, n in MISSES.items():
        kinds[k.split("?")[0].split("/")[1] + ("?" if "?" in k else "")] += n
    print("links to not-in-demo, by kind:", ", ".join(f"{k} {n}" for k, n in kinds.most_common(10)), flush=True)
    print("distinct missing /mp/ pages:", len({k for k in MISSES if k.startswith("/mp/")}), flush=True)
    print(f"jump box: {len(jump)} pages", flush=True)
    print(f"{rendered} pages ({len(pages) - len(redirect)} per language), {len(answers)} answers, "
          f"{size / 1e6:.1f} MB in {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "demo")
    ap.add_argument("--base", default="/tanya-dewan/", help="the path GitHub Pages serves the demo under")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    if not a.check_only:
        build(a.out, a.base)
    bad = check(a.out)
    for b in bad[:40]:
        print("BROKEN", b)
    print(f"{len(bad)} broken links")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
