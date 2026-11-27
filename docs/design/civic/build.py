import json, re, html, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "civic"
d = json.loads((ROOT / "data.json").read_text(encoding="utf8"))
E = lambda s: html.escape(str(s), quote=True)

def ic(name, cls="i"):
    p = {
     "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
     "spark": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
     "draft": '<path d="M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4"/>',
     "ext": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
     "chev": '<path d="M6 9l6 6 6-6"/>',
     "ask": '<path d="M4 5h16v11H9l-5 4z"/>',
     "acts": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>',
     "sit": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
     "q": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',
     "commit": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
     "mp": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.5-3.5 3.2-5.5 6.5-5.5s6 2 6.5 5.5M16 5a3.2 3.2 0 0 1 0 6M18 14.8c2 .6 3.2 2.3 3.5 5"/>',
     "bill": '<path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4M10 12h6M10 16h6"/>',
     "topic": '<path d="M3 12l9-9h8v8l-9 9z"/><circle cx="16" cy="8" r="1.2"/>',
     "dots": '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
     "left": '<path d="M15 6l-6 6 6 6"/>',
     "right": '<path d="M9 6l6 6-6 6"/>',
     "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
     "pin": '<path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
     "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
     "shield": '<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
     "scale": '<path d="M12 4v16M6 20h12M5 8h14M5 8l-2.5 6a3 3 0 0 0 5 0zM19 8l-2.5 6a3 3 0 0 0 5 0z"/>',
     "text": '<path d="M5 6h14M5 11h14M5 16h9"/>',
    }[name]
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{p}</svg>'

def fdate(s, short=True):
    x = dt.date.fromisoformat(s)
    return f"{x.day} {x.strftime('%b %Y')}" if short else f"{x.day} {x.strftime('%B %Y')}"

def ncomma(n): return f"{n:,}"

CH = {"DR": "Dewan Rakyat", "KK": "Special Chamber (Kamar Khas)"}

DEFS = '''<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<pattern id="songket" width="32" height="16" patternUnits="userSpaceOnUse">
<path d="M16 1.5L24.5 8 16 14.5 7.5 8z" fill="none" style="stroke:var(--motif)" stroke-width="1.4"/>
<path d="M16 5.2L20 8 16 10.8 12 8z" style="fill:var(--accent)"/>
<path d="M0 8h5.5M26.5 8H32" style="stroke:var(--motif)" stroke-width="1.4"/>
<path d="M0 0l3 3M0 16l3-3M32 0l-3 3M32 16l-3-3" style="stroke:var(--motif)" stroke-width="1.1"/>
</pattern>
<pattern id="songket-inv" width="48" height="24" patternUnits="userSpaceOnUse">
<path d="M24 2L36 12 24 22 12 12z" fill="none" style="stroke:var(--motif-inv)" stroke-width="1.6"/>
<path d="M24 7.5L30 12 24 16.5 18 12z" fill="none" style="stroke:var(--motif-inv)" stroke-width="1.6"/>
<path d="M0 12h9M39 12h9M0 0l4 4M0 24l4-4M48 0l-4 4M48 24l-4-4" style="stroke:var(--motif-inv)" stroke-width="1.6"/>
</pattern></defs></svg>'''

def divider(): return '<svg class="divider" aria-hidden="true"><rect width="100%" height="16" fill="url(#songket)"/></svg>'

NAV = [("Ask", "home.html", "ask"), ("Acts", "home.html#sources-line", "acts"), ("Sittings", "debate.html", "sit"),
       ("Questions", "debate.html#qa", "q"), ("Commitments", "mp.html#commitments", "commit"),
       ("MPs", "mp.html", "mp"), ("Bills", "debate.html#bill", "bill"), ("Topics", "home.html#topics", "topic")]

def head(title, desc):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;1,7..72,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{DEFS}'''

def header(active):
    links = "".join(f'<a href="{h}"{" aria-current=\"page\"" if n == active else ""}>{n}</a>' for n, h, _ in NAV)
    return f'''<header class="site-header"><div class="wrap">
