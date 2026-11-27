import json, html, re, datetime
from pathlib import Path
OUT = Path(__file__).resolve().parent
D = json.load(open(OUT.parent / "data.json", encoding="utf8"))
E = lambda s: html.escape(str(s), quote=True)

def fdate(s, short=False):
    d = datetime.date.fromisoformat(s)
    return d.strftime("%d %b %Y" if short else "%d %B %Y").lstrip("0")
def n(x): return f"{x:,}"
def chamber(c): return "Dewan Rakyat" if c == "DR" else "Special Chamber (Kamar Khas)"

ICONS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<symbol id="i-pen" viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></symbol>
<symbol id="i-spark" viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M18.5 16l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/></symbol>
<symbol id="i-ext" viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></symbol>
<symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></symbol>
<symbol id="i-chev" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></symbol>
<symbol id="i-moon" viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/></symbol>
<symbol id="i-link" viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></symbol>
<symbol id="i-doc" viewBox="0 0 24 24"><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></symbol>
</defs></svg>"""
def ic(name, cls="icon"): return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'
AI = lambda t="AI summary": f'<span class="ai">{ic("spark")}{t}</span>'
DRAFT = lambda t="Unrevised draft": f'<span class="draft">{ic("pen")}{t}</span>'

NAV = [("Ask", "home.html"), ("Acts", "#"), ("Sittings", "debate.html"), ("Questions", "#"), ("Commitments", "#"), ("MPs", "mp.html"), ("Bills", "#"), ("Topics", "#")]
HEAD_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">"""