<a class="brand" href="home.html" aria-label="Parlimen Search, home"><svg viewBox="0 0 34 34" aria-hidden="true"><rect width="34" height="34" rx="9" fill="#0A1F5C"/><path d="M17 6l9 11-9 11-9-11z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M17 12.5l4.6 4.5-4.6 4.5-4.6-4.5z" fill="#F5B800"/></svg>Parlimen Search</a>
<nav class="nav" aria-label="Main">{links}</nav>
<div class="lang" role="group" aria-label="Language"><button type="button" aria-pressed="true">EN</button><button type="button" aria-pressed="false" lang="ms">BM</button></div>
</div></header>'''

def bottom(active):
    pick = [("Ask", "home.html", "ask"), ("Sittings", "debate.html", "sit"), ("Questions", "debate.html#qa", "q"), ("MPs", "mp.html", "mp")]
    items = "".join(f'<a href="{h}"{" aria-current=\"page\"" if n == active else ""}>{ic(i)}<span>{n}</span></a>' for n, h, i in pick)
    sheet = "".join(f'<a href="{h}">{ic(i)}{n}</a>' for n, h, i in NAV)
    return f'''<nav class="bottom-nav" aria-label="Main, phone">{items}<button type="button" id="more-btn" aria-expanded="false" aria-controls="more-sheet">{ic("dots")}<span>More</span></button></nav>
<div class="sheet" id="more-sheet" hidden>{sheet}</div>'''

def footer():
    return f'''<footer class="site-footer"><div class="wrap">
{divider()}
<p id="sources-line">{ic("acts")}<span><b>Sources.</b> The principal Acts of Malaysia and the Hansard of the Dewan Rakyat and its Special Chamber, 14th and 15th Parliaments (2018 to now), as published by Parliament at parlimen.gov.my. Quoted text is verbatim.</span></p>
<p>{ic("spark")}<span><b>AI.</b> Summaries, question and answer pairs, and the plain-language wording of commitments are written by AI and always sit beside the verbatim text they come from. They can be wrong: check the quote.</span></p>
<p>{ic("scale")}<span><b>Not legal advice.</b> This is a search of the public record. It does not advise on your own case.</span></p>
</div></footer>'''

LABEL_AI = lambda t="AI summary": f'<span class="label-ai">{ic("spark")}{t}</span>'
DRAFT = lambda t="Unrevised draft": f'<span class="draft">{ic("draft")}{t}</span>'

def page(title, desc, active, body, script=True, extra=""):
    return head(title, desc) + header(active) + f'\n<main id="main">\n{body}\n</main>\n{footer()}\n{bottom(active)}\n{extra}\n<script src="app.js"></script>\n</body>\n</html>\n'

# ---------------------------------------------------------------- charts
def bar_chart(width, height, data, label, yr_every=1):
    # continuous month axis
    def idx(m): y, mo = map(int, m.split("-")); return y * 12 + mo - 1
    first, last = idx(data[0]["month"]), idx(data[-1]["month"])
    n = last - first + 1
    L, R, T, B = 30, 6, 26, 24
    pw, ph = width - L - R, height - T - B
    mx = 40
    bw = pw / n
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{E(label)}"><title>{E(label)}</title>']
    for v in (0, 10, 20, 30, 40):
        y = T + ph - ph * v / mx
        parts.append(f'<line class="grid-l" x1="{L}" x2="{width-R}" y1="{y:.1f}" y2="{y:.1f}"/><text x="{L-6}" y="{y+4:.1f}" text-anchor="end">{v}</text>')
    peak = max(data, key=lambda r: r["items"])
    for r in data:
        x = L + (idx(r["month"]) - first) * bw
        h = ph * r["items"] / mx
        cls = "bar peak" if r is peak else "bar"
        mm = dt.date(int(r["month"][:4]), int(r["month"][5:]), 1).strftime("%b %Y")
        parts.append(f'<rect class="{cls}" x="{x+0.25:.2f}" y="{T+ph-h:.1f}" width="{max(bw-0.5,1):.2f}" height="{h:.1f}" rx="1"><title>{mm}: {r["items"]} items</title></rect>')
    for y in range(first // 12, last // 12 + 1):
        x = L + max(0, y * 12 - first) * bw
        parts.append(f'<text x="{x+2:.1f}" y="{height-6}">{y}</text>')
    px = L + (idx(peak["month"]) - first) * bw + bw / 2
    anchor = "end" if px > width * 0.75 else "middle"
    pm = dt.date(int(peak["month"][:4]), int(peak["month"][5:]), 1).strftime("%b %Y")
    parts.append(f'<text class="val" x="{px:.1f}" y="{T+ph-ph*peak["items"]/mx-6:.1f}" text-anchor="{anchor}">{peak["items"]} items, {pm}</text>')
    parts.append('</svg>')
    return "".join(parts)

def trend_card(name, rows):
    W, H = 240, 96
    L, B, T = 4, 18, 18
    mx = max(r["n"] for r in rows)
    n = len(rows); bw = (W - L * 2) / n
    peak = max(rows, key=lambda r: r["n"])
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(name)} by year, peak {peak["year"]}: {ncomma(peak["n"])}">']
    for i, r in enumerate(rows):
        h = (H - T - B) * r["n"] / mx
        x = L + i * bw
        cls = "bar peak" if r is peak else "bar"
        s.append(f'<rect class="{cls}" x="{x+3:.1f}" y="{H-B-h:.1f}" width="{bw-6:.1f}" height="{h:.1f}" rx="2"><title>{r["year"]}: {ncomma(r["n"])}</title></rect>')
        if i in (0, n - 1) or (r is peak and 1 < i < n - 2):
            s.append(f'<text x="{x+bw/2:.1f}" y="{H-4}" text-anchor="middle">{r["year"]}</text>')
    px = L + rows.index(peak) * bw + bw / 2
    s.append(f'<text class="val" x="{min(max(px,22),W-22):.1f}" y="{H-B-(H-T-B)-4+0:.1f}" text-anchor="middle">{ncomma(peak["n"])}</text>')
    s.append('</svg>')
    total = sum(r["n"] for r in rows)
    return f'<div class="card chart-card"><h3>{E(name.capitalize())}</h3><div class="sub tnum">{ncomma(total)} items, 2018 to 2026</div>{"".join(s)}</div>'

# ---------------------------------------------------------------- HOME
def build_home():
    a, h = d["answer"], d["home"]
    demo = {"question": a["question"], "answer": a["answer"], "sources": a["sources"]}
    demo_json = json.dumps(demo, ensure_ascii=False).replace("</", "<\\/")
    parties = ["AMANAH", "BERSATU", "DAP", "PAS", "UMNO"]
    topics_opts = "".join(f'<option>{E(t["name"])}</option>' for t in sorted(h["topics"], key=lambda x: x["name"].lower()))
    party_opts = "".join(f"<option>{p}</option>" for p in parties)
    stage_names = {"bm25": "Keyword search", "dense": "Meaning search", "fused": "Both lists combined", "reranked": "Best matches re-ranked"}
    mxms = max(s["ms"] for s in a["stages"]) or 1
    rows = "".join(f'<tr><td>{stage_names[s["name"]]}</td><td class="r">{s["hits"]}</td><td class="r">{s["ms"]/1000:.1f} s</td><td style="width:26%"><span class="stage-bar" style="width:{max(2, 100*s["ms"]/mxms):.0f}%"></span></td></tr>' for s in a["stages"])
    sit = ""
    for s in h["latest_sittings"]:
        dr = f'<span class="draft">{ic("draft")}Unrevised draft</span>' if s["draft"] else '<span>Revised</span>'
        sit += f'<a class="card sit" href="debate.html"><span class="ch">{CH[s["chamber"]]}</span><span class="d tnum">{fdate(s["date"], False)}</span><span class="row"><span class="tnum">{s["items"]} agenda items</span>{dr}</span></a>'
    com = ""
    for c in h["latest_commitments"]:
        spk = re.sub(r"\s*\[.*?\]", "", c["speaker"]) if "[" in c["speaker"] and c["speaker"].split("[")[0].strip() != "" and c["speaker"].split("[")[0].strip().startswith(("Timbalan", "Menteri")) else c["speaker"]
        who = c["speaker"].split("[")[1].rstrip("]") if "[" in c["speaker"] else c["speaker"]
        com += f'''<article class="card commit"><div><span class="label-rec">Verbatim, {fdate(c["date"])}</span><blockquote class="rec rec-quote" lang="ms"><span>{E(c["quote"])}</span></blockquote></div>