def page(title, active, body, extra_head="", desc=""):
    nav = "".join(f'<a href="{h}"{" aria-current=\"page\"" if l == active else ""}>{l}</a>' for l, h in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="color-scheme" content="light dark">
{HEAD_LINKS}
{extra_head}
</head>
<body>
{ICONS}
<a class="skip" href="#main">Skip to the record</a>
<header class="mast">
  <div class="wrap mast-top">
    <span><span class="dateline-long">Thursday 26 November 2026 &middot; </span>Record to 22 October 2026</span>
    <span class="tools">
      <span class="seg" role="group" aria-label="Language"><button type="button" data-lang="en" aria-pressed="true">EN</button><button type="button" data-lang="ms" aria-pressed="false" title="Prototype: interface copy stays in English">BM</button></span>
      <button class="iconbtn" id="theme-toggle" type="button" aria-label="Switch between day and night edition">{ic("moon")}<span class="dateline-long">Night edition</span></button>
    </span>
  </div>
  <a class="brand" href="home.html"><span class="brand-name">Parlimen Search</span><span class="brand-tag">The searchable record of the Dewan Rakyat &middot; 2018 to now</span></a>
  <div class="nav-bar"><div class="wrap">
    <button class="nav-menu" id="nav-menu" type="button" aria-expanded="false" aria-controls="nav"><span>Sections</span>{ic("chev")}</button>
    <nav class="nav" id="nav" aria-label="Sections">{nav}</nav>
  </div></div>
</header>
<main id="main">
{body}
</main>
<footer class="foot"><div class="wrap cols">
  <p><strong>Sources</strong>Acts of Parliament and the Dewan Rakyat Hansard, as published at parlimen.gov.my and the Attorney General's Chambers. Speeches are shown verbatim, with the page of the official PDF.</p>
  <p><strong>Written by AI</strong>Summaries, answers, paraphrased commitments and question-answer pairs are written by AI and always labelled. Who spoke is decided by the parser, never the model.</p>
  <p><strong>Not legal advice</strong>This is general information from the published record. It does not replace advice on your own case.</p>
</div></footer>
<script src="app.js"></script>
</body>
</html>
"""

# ======================= HOME =======================
H = D["home"]; A = D["answer"]; M = H["meta"]

def fn_html(s):
    q = s["quotes"]
    first = f'<blockquote lang="ms">{E(q[0])}</blockquote>'
    more = ""
    if len(q) > 1:
        more = f'<details><summary>{len(q)-1} more from this source</summary>' + "".join(f'<blockquote lang="ms">{E(x)}</blockquote>' for x in q[1:]) + "</details>"
    dr = f'<div>{DRAFT("Unrevised draft")}</div>' if s["draft"] else ""
    return f"""<li class="fn" id="src-{s['n']}" hidden>
  <div class="fn-head"><span class="fn-n">{s['n']}</span><span>{E(s['cite'])}</span></div>{dr}
  {first}{more}
  <div class="fn-links"><a href="debate.html">{ic("link")}Read in context</a><a href="{E(s['pdf'])}" rel="noopener">{ic("ext")}Official PDF</a></div>
</li>"""

st = {s["name"]: s for s in A["stages"]}
maxms = max(s["ms"] for s in A["stages"]) or 1
labels = {"bm25": "Keyword search (BM25)", "dense": "Meaning search (dense)", "fused": "Fused list", "reranked": "Reranked"}
stage_html = "".join(f'<div class="stage"><div class="v">{n(s["hits"])}<small>hits</small></div><div class="meta">{labels.get(s["name"], s["name"])}<br>{s["ms"]/1000:.1f} s</div><div class="bar"><i style="width:{max(2, s["ms"]/maxms*100):.0f}%"></i></div></div>' for s in A["stages"])
stage_html += f'<div class="stage"><div class="v">${A["usd"]:.4f}</div><div class="meta">Cost of this answer<br>search {A["search_ms"]/1000:.0f} s, total {A["total_ms"]/1000:.0f} s</div></div>'

demo = {"question": A["question"], "answer": A["answer"], "sources_n": len(A["sources"])}
examples = [("EN", "What has the government said about targeted diesel subsidies?"),
            ("EN", "What did the Health Minister promise about hospital equipment?"),
            ("EN", "Which Act sets the rules on employment contracts and what was amended in 2021?"),
            ("BM", "Apakah kenyataan kerajaan mengenai subsidi diesel bersasar?"),
            ("BM", "Apakah komitmen Menteri Kesihatan tentang ambulans?"),
            ("BM", "Bagaimana Akta Kerja 1955 dipinda pada tahun 2021?")]
ex_html = "".join(f'<li><button type="button" class="ex" data-q="{E(q)}"><span class="lang">{l}</span><span lang="{"ms" if l=="BM" else "en"}">{E(q)}</span></button></li>' for l, q in examples)

parties = sorted({r["party"] for r in D["debate"]["speech_rows"]} | {p["party"] for p in D["mp"]["parties"]})
topic_opts = "".join(f'<option>{E(t["name"])}</option>' for t in H["topics"])

def chips(name, opts, checked):
    return '<div class="chips">' + "".join(f'<label class="chip"><input type="radio" name="{name}" value="{v}"{" checked" if v == checked else ""}><span>{l}</span></label>' for v, l in opts) + "</div>"

filters = f"""<details class="filters" id="filters">
 <summary class="linkbtn" style="cursor:pointer">{ic("chev","icon chev")}Filters <span class="meta">(Acts or debates, Parliament, chamber, dates, party, topic, speaker, Act)</span></summary>
 <div class="filter-grid">
  <fieldset class="field"><legend>Search in</legend>{chips("kind", [("", "Both"), ("law", "Acts"), ("debate", "Debates")], "")}</fieldset>
  <fieldset class="field"><legend>Parliament</legend>{chips("parl", [("", "Any"), ("14", "14th"), ("15", "15th")], "")}</fieldset>
  <label class="field"><span>Chamber</span><select name="chamber"><option>Any</option><option>Dewan Rakyat</option><option>Special Chamber (Kamar Khas)</option></select></label>
  <label class="field"><span>Party</span><select name="party"><option>Any</option>{"".join(f"<option>{E(p)}</option>" for p in parties)}</select></label>
  <label class="field"><span>From</span><input type="date" name="from" min="2018-07-16"></label>
  <label class="field"><span>To</span><input type="date" name="to" min="2018-07-16"></label>
  <label class="field"><span>Topic</span><select name="topic"><option>Any</option>{topic_opts}</select></label>
  <label class="field"><span>Speaker</span><input type="text" name="speaker" placeholder="for example Lim Hui Ying"></label>
  <label class="field"><span>Act number</span><input type="text" name="act" inputmode="numeric" placeholder="for example 265"></label>
 </div>
</details>"""

# topic trend small multiples
years = sorted({t["year"] for t in H["topic_trend"]})
names = []
for t in H["topic_trend"]:
    if t["name"] not in names: names.append(t["name"])
ymax = max(t["n"] for t in H["topic_trend"])
def multiple(name):
    pts = {t["year"]: t["n"] for t in H["topic_trend"] if t["name"] == name}
    W, Hh, pl, pr, pt, pb = 320, 90, 4, 4, 10, 18
    x = lambda i: pl + i * (W - pl - pr) / (len(years) - 1)
    y = lambda v: pt + (Hh - pt - pb) * (1 - v / ymax)
    coords = [(x(i), y(pts.get(yr, 0))) for i, yr in enumerate(years)]
    path = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in coords)
    pk = max(range(len(years)), key=lambda i: pts.get(years[i], 0))
    grid = "".join(f'<line class="grid" x1="{pl}" x2="{W-pr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>' for v in (0, ymax / 2, ymax))
    xl = "".join(f'<text x="{x(i):.1f}" y="{Hh-3}" text-anchor="{"start" if i==0 else "end" if i==len(years)-1 else "middle"}">{years[i] if i in (0, 4, 8) else ""}</text>' for i in range(len(years)))
    return f"""<div class="multiple"><h3>{E(name[0].upper()+name[1:])}<span class="num">{n(sum(pts.values()))} items</span></h3>
<svg class="chart" viewBox="0 0 {W} {Hh}" role="img" aria-label="{E(name)} items per year, peak {pts[years[pk]]} in {years[pk]}">{grid}<path class="ink draw" pathLength="1" d="{path}"/><circle class="acc" cx="{coords[pk][0]:.1f}" cy="{coords[pk][1]:.1f}" r="3.6"/><text x="{coords[pk][0]:.1f}" y="{coords[pk][1]-8:.1f}" text-anchor="{'end' if pk>6 else 'middle'}" style="fill:var(--accent);font-weight:700">{n(pts[years[pk]])} in {years[pk]}</text>{xl}</svg></div>"""
mult_html = "".join(multiple(nm) for nm in names)

sit_html = "".join(f'<li><a class="row sit" href="debate.html"><b>{fdate(s["date"], True)} &middot; {"Dewan Rakyat" if s["chamber"]=="DR" else "Special Chamber"}</b><span class="meta">{s["items"]} agenda items{(" &nbsp;" + DRAFT()) if s["draft"] else ""}</span></a></li>' for s in H["latest_sittings"])
com_html = "".join(f'<li><q lang="ms">{E(c["quote"])}</q><div class="gist">{AI("AI")} {E(c["promise"])}</div><div class="by">{E(re.sub(r"\s*\[.*", "", c["speaker"]) if "[" in c["speaker"] else c["speaker"])} &middot; {fdate(c["date"], True)}</div></li>' for c in H["latest_commitments"][:5])
top_html = "".join(f'<li><a href="#">{E(t["name"][0].upper()+t["name"][1:])}</a><span class="dots"></span><span class="n num">{n(t["n"])}</span></li>' for t in H["topics"])

glance = "".join(f'<div class="stat"><span class="big num">{n(v)}</span><span>{l}</span></div>' for v, l in [(M["units"], "agenda items"), (M["speeches"], "speeches"), (M["qa"], "oral questions with answers"), (M["commitments"], "ministers' commitments"), (M["members"], "members of the House")])

home = f"""
<div class="wrap">
<section class="hero" aria-labelledby="h1">
  <div>
    <p class="kicker acc">Ask the record</p>
    <h1 id="h1">What has Parliament <em>actually</em> said?</h1>
    <p class="lede">Ask in English or Bahasa Melayu. Every sentence of the answer cites an Act section or a speech in Hansard, quoted word for word.</p>
    <form class="ask" id="ask" role="search" autocomplete="off">
      <label class="sr" for="q">Your question</label>
      <textarea id="q" name="q" rows="3" maxlength="500" placeholder="Ask about an Act, a debate, a minister or a promise"></textarea>
      <div class="ask-bar">
        <span class="meta">English or Bahasa Melayu &middot; up to 500 characters</span>
        <button class="btn" id="answer-btn" type="submit">{ic("search")}Find the answer</button>
      </div>
      {filters}
    </form>
    <div class="examples">
      <p class="label">Questions to start with</p>
      <ul class="ex-list">{ex_html}</ul>
      <p class="meta" style="margin-top:12px">Prototype: every question plays the same recorded answer, streamed from saved text.</p>
    </div>
  </div>
  <aside class="glance" aria-label="The record at a glance"><p class="label" style="margin-bottom:6px">The record at a glance</p>{glance}<p class="note">14th and 15th Parliaments, July 2018 to October 2026. Updated {fdate(M["built"][:10])}.</p></aside>
</section>

<section class="answer-sec" id="answer" aria-live="polite" hidden>
  <div class="lead">
    <div class="lead-head"><span class="kicker acc">The answer</span>{AI("AI answer")}<span class="meta" id="answer-status"></span></div>
    <h2 class="lead-q" id="lead-q"></h2>
    <div class="lead-body"><div class="prose" id="answer-body"></div></div>
    <aside class="marginalia" aria-label="Sources"><span class="label">Sources, verbatim from the record</span><ol id="margin-list" style="list-style:none">{"".join(fn_html(s) for s in A["sources"])}</ol></aside>
    <details class="how"><summary><span>How it was found, and what it cost</span>{ic("chev","icon chev")}</summary><div class="stages">{stage_html}</div></details>
  </div>
</section>

<section class="section" aria-labelledby="latest">
  <div class="sec-head"><h2 id="latest">The latest from the House</h2><span class="meta">Updated {fdate(M["built"][:10], True)}</span></div>
  <div class="cols3">
    <div><p class="label" style="margin-bottom:8px">Latest sittings</p><ul class="rows">{sit_html}</ul></div>
    <div><p class="label" style="margin-bottom:8px">Latest commitments by ministers</p><ul class="commit-list">{com_html}</ul></div>
    <div><p class="label" style="margin-bottom:8px">Read the record by</p><ul class="rows"><li><a class="row" href="#"><b>Acts</b><span class="meta">principal Acts</span></a></li><li><a class="row" href="#"><b>Questions</b><span class="meta">{n(M["qa"])}</span></a></li><li><a class="row" href="#"><b>Commitments</b><span class="meta">{n(M["commitments"])}</span></a></li><li><a class="row" href="mp.html"><b>Members</b><span class="meta">{M["members"]}</span></a></li><li><a class="row" href="#"><b>Bills</b><span class="meta">with their debates</span></a></li></ul></div>
  </div>
</section>

<section class="section" aria-labelledby="topics">
  <div class="sec-head"><h2 id="topics">Topics, by items in the record</h2><span class="meta">AI-assigned topic tags</span></div>
  <ul class="topic-index">{top_html}</ul>
</section>

<section class="section" aria-labelledby="trend">
  <div class="sec-head"><h2 id="trend">Six leading topics by year</h2><span class="meta">Items per year, one shared scale. 2026 is a partial year.</span></div>
  <div class="multiples">{mult_html}</div>
</section>
</div>
"""
home = home.replace('<script src="app.js">', "")
(OUT / "home.html").write_text(page("Parlimen Search: Ask the record", "Ask", home, desc="Search Malaysia's Acts and Dewan Rakyat debates together.").replace(
    '<script src="app.js"></script>', '<script type="application/json" id="demo-data">' + json.dumps(demo, ensure_ascii=False).replace("</", "<\\/") + '</script>\n<script src="app.js"></script>'), encoding="utf8")

# ======================= MP =======================
P = D["mp"]
act = P["activity_by_month"]
byyear = {}
for a in act: byyear.setdefault(a["month"][:4], {})[int(a["month"][5:])] = a["items"]
amax = max(a["items"] for a in act)
def yr_chart(y):
    mm = byyear.get(y, {})
    W, Hh = 120, 100
    bw = W / 12
    bars = ""
    for m in range(1, 13):
        v = mm.get(m, 0)
        if not v: continue
        h = v / amax * (Hh - 16)
        top = v == amax
        bars += f'<rect class="grow {"acc" if top else ""}" style="animation-delay:{m*40}ms;{"" if top else "fill:var(--ink)"}" x="{(m-1)*bw+1.5:.1f}" y="{Hh-14-h:.1f}" width="{bw-3:.1f}" height="{h:.1f}"><title>{y}-{m:02d}: {v} items</title></rect>'
    if amax in mm.values(): pass
    base = f'<line class="grid" x1="0" x2="{W}" y1="{Hh-14}" y2="{Hh-14}"/>'
    lab = f'<text x="0" y="{Hh-2}">J</text><text x="{W/2-4}" y="{Hh-2}">J</text><text x="{W-8}" y="{Hh-2}">D</text>'
    tot = sum(mm.values())
    return f'<div class="yr"><div class="y">{y}<span class="num">{tot}</span></div><svg class="chart" viewBox="0 0 {W} {Hh}" role="img" aria-label="{y}: {tot} items spoken in {len(mm)} sitting months">{base}{bars}{lab}</svg></div>'
yrs_html = "".join(yr_chart(y) for y in sorted(byyear))
peak = max(act, key=lambda a: a["items"])

pq = next(c for c in P["recent_commitments"] if c["id"] == "DR-2026-10-12-003-c1")
pq_quote = pq["quote"].replace("tahun—", "tahun, ")
cnt = P["counts"]
counts_html = "".join(f'<div><span class="big num">{n(v)}</span><span class="label">{l}</span></div>' for v, l in [(cnt["items_spoken"], "agenda items spoken in"), (cnt["questions_answered"], "questions answered"), (cnt["questions_asked"], "questions asked"), (cnt["commitments"], "commitments made")])

def com_entry(c):
    facts = ""
    fs = []
    if c["deadline"]: fs.append(f'<span>Deadline <b>{E(c["deadline"])}</b></span>')
    if c["amount"].strip() and len(c["amount"].strip())<40: fs.append(f'<span>Amount <b lang="ms">{E(c["amount"].strip()[:90])}</b></span>')
    if fs: facts = '<div class="facts">' + "".join(fs) + "</div>"
    return f"""<article class="entry"><div class="when"><span class="num">{fdate(c["date"])}</span><span>{E(c["office"])}</span><a href="debate.html#{c['id']}">Read the speech {ic("link")}</a></div>
<q lang="ms">{E(c["quote"])}</q><div class="para">{AI("AI")}<span>{E(c["promise"])}</span></div>{facts}</article>"""
com_list = "".join(com_entry(c) for c in P["recent_commitments"])

def qa_entry(q):
    return f"""<article class="entry"><div class="when"><span class="num">{fdate(q["date"])}</span><span>Asked by {E(q["asker"])}</span><a href="debate.html#{q['unit']}">The debate {ic("link")}</a></div>
<div class="qa-pair"><div><div class="who">Question {AI("AI summary")}</div><p>{E(q["question"])}</p></div><div><div class="who">Answer {AI("AI summary")}</div><p>{E(q["answer"])}</p></div></div></article>"""
qa_list = "".join(qa_entry(q) for q in P["recent_answers"])

tmax = P["top_topics"][0]["n"]
tt = "".join(f'<li><span class="t">{E(t["name"][0].upper()+t["name"][1:])}</span><span class="n num">{t["n"]}</span><span class="trk"><i style="width:{t["n"]/tmax*100:.0f}%"></i></span></li>' for t in P["top_topics"])
offices = "".join(f'<li><span>{E(o["office"])}<br><span class="meta">{fdate(o["first"], True)} to {fdate(o["last"], True)}</span></span><span class="num">{o["n"]} commitments</span></li>' for o in P["offices"])
seatrows = "".join(f'<li><span><b>{p["parliament"]}th Parliament</b><br><span class="meta">{E(s["seat"])} ({s["code"]})</span></span><span>{E(p["party"])}</span></li>' for s, p in zip(P["seats"], P["parties"]))
first = P["activity_by_month"][0]["month"]; last = P["activity_by_month"][-1]["month"]

mp = f"""
<div class="wrap">
<section class="profile" aria-labelledby="h1">
  <div>
    <p class="kicker acc">Member profile &middot; Minister of Health</p>
    <h1 id="h1">{E(P["name"])}</h1>
    <p class="sub"><span>Member for <b>Kuala Selangor</b> (P096)</span><span>Party <b>AMANAH</b></span><span>14th and 15th Parliaments</span></p>
  </div>
  <div class="counts">{counts_html}</div>
</section>

<section class="pull" aria-label="A commitment in his own words">
  <div class="src"><b>In the record</b>{fdate(pq["date"])}<br>{E(pq["office"])}<br><a href="debate.html#{pq['id']}">Read the speech</a></div>
  <div><blockquote lang="ms">{E(pq_quote)}</blockquote>
  <p class="gloss">{AI("AI")}<span>{E(pq["promise"])}. Deadline {E(pq["deadline"])}.</span></p></div>
</section>

<section class="section" aria-labelledby="act">
  <div class="sec-head"><h2 id="act">Activity, month by month</h2><span class="meta">Agenda items spoken in. One scale, busiest month {fdate(peak["month"]+"-01").split(" ",1)[1]} ({peak["items"]}).</span></div>
  <div class="yrs">{yrs_html}</div>
</section>

<section class="section">
 <div class="mp-grid">
  <div>
    <div class="sec-head"><h2>Recent commitments</h2><span class="meta">Verbatim quote first, then the AI paraphrase</span></div>
    {com_list}
    <div class="sec-head" style="margin-top:48px"><h2>Recent questions answered</h2><span class="meta">Question and answer are AI summaries</span></div>
    {qa_list}
  </div>
  <aside class="rail" aria-label="About this member">
    <section><div class="sec-head"><h2>Seat and party</h2></div><ul class="kv">{seatrows}</ul></section>
    <section><div class="sec-head"><h2>Offices held</h2></div><ul class="kv">{offices}</ul></section>
    <section><div class="sec-head"><h2>Top topics</h2></div><ul class="hbars">{tt}</ul><p class="meta" style="margin-top:8px">Topic tags are AI-assigned.</p></section>
  </aside>
 </div>
</section>
</div>
"""
(OUT / "mp.html").write_text(page(P["name"] + ": Parlimen Search", "MPs", mp, desc="Member profile"), encoding="utf8")

# ======================= DEBATE =======================
B = D["debate"]; S = B["sitting"]; BL = D["bill"]
def speech_html(r):
    paras = [p for p in re.split(r"\n\s*\n", r["text"].strip())]
    # Hansard hard-wraps lines; rejoin lines within a paragraph
    if len(paras) == 1:
        paras = [r["text"]]
    body = "".join(f"<p>{E(re.sub(chr(10), ' ', p).strip())}</p>" for p in paras)
    nm = re.sub(r"\s*\[.*", "", r["label"])
    short = " short" if len(r["text"]) < 120 else ""
    return f"""<article class="sp{short}" id="seq-{r['seq']}"><div class="who"><a href="mp.html">{E(r["name"])}</a><span>{E(r["label"].split("[")[0].strip()) if r["label"].split("[")[0].strip() != r["name"] else ""}</span><span>{E(r["seat"])}</span> <span class="party">{E(r["party"])}</span><span class="stamp num">{r["time"][:2]}:{r["time"][2:]} &middot; PDF p. {r["page_start"]}</span></div><div class="words" lang="ms">{body}</div></article>"""
speeches = "".join(speech_html(r) for r in B["speech_rows"])

def figs(q):
    try: f = json.loads(q["figures"])
    except Exception: return ""
    return '<div class="figs">' + "".join(f'<div><b>{E(x["value"])}</b>{E(x["meaning"])}</div>' for x in f[:6]) + "</div>"
qcards = "".join(f"""<article class="qcard" id="{q['id']}"><div class="row2">
<div><div class="who">Asked by {E(q["asker"])} {AI("AI summary")}</div><p>{E(q["question"])}</p></div>
<div><div class="who">{E(q["office"])}, {E(re.sub(r'.*\[|\]', '', q["answerer"]))} {AI("AI summary")}</div><p>{E(q["answer"])}</p></div></div>{figs(q)}
<p class="meta" style="margin-top:12px"><a href="#seq-{q['asker_seq']}">Question, speech {q['asker_seq']}</a> &middot; <a href="#seq-{q['answerer_seq']}">Answer, speech {q['answerer_seq']}</a></p></article>""" for q in B["qa"])
ccards = "".join(f"""<article class="entry" id="{c['id']}"><div class="when"><span>{E(re.sub(r'.*\[|\]', '', c["speaker"]))}</span><span>{E(c["office"])}</span><a href="#seq-{c['seq']}">Speech {c['seq']} {ic("link")}</a></div>
<q lang="ms">{E(c["quote"])}</q><div class="para">{AI("AI")}<span>{E(c["promise"])}</span></div>{('<div class="facts"><span>Deadline <b>'+E(c["deadline"])+'</b></span></div>') if c["deadline"] else ''}</article>""" for c in B["commitment_rows"])

# bill timeline grouped by date
days = {}
for t in BL["timeline"]: days.setdefault(t["date"], []).append(t)
def biz(b): return re.sub(r"^RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT\s*", "", b).replace("RANG UNDANG-UNDANG KERJA (PINDAAN) 2021 ", "")
tl = "".join(f'<div class="tl-day"><h3>{fdate(d_)} <span>{len(it)} item{"s" if len(it)>1 else ""}</span></h3>' + "".join(f'<div class="tl-item"><span class="biz">{E(biz(i["business"]))}</span><p><a href="debate.html#{i["id"]}">{E(i["summary_en"])}</a></p></div>' for i in it) + "</div>" for d_, it in days.items())

nb = B["neighbours"]
prev_ = f'<a href="debate.html#{nb[0]["id"]}"><span class="label">Previous item</span><span class="b">{E(nb[0]["business"].title())} &middot; {nb[0]["id"][-3:]}</span></a>'
next_ = f'<a href="debate.html#{nb[1]["id"]}"><span class="label">Next item</span><span class="b">{E(nb[1]["business"].title())} &middot; {nb[1]["id"][-3:]}</span></a>'
tags = "".join(f'<a href="#">{E(t)}</a>' for t in json.loads(B["topics"]))

deb = f"""
<div class="wrap">
<header class="dhead">
  <p class="kicker acc">{chamber(S["chamber"])} &middot; {E(S["meeting"])}</p>
  <h1>{E(B["business"].title())} <span class="meta" style="font-size:.4em;letter-spacing:.1em;white-space:nowrap">Item {B["ord"]}</span></h1>
  <p class="sub"><span><b class="num">{fdate(B["date"])}</b></span><span>{B["speeches"]} speeches, from PDF page {B["page_start"]}</span><span>{E(S["term"])}, {B["parliament"]}th Parliament</span><a href="{E(S["pdf"])}" rel="noopener">{ic("ext")} Official PDF of the sitting</a></p>
  <div class="draftnote">{DRAFT()}<span>This sitting is an unrevised draft. The official text can still change when Hansard publishes the revised edition; the speeches below are shown as published so far.</span></div>
</header>

<div class="dlay">
  <aside class="sum" aria-label="AI summary">
    <div class="box"><div class="top"><span class="label" style="color:var(--ink)">Summary of this item</span>{AI("AI summary")}</div>
    <p>{E(B["summary_en"].split(". ")[0])}.</p>
    <details><summary>Read the whole summary</summary><p>{E(B["summary_en"])}</p></details>
    <details><summary>Ringkasan dalam Bahasa Melayu</summary><p lang="ms">{E(B["summary_ms"])}</p></details>
    <div class="tags">{tags}</div>
    <p class="meta" style="margin-top:12px">Written by AI from the speeches on the left. Check the verbatim text before you quote it.</p></div>
  </aside>

  <div class="tr">
    <div class="sec-head" style="margin-top:0"><h2>The record, verbatim</h2><span class="verbatim-tag">Hansard text &middot; speeches {B["speech_rows"][0]["seq"]} to {B["speech_rows"][-1]["seq"]}</span></div>
    {speeches}
    <div class="sec-head sec-lab"><h2>Questions and answers in this item</h2><span class="meta">Summaries are AI-written</span></div>
    {qcards}
    <div class="sec-head sec-lab"><h2>Commitments made in this item</h2><span class="meta">Quote first, paraphrase second</span></div>
    {ccards}
    <nav class="nextprev" aria-label="Neighbouring items">{prev_}{next_}</nav>
  </div>

  <aside class="bill" aria-labelledby="billh">
    <div class="sec-head" style="margin-top:0"><h2 id="billh">This bill in Parliament</h2></div>
    <p style="font-weight:600;line-height:1.25">{E(BL["title"].title())} Bill</p>
    <p class="meta" style="margin:4px 0 12px">Amends {E(BL["act_title_bi"].title())} (Act {BL["act"]}). {len(BL["timeline"])} debates on {len(days)} dates. Summaries are AI-written {AI("AI")}</p>
    <div class="timeline" tabindex="0" role="region" aria-label="Bill timeline, scrollable">{tl}</div>
    <p class="tl-note">An example of a bill's path; this item is not part of it.</p>
  </aside>
</div>
</div>
"""
(OUT / "debate.html").write_text(page("Oral questions, 22 Oct 2026: Parlimen Search", "Sittings", deb, desc="A debate item with its verbatim record."), encoding="utf8")
print("ok")