<div class="ai">{LABEL_AI("AI paraphrase")}<p>{E(c["promise"])}</p></div><div class="who">{E(who)}, {E(c["office"])}</div><a class="linkbtn" href="debate.html">Open the debate</a></article>'''
    topics = "".join(f'<a class="chip" href="#">{E(t["name"])}<span class="n">{ncomma(t["n"])}</span></a>' for t in h["topics"])
    tt = {}
    for r in h["topic_trend"]: tt.setdefault(r["name"], []).append(r)
    order = sorted(tt, key=lambda k: -sum(r["n"] for r in tt[k]))
    cards = "".join(trend_card(k, sorted(tt[k], key=lambda r: r["year"])) for k in order)
    m = h["meta"]
    body = f'''<div class="wrap">
<section class="hero" aria-labelledby="h1">
<svg class="texture" aria-hidden="true"><rect width="100%" height="100%" fill="url(#songket-inv)"/></svg>
<span class="eyebrow">Malaysia's Acts and Dewan Rakyat debates, searched together</span>
<h1 id="h1">Ask Parliament, get <span class="hl">answers</span> with receipts.</h1>
<p class="sub">Plain answers in English or Bahasa Melayu. Every sentence points to an Act section or a speech in Hansard, so you can check it yourself.</p>
<form class="ask" id="ask-form" role="search" autocomplete="off">
<label class="sr-only" for="q">Ask a question</label>
<div class="ask-field">{ic("search")}<input id="q" name="q" type="text" placeholder="" enterkeyhint="search"><button class="ask-go" type="submit">{ic("spark")}<span class="go-text">Ask</span><span class="sr-only">Ask</span></button></div>
<div class="try"><span class="k">Try</span>
<button type="button" data-example><span class="lg">EN</span>What has the government said about targeted diesel subsidies?</button>
<button type="button" data-example lang="ms"><span class="lg">BM</span>Apakah kata kerajaan tentang subsidi diesel bersasar?</button></div>
<div class="filters" role="group" aria-label="Filters">
<label class="fchip"><span class="k">Search in</span><select><option>Acts and debates</option><option>Acts only</option><option>Debates only</option></select></label>
<label class="fchip"><span class="k">Parliament</span><select><option>Any</option><option>14th</option><option>15th</option></select></label>
<label class="fchip"><span class="k">Chamber</span><select><option>Both</option><option>Dewan Rakyat</option><option>Special Chamber</option></select></label>
<label class="fchip"><span class="k">Topic</span><select><option>Any</option>{topics_opts}</select></label>
<button type="button" class="more-filters" id="more-filters" aria-expanded="false" aria-controls="extra-filters"><span class="mf-t">More filters</span>{ic("chev","i sm")}</button>
<div class="extra" id="extra-filters" hidden>
<label class="fchip"><span class="k">From</span><input type="date" aria-label="From date"></label>
<label class="fchip"><span class="k">To</span><input type="date" aria-label="To date"></label>
<label class="fchip"><span class="k">Party</span><select><option>Any</option>{party_opts}</select></label>
<label class="fchip"><span class="k">Speaker</span><input type="text" placeholder="Name"></label>
<label class="fchip"><span class="k">Act</span><input type="text" placeholder="e.g. Act 265"></label>
</div></div>
</form>
</section>

<div class="stats" aria-label="The record in numbers">
<div><b>{ncomma(m["units"])}</b><span>agenda items</span></div>
<div><b>{ncomma(m["speeches"])}</b><span>speeches</span></div>
<div><b>{ncomma(m["qa"])}</b><span>oral questions answered</span></div>
<div><b>{ncomma(m["commitments"])}</b><span>ministers' commitments</span></div>
</div>

<section id="answer" hidden aria-label="Answer">
<div class="q-echo">{LABEL_AI("AI answer")}<q id="q-echo-text"></q></div>
<div class="answer-grid">
<div class="card pad answer-card" id="answer-card" aria-live="polite" aria-busy="false">
<div class="head"><h2 style="font-size:20px;font-weight:650">Answer</h2><span class="meta">Every claim carries a source mark. Tap or hover a mark to preview it.</span></div>
<div class="answer-text" id="answer-text"></div>
<div class="answer-foot" id="answer-foot" hidden>{ic("info")}<span>Written by AI from the passages on the right. Check the quotes before relying on a sentence.</span></div>
<p class="demo-note">Prototype note: this demo streams one saved real answer, whichever question you pick.</p>
</div>
<aside class="sources" id="sources" hidden aria-label="Sources"><h3>Sources <span>{len(a["sources"])} passages, verbatim</span></h3><ol class="src-list" id="src-list"></ol></aside>
</div>
<details class="card fold" id="how" hidden><summary>{ic("search")}How it was found <span class="meta tnum">{a["search_ms"]/1000:.0f} s search</span>{ic("chev","i chev")}</summary>
<div class="body"><div class="scroll-x"><table class="stages"><thead><tr><th>Step</th><th class="r">Passages</th><th class="r">Time</th><th><span class="sr-only">Relative time</span></th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="meta" style="margin-top:12px">Total {a["total_ms"]/1000:.0f} s, of which searching {a["search_ms"]/1000:.0f} s. Filters: {E(a["filters"])}.</p></div></details>
</section>

<section class="section" id="sittings"><div class="section-head"><div><h2>Latest sittings</h2><p>The newest Hansard on the record. Drafts are unrevised and can change.</p></div><a class="linkbtn" href="debate.html">All sittings {ic("right","i sm")}</a></div>
<div class="grid c3">{sit}</div></section>

<section class="section" id="commitments"><div class="section-head"><div><h2>Latest commitments</h2><p>What ministers promised in the House, in their own words first.</p></div><a class="linkbtn" href="mp.html#commitments">All commitments {ic("right","i sm")}</a></div>
<div class="grid c3">{com}</div></section>

<section class="section" id="topics"><div class="section-head"><div><h2>Topics</h2><p>Agenda items by subject, 2018 to now.</p></div></div>
<div class="chips">{topics}</div></section>

<section class="section" id="trend"><div class="section-head"><div><h2>What Parliament talks about</h2><p>The six biggest topics, items per year. Yellow marks each topic's busiest year.</p></div></div>
<div class="charts">{cards}</div></section>
</div>
<script type="application/json" id="demo-data">{demo_json}</script>
<div class="peek" id="peek" role="dialog" aria-label="Source preview" hidden><div class="cl"><span class="num"></span><span class="cl-t"></span></div><blockquote class="rec" lang="ms"></blockquote><button type="button" class="linkbtn go">Jump to source {ic("right","i sm")}</button></div>'''
    (OUT / "home.html").write_text(page("Parlimen Search: ask Parliament", "Ask Malaysia's Acts and Dewan Rakyat debates in English or Malay and get answers with sources.", "Ask", body), encoding="utf8")

# ---------------------------------------------------------------- MP
def build_mp():
    m = d["mp"]
    ini = "".join(w[0].upper() for w in m["name_key"].split()[:2])
    seat = m["seats"][-1]
    offices = "".join(f'<div class="office">{ic("shield")}<div><b>{E(o["office"])}</b><div class="meta tnum">{fdate(o["first"], False)} to {fdate(o["last"], False)}, {o["n"]} commitments recorded</div></div></div>' for o in m["offices"])
    c = m["counts"]
    tiles = [("items_spoken", "agenda items spoken in"), ("questions_answered", "questions answered"), ("questions_asked", "questions asked"), ("commitments", "commitments made")]
    stats = "".join(f'<div><b>{ncomma(c[k])}</b><span>{t}</span></div>' for k, t in tiles)
    wide = bar_chart(740, 300, m["activity_by_month"], "Agenda items per month, July 2018 to October 2026")
    narrow = bar_chart(350, 230, m["activity_by_month"], "Agenda items per month, July 2018 to October 2026")
    topics = "".join(f'<a class="chip" href="home.html#topics">{E(t["name"])}<span class="n">{t["n"]}</span></a>' for t in m["top_topics"])
    cm = ""
    for r in m["recent_commitments"]:
        facts = ""
        if r["deadline"]: facts += f'<span>Deadline <b lang="ms">{E(r["deadline"])}</b></span>'
        if r["amount"]: facts += f'<span class="clamp">Amount <b lang="ms">{E(r["amount"])}</b></span>'
        kind = "Promise" if r["kind"] == "promise" else "Routine reply"
        cm += f'''<article class="card cm" id="{r["id"]}"><div class="head"><span class="label-rec">Verbatim, {fdate(r["date"], False)}</span><span class="meta">{kind}, {E(r["office"])}</span></div>
<blockquote class="rec rec-quote" lang="ms"><span>{E(r["quote"])}</span></blockquote>
<div class="ai">{LABEL_AI("AI paraphrase")}<p>{E(r["promise"])}</p></div>
{f'<div class="facts-row">{facts}</div>' if facts else ''}
<div><a class="linkbtn" href="debate.html">Open the debate {ic("right","i sm")}</a></div></article>'''
    qa = ""
    for r in m["recent_answers"]:
        qa += f'''<article class="card qa"><div class="pair"><div>{LABEL_AI("AI summary of the question")}<p>{E(r["question"])}</p></div><div>{LABEL_AI("AI summary of the answer")}<p>{E(r["answer"])}</p></div></div>
<div class="foot"><span>Asked by <b>{E(r["asker"])}</b>, {fdate(r["date"], False)}</span><a class="linkbtn" href="debate.html">Read the exchange {ic("right","i sm")}</a></div></article>'''
    parl = ", ".join(str(s["parliament"]) for s in m["seats"])
    body = f'''<div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="home.html">Ask</a>{ic("right")}<a href="mp.html">MPs</a>{ic("right")}<span>{E(m["name_key"].title())}</span></nav>
<section class="card profile" aria-labelledby="h1"><div class="band">{divider()}</div>
<div class="inner"><div class="avatar" aria-hidden="true">{ini}</div>
<div><span class="eyebrow">Member of Parliament</span><h1 id="h1" style="margin-top:6px">{E(m["name"])}</h1>
<div class="facts"><div>{ic("pin","i sm")}<span><b>{E(seat["seat"])}</b> ({seat["code"]})</span></div><div>{ic("mp","i sm")}<span><b>{E(m["parties"][-1]["party"])}</b>, Parliaments {parl}</span></div></div></div></div></section>
<div class="stats" style="margin-top:20px">{stats}</div>
<div class="two">
<section class="card pad chart-big" aria-labelledby="act-h"><h2 id="act-h">Activity by month</h2><p class="sub">Agenda items this MP spoke in. Gaps are months Parliament did not sit.</p>
<div class="only-wide">{wide}</div><div class="only-narrow">{narrow}</div></section>
<div class="stack">
<section class="card pad box" aria-labelledby="off-h"><h2 id="off-h">Offices held</h2><div style="margin-top:8px">{offices}</div></section>
<section class="card pad box" aria-labelledby="top-h"><h2 id="top-h">Most spoken topics</h2><p class="sub">Agenda items by topic.</p><div class="chips" style="margin-top:12px">{topics}</div></section>
</div></div>
<section class="section" id="commitments"><div class="section-head"><div><h2>Recent commitments</h2><p>The quote comes first. The AI paraphrase underneath is a reading aid, not the record.</p></div></div><div class="commit-list">{cm}</div></section>
<section class="section" id="answers"><div class="section-head"><div><h2>Recent questions answered</h2><p>Both the question and the answer are AI summaries. Open the exchange for the verbatim words.</p></div></div><div class="qa-list">{qa}</div></section>
</div>'''
    (OUT / "mp.html").write_text(page(f'{m["name_key"].title()}: MP profile', "Offices, activity, topics and commitments.", "MPs", body), encoding="utf8")

# ---------------------------------------------------------------- DEBATE
def paras(text, mx):
    lines = text.split("\n")
    out, cur = [], ""
    for i, ln in enumerate(lines):
        if cur.endswith("-") and not cur.endswith(" -"): cur = cur[:-1] + ln.strip()
        else: cur = (cur + " " + ln.strip()).strip()
        if ln.rstrip()[-1:] in ".?!" and len(ln) < mx * 0.8 and i < len(lines) - 1:
            out.append(cur); cur = ""
    if cur: out.append(cur)
    return out

def build_debate():
    g, b = d["debate"], d["bill"]
    s = g["sitting"]
    topics = "".join(f'<a class="chip" href="home.html#topics">{E(t)}</a>' for t in json.loads(g["topics"]))
    turns = ""
    for r in g["speech_rows"]:
        lab = r["label"]; role = ""
        if "[" in lab:
            pre = lab.split("[")[0].strip()
            if pre != r["name"]: role = pre
        ini = "".join(w[0].upper() for w in r["member"].split("-")[:2])
        chair = role.startswith("Timbalan Yang di-Pertua")
        gov = "Menteri" in role
        t = r["time"]; tm = f'{t[:2]}:{t[2:]}'
        ps = paras(r["text"], max(len(x) for x in r["text"].split("\n")))
        if len(ps) > 2:
            first = "".join(f"<p>{E(p)}</p>" for p in ps[:2]); rest = "".join(f"<p>{E(p)}</p>" for p in ps[2:])
            txt = f'{first}<details><summary>{ic("chev","i sm")}Read the full speech ({len(ps)-2} more paragraphs)</summary>{rest}</details>'
        else:
            txt = "".join(f"<p>{E(p)}</p>" for p in ps)
        cls = "turn chair" if chair else ("turn gov" if gov else "turn")
        seatline = f'{E(r["seat"])}' if not chair else "Chair"
        turns += f'''<article class="{cls}" id="seq-{r["seq"]}"><div class="av" aria-hidden="true">{ini}</div><div>
<div class="who"><b>{E(r["name"])}</b>{f'<span class="role">{E(role)}</span>' if role else ''}<span class="meta">{seatline}</span><span class="party">{E(r["party"])}</span>
<span class="tm"><span class="tnum">{tm}</span><a href="{s["pdf"]}#page={r["page_start"]}" target="_blank" rel="noopener">PDF p.{r["page_start"]}{ic("ext","i sm")}</a></span></div>
<div class="rec" lang="ms">{txt}</div></div></article>'''
    qa = ""
    for q in g["qa"]:
        figs = "".join(f'<span lang="ms">{E(f["value"])}</span>' for f in json.loads(q["figures"])[:5])
        qa += f'''<div class="qa-i"><div class="k">Question, {E(q["asker"])}</div><p>{E(q["question"])}</p><div class="k">Answer, {E(q["answerer"].split("[")[-1].rstrip("]"))}</div><p>{E(q["answer"])}</p><div class="figs" aria-label="Figures in the answer">{figs}</div><a class="linkbtn" href="#seq-{q["asker_seq"]}">Read the question {ic("right","i sm")}</a></div>'''
    cr = ""
    for c in g["commitment_rows"]:
        dl = f'<div class="meta">Deadline <b lang="ms">{E(c["deadline"])}</b></div>' if c["deadline"] else ""
        cr += f'<div class="c-i"><blockquote class="rec rec-quote" lang="ms"><span>{E(c["quote"])}</span></blockquote><div>{LABEL_AI("AI paraphrase")}</div><p>{E(c["promise"])}</p>{dl}<a class="linkbtn" href="#seq-{c["seq"]}">Jump to the speech {ic("right","i sm")}</a></div>'
    # bill
    tl = b["timeline"]
    first = tl[0]; rest = [x for x in tl if x["date"] != first["date"]]
    gap = (dt.date.fromisoformat(rest[0]["date"]) - dt.date.fromisoformat(first["date"])).days
    sp2 = sum(x["speeches"] for x in rest)
    items = "".join(f'<div class="bi"><div class="h"><a href="debate.html">{fdate(x["date"])}, item {int(x["id"][-3:])}</a><span class="tnum">{x["speeches"]} speeches</span></div><p>{E(x["summary_en"])}</p></div>' for x in tl)
    bill = f'''<section class="bill" id="bill" aria-labelledby="bill-h"><div class="card headcard">
<span class="eyebrow">This bill in Parliament</span><h2 id="bill-h" style="margin-top:8px">{E(b["title"].title().replace("(Pindaan)", "(Pindaan)"))}</h2>
<p class="act">Amends the {E(b["act_title_bi"].title())} (Act {b["act"]}), in Malay <span lang="ms">{E(b["act_title_bm"].title())}</span>. A sample bill record, shown here to preview how a bill's path through the House reads.</p>
<ol class="stepper" aria-label="Stages of the bill">
<li class="done"><span class="node" aria-hidden="true">1</span><h3>First reading</h3><div class="when tnum">{fdate(first["date"], False)}</div><p class="s">The bill was tabled. {first["speeches"]} speeches in 1 agenda item.</p></li>
<li class="now"><span class="node" aria-hidden="true">2</span><h3>Second and third reading</h3><div class="when tnum">{fdate(rest[0]["date"], False)}</div><span class="gap tnum">{gap} days after first reading</span><p class="s">Debated and passed in a single sitting: {len(rest)} agenda items, {sp2} speeches.</p></li>
</ol></div>
<details class="bill-items card fold" style="margin-top:16px"><summary>{ic("text")}All {len(tl)} agenda items for this bill{ic("chev","i chev")}</summary><div class="body"><p class="meta" style="margin-bottom:10px">{LABEL_AI("AI summary")} each item is summarised below, linked to its record page.</p><div class="box card" style="box-shadow:none">{items}</div></div></details></section>'''
    nb = g["neighbours"]
    body = f'''<div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="home.html">Ask</a>{ic("right")}<a href="debate.html">Sittings</a>{ic("right")}<span class="tnum">{fdate(s["date"], False)}</span>{ic("right")}<span>Item {g["ord"]}</span></nav>
<section class="card dh" aria-labelledby="h1"><div class="kicker"><span>{CH[s["chamber"]]}</span><span class="tnum">{fdate(g["date"], False)}</span><span>Parliament {g["parliament"]}, {E(s["term"])}</span><span>Item {g["ord"]}, from PDF p.{g["page_start"]}</span></div>
<h1 id="h1" lang="ms">{E(g["business"].title())}</h1>
<p class="sub">{g["speeches"]} speeches. Heading as printed in Hansard.</p>
<div class="draft-note" role="note">{ic("draft")}<div><b>Unrevised draft.</b> This sitting's Hansard has not been revised by Parliament yet. Wording and page numbers may change when the final version is published. <a href="{s["pdf"]}" target="_blank" rel="noopener">Official PDF</a></div></div></section>
<section class="card happened" aria-labelledby="wh"><div class="head"><div>{LABEL_AI("AI summary")}<h2 id="wh">What happened</h2></div>
<div class="tabs" id="tabs" data-for="sum" role="group" aria-label="Summary language"><button type="button" data-l="en" aria-pressed="true">English</button><button type="button" data-l="ms" aria-pressed="false" lang="ms">Melayu</button></div></div>
<div id="sum" class="summary-more"><p class="summary-text clamped" id="sum-en" data-lang="en" style="margin-top:12px">{E(g["summary_en"])}</p><p class="summary-text clamped" id="sum-ms" data-lang="ms" lang="ms" hidden style="margin-top:12px">{E(g["summary_ms"])}</p><button type="button" class="linkbtn" id="sum-toggle" aria-expanded="false"><span class="t">Read the whole summary</span>{ic("chev","i sm")}</button></div>
<div class="topic-row"><span class="meta">Topics</span>{topics}</div></section>
<div class="layout">
<section aria-labelledby="tr"><div class="transcript-head"><div><span class="label-rec">{ic("text","i sm")} Verbatim record</span><h2 id="tr" style="margin-top:4px">Speeches</h2></div><a class="linkbtn" href="{s["pdf"]}" target="_blank" rel="noopener">Official PDF {ic("ext","i sm")}</a></div>
<div class="turns">{turns}</div></section>
<aside class="aside" aria-label="Around this item">
<section class="card aside-box" id="qa" aria-labelledby="qa-h"><h2 id="qa-h">Questions and answers {LABEL_AI("AI summary")}</h2>{qa}</section>
<section class="card aside-box" aria-labelledby="cm-h"><h2 id="cm-h">Commitments in this item</h2>{cr}</section>
</aside></div>
<nav class="pn" aria-label="Previous and next item"><a class="card" href="debate.html"><span class="d">{ic("left","i sm")}Previous item</span><span class="t tnum">Item {int(nb[0]["id"][-3:])}, oral questions</span></a><a class="card" href="debate.html"><span class="d">Next item{ic("right","i sm")}</span><span class="t tnum">Item {int(nb[1]["id"][-3:])}, oral questions</span></a></nav>
{bill}
</div>'''
    (OUT / "debate.html").write_text(page("Oral questions, 22 Oct 2026: debate record", "Sitting record with verbatim speeches and an AI summary.", "Sittings", body), encoding="utf8")

build_home(); build_mp(); build_debate()
print("ok")
