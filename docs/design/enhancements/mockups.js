/* Tanya Dewan upgrade mockups. Data: data.json beside this file (built by mockup_data.py). */
(() => {
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => Number(n).toLocaleString("en-GB");
const icon = (n, cls = "i") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const safeUrl = u => (typeof u === "string" && u.startsWith("https://")) ? u : null;
const typing = e => { const t = e.target; return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)); };

/* Small markdown: paragraphs, "- " bullets, **bold**, [n] citations. */
function md(text, live = false) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(\d+)\]/g, (_, n) => `<button type="button" class="cite" data-n="${n}" aria-label="Source ${n}">${n}</button>`);
  const out = []; let list = null;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) { if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } continue; }
    if (/^[-*] /.test(line)) { (list ||= []).push(`<li>${inline(line.slice(2))}</li>`); continue; }
    if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
    out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push(`<ul>${list.join("")}</ul>`);
  let html = out.join("");
  if (live) html = html.replace(/(<\/(?:p|li)>)(<\/ul>)?$/, '<span class="caret" aria-hidden="true"></span>$1$2');
  return html;
}

fetch("data.json").then(r => r.json()).then(D => {
  const parts = [["ws", watchItSearch], ["cr", citationReader], ["cp", palette], ["sm", seatMap], ["dt", debateTimeline], ["te", topicExplorer], ["hb", howBuilt]];
  for (const [id, fn] of parts) { try { fn($("#" + id), D); } catch (e) { $("#" + id).textContent = "This mockup failed to load: " + e.message; console.error(e); } }
}).catch(e => { $$(".frame-body").forEach(b => b.textContent = "The data file did not load: " + e.message); });

/* ---------------- 1. Watch it search ---------------- */
function watchItSearch(root, D) {
  const ev = D.answer.events, done = ev.find(e => e.event === "done").data;
  const total = Number(D.meta.speeches) + Number(D.meta.sections);
  const steps = [
    { key: "all", nm: "Everything searched", sub: "speeches and Act sections", n: total },
    { key: "bm25", nm: "Keyword match", sub: "BM25 on SQLite FTS5" },
    { key: "dense", nm: "Meaning match", sub: "Qwen3 embeddings" },
    { key: "fused", nm: "Merged", sub: "reciprocal rank fusion" },
    { key: "reranked", nm: "Reranked", sub: "Claude Haiku reads the top passages" },
    { key: "cited", nm: "Cited in the answer", sub: "every sentence needs one", n: done.sources.length },
  ];
  const final = Object.fromEntries(done.stages.map(s => [s.name, s]));
  const w = n => Math.max(1.5, 100 * Math.log10(Math.max(n, 1)) / Math.log10(total));
  root.innerHTML = `
    <div class="ws-q"><q>${esc(done.question)}</q>
      <div class="seg" role="group" aria-label="Playback speed"><button type="button" data-sp="1" aria-pressed="true">Real speed</button><button type="button" data-sp="4" aria-pressed="false">4 times faster</button></div>
      <button class="btn" type="button" id="ws-play">${icon("play")}Play the search</button></div>
    <div class="ws-grid">
      <div>
        <div class="card funnel"><h3>How the search narrowed <span id="ws-clock" class="tnum"></span></h3>
          ${steps.map(s => `<div class="fstep ${s.key === "cited" ? "cited" : ""}" data-k="${s.key}">
            <span class="nm"><span class="spin" aria-hidden="true"></span>${esc(s.nm)} <small>${esc(s.sub)}</small></span>
            <span class="v tnum"><span class="n"></span><small class="ms"></small></span>
            <span class="bar"><i></i></span></div>`).join("")}
        </div>
        <div class="toolbar" style="margin-top:14px"><button class="btn ghost" type="button" id="ws-stream-btn" aria-pressed="false" aria-controls="ws-stream">Show the stream from the server</button>
          <span class="hint">The real events, as the browser receives them.</span></div>
        <div class="stream" id="ws-stream" hidden aria-live="off"></div>
      </div>
      <div>
        <div class="card ws-answer"><div class="head"><span class="label-ai">${icon("spark")}AI answer</span><span id="ws-state"></span></div>
          <div class="answer-text" id="ws-text" lang="en"></div></div>
        <div style="margin-top:16px"><div class="ws-new" id="ws-new">${icon("warn")}New: the sources show here before the answer text.</div>
          <div class="ws-src" id="ws-src"></div></div>
      </div>
    </div>`;
  const rows = Object.fromEntries($$(".fstep", root).map(r => [r.dataset.k, r]));
  const setRow = (k, state, n, ms) => {
    const r = rows[k]; r.classList.toggle("on", state !== "off"); r.classList.toggle("done", state === "done");
    $(".n", r).textContent = n != null ? fmt(n) : (state === "on" ? "…" : "");
    $(".ms", r).textContent = ms != null ? (ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : ms + " ms") : "";
    $(".bar i", r).style.width = n != null ? w(n) + "%" : "0";
  };
  const text = $("#ws-text", root), state = $("#ws-state", root), src = $("#ws-src", root), clock = $("#ws-clock", root), stream = $("#ws-stream", root);
  const showSources = () => {
    src.innerHTML = done.sources.map(s => `<div class="card s" data-n="${s.n}"><span class="num">${s.n}</span><div><b>${esc(s.title)}</b><span>${esc(s.meta)}</span></div></div>`).join("");
  };
  const ghostSources = () => { src.innerHTML = `<div class="ghost-card">The sources arrive when ranking ends.</div>`; };
  const finalState = () => {
    setRow("all", "done", total);
    for (const k of ["bm25", "dense", "fused", "reranked"]) setRow(k, "done", final[k].hits, final[k].ms);
    setRow("cited", "done", done.sources.length);
    text.innerHTML = md(done.answer); showSources();
    state.textContent = `Done in ${(done.total_ms / 1000).toFixed(1)} s`;
    clock.textContent = "";
  };
  src.addEventListener("click", () => {});
  text.addEventListener("click", e => { const b = e.target.closest(".cite"); if (!b) return;
    $$(".s", src).forEach(c => c.classList.toggle("lit", c.dataset.n === b.dataset.n)); $$(".cite", text).forEach(c => c.classList.toggle("lit", c === b)); });

  let speed = 1, timers = [], raf = 0;
  const stop = () => { timers.forEach(clearTimeout); timers = []; cancelAnimationFrame(raf); };
  const logRow = (t, name, data, isNew) => {
    if (stream.querySelector(".empty")) stream.innerHTML = "";
    let json = JSON.stringify(data); if (json.length > 150) json = json.slice(0, 150) + "…";
    const r = document.createElement("div"); r.className = "row" + (isNew ? " new" : "");
    r.innerHTML = `<span class="t">${(t / 1000).toFixed(2)}s</span><span class="e">${esc(name)}${isNew ? " (new)" : ""}</span><span class="d">${esc(json)}</span>`;
    stream.appendChild(r); stream.scrollTop = stream.scrollHeight;
  };
  const fillLog = () => { stream.innerHTML = ""; let srcT = null;
    for (const e of ev) { logRow(e.t, e.event, e.data); if (e.event === "stage" && e.data.name === "reranked" && e.data.hits != null) { srcT = e.t; logRow(e.t, "sources", { n: done.sources.length, first: done.sources[0].title }, true); } } };
  function play() {
    stop(); for (const k of Object.keys(rows)) setRow(k, "off");
    text.innerHTML = `<p class="ws-wait">Searching…</p>`; ghostSources(); state.textContent = "Working"; stream.innerHTML = `<div class="empty">Waiting for the first event…</div>`;
    setRow("all", "done", total);
    const t0 = performance.now(); let shown = 0, target = "";
    const tick = () => { const el = (performance.now() - t0) * speed; clock.textContent = (el / 1000).toFixed(1) + " s";
      if (shown < target.length) { shown = Math.min(target.length, shown + Math.max(2, Math.round(3 * speed))); text.innerHTML = md(target.slice(0, shown), true); }
      raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    for (const e of ev) timers.push(setTimeout(() => {
      logRow(e.t, e.event, e.data);
      if (e.event === "stage") {
        const k = e.data.name;
        if (k === "answer") { text.innerHTML = `<p class="ws-wait">Writing the answer…</p>`; state.textContent = "Writing"; return; }
        if (e.data.hits == null) setRow(k, "on"); else setRow(k, "done", e.data.hits, e.data.ms);
        if (k === "reranked" && e.data.hits != null) { logRow(e.t, "sources", { n: done.sources.length, first: done.sources[0].title }, true); showSources(); }
      } else if (e.event === "text") { target = e.data.text; }
      else if (e.event === "done") { target = done.answer;
        timers.push(setTimeout(() => { stop(); finalState(); }, 900 / speed)); }
    }, e.t / speed));
  }
  $$(".seg button", root).forEach(b => b.addEventListener("click", () => { speed = +b.dataset.sp; $$(".seg button", root).forEach(x => x.setAttribute("aria-pressed", String(x === b))); }));
  $("#ws-play", root).addEventListener("click", play);
  const sb = $("#ws-stream-btn", root);
  sb.addEventListener("click", () => { const on = sb.getAttribute("aria-pressed") !== "true"; sb.setAttribute("aria-pressed", String(on)); stream.hidden = !on;
    sb.textContent = on ? "Hide the stream" : "Show the stream from the server"; if (on && !stream.children.length) fillLog(); });
  finalState(); fillLog();
}

/* ---------------- 2. Citation reader ---------------- */
function citationReader(root, D) {
  const done = D.answer.events.find(e => e.event === "done").data;
  const norm = s => s.replace(/\s+/g, " ").trim();
  const passageFor = s => done.passages.find(p => p.cite === s.cite) || done.passages.find(p => p.url === s.url);
  root.innerHTML = `<div class="cr" id="cr-grid">
      <div class="card ans"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px"><span class="label-ai">${icon("spark")}AI answer</span><span class="hint">Press a number to read its source.</span></div>
        <div class="answer-text" id="cr-text" lang="en">${md(done.answer)}</div></div>
      <aside class="card reader" id="cr-reader" role="dialog" aria-labelledby="cr-title" hidden>
        <div class="rh"><span class="num" id="cr-num"></span><div><h3 id="cr-title" tabindex="-1"></h3><p id="cr-meta"></p></div>
          <button class="x" type="button" id="cr-close" aria-label="Close the reader">${icon("x")}</button></div>
        <div class="rb"><p class="hint" style="margin-bottom:8px">The words the answer quotes are marked.</p><blockquote class="rec" id="cr-body" lang="en"></blockquote></div>
        <div class="rf"><div class="nav"><button class="btn ghost" type="button" id="cr-prev">${icon("up")}Previous</button><button class="btn ghost" type="button" id="cr-next">Next${icon("down")}</button></div>
          <a id="cr-pdf" target="_blank" rel="noopener">Official PDF ${icon("ext")}</a></div>
      </aside></div>`;
  const grid = $("#cr-grid", root), reader = $("#cr-reader", root), txt = $("#cr-text", root);
  let cur = 0, opener = null;
  function marked(raw, quotes) {
    const ranges = [];
    for (const q of quotes) {
      const words = norm(q).split(" ").map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      const m = new RegExp(words.join("\\s+")).exec(raw); if (m) ranges.push([m.index, m.index + m[0].length]);
    }
    ranges.sort((a, b) => a[0] - b[0]);
    let out = "", at = 0;
    for (const [a, b] of ranges) { if (a < at) continue; out += esc(raw.slice(at, a)) + "<mark>" + esc(raw.slice(a, b)) + "</mark>"; at = b; }
    return out + esc(raw.slice(at));
  }
  function open(n, focus = true) {
    const s = done.sources.find(x => x.n === n); if (!s) return; cur = n;
    const p = passageFor(s); const raw = p ? p.text : s.quotes.join("\n\n");
    $("#cr-num", root).textContent = n; $("#cr-title", root).textContent = s.title; $("#cr-meta", root).textContent = s.meta + " · " + s.cite;
    $("#cr-body", root).innerHTML = marked(raw, s.quotes);
    const pdf = safeUrl(s.pdf), a = $("#cr-pdf", root); if (pdf) { a.href = pdf; a.hidden = false; } else a.hidden = true;
    reader.hidden = false; grid.classList.add("open");
    $$(".cite", txt).forEach(c => c.classList.toggle("lit", +c.dataset.n === n));
    $("#cr-prev", root).disabled = n <= 1; $("#cr-next", root).disabled = n >= done.sources.length;
    const m = $("mark", reader); if (m) m.scrollIntoView({ block: "nearest" });
    if (focus) $("#cr-title", root).focus({ preventScroll: true });
  }
  function close() { reader.hidden = true; grid.classList.remove("open"); $$(".cite", txt).forEach(c => c.classList.remove("lit")); if (opener) opener.focus(); }
  txt.addEventListener("click", e => { const b = e.target.closest(".cite"); if (!b) return; opener = b; open(+b.dataset.n); });
  $("#cr-close", root).addEventListener("click", close);
  $("#cr-prev", root).addEventListener("click", () => open(cur - 1));
  $("#cr-next", root).addEventListener("click", () => open(cur + 1));
  document.addEventListener("keydown", e => {
    if (reader.hidden || typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "j" || e.key === "J") { if (cur < done.sources.length) open(cur + 1); e.preventDefault(); }
    else if (e.key === "k" || e.key === "K") { if (cur > 1) open(cur - 1); e.preventDefault(); }
    else if (e.key === "Escape" && $("#keys").hidden) { close(); }
  });
}

/* ---------------- 3. Jump to anything ---------------- */
function palette(root, D) {
  const KINDS = [["MP", "user", "MPs"], ["Act", "book", "Acts"], ["Bill", "doc", "Bills"], ["Topic", "tag", "Topics"], ["Sitting", "cal", "Sittings"]];
  const ICON = Object.fromEntries(KINDS.map(([k, ic]) => [k, ic]));
  const items = D.index.map((x, i) => ({ ...x, i, low: x.t.toLowerCase() }));
  const START = ["Dzulkefly", "Employment Act 1955", "Keselamatan Dalam Talian", "budget and spending"];
  root.innerHTML = `<div class="cp-stage">
      <div class="cp-fake"><button type="button" class="cp-open" id="cp-open">${icon("search")}<span>Jump to an MP, Act, bill…</span><kbd>Ctrl K</kbd></button>
        <span class="hint">Or press <kbd>Ctrl</kbd> <kbd>K</kbd> anywhere on this page.</span></div>
      <p class="cp-said" id="cp-said" aria-live="polite"></p>
      <div class="card cp" id="cp" hidden>
        <div class="in">${icon("search")}<label class="sr-only" for="cp-in">Jump to</label>
          <input id="cp-in" type="text" role="combobox" aria-expanded="true" aria-controls="cp-list" aria-autocomplete="list" autocomplete="off" placeholder="Type a name, an Act, a topic or a date"></div>
        <ul id="cp-list" role="listbox" aria-label="Matches"></ul>
        <div class="ft"><span><kbd>↑</kbd> <kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span><span><kbd>Esc</kbd> to close</span><span id="cp-count"></span></div>
      </div></div>`;
  const box = $("#cp", root), input = $("#cp-in", root), list = $("#cp-list", root), said = $("#cp-said", root);
  let shown = [], sel = 0, opener = null;
  function score(it, q) {
    const i = it.low.indexOf(q);
    if (i >= 0) { const word = i === 0 || /[\s(-]/.test(it.low[i - 1]); return { s: 1000 - i * 2 + (word ? 300 : 0) - it.low.length * .5, hits: [...Array(q.length)].map((_, k) => i + k) }; }
    const hits = []; let at = 0;
    for (const ch of q) { if (ch === " ") continue; const j = it.low.indexOf(ch, at); if (j < 0) return null; hits.push(j); at = j + 1; }
    const spread = hits[hits.length - 1] - hits[0];
    return spread > q.length * 4 ? null : { s: 400 - spread * 6 - it.low.length * .5, hits };
  }
  const hl = (t, hits) => { const set = new Set(hits); return [...t].map((c, k) => set.has(k) ? `<b>${esc(c)}</b>` : esc(c)).join(""); };
  function render() {
    const q = input.value.trim().toLowerCase(); let res;
    if (!q) res = START.map(s => items.find(it => it.low.includes(s.toLowerCase()))).filter(Boolean).map(it => ({ it, hits: [] }));
    else res = items.map(it => { const r = score(it, q); return r && { it, ...r }; }).filter(Boolean).sort((a, b) => b.s - a.s);
    const groups = q ? KINDS.map(([k, ic, label]) => ({ k, ic, label, rows: res.filter(r => r.it.k === k).slice(0, 5) })).filter(g => g.rows.length)
      : [{ label: "Try", rows: res }];
    shown = groups.flatMap(g => g.rows); sel = Math.min(sel, Math.max(0, shown.length - 1));
    $("#cp-count", root).textContent = q ? `${fmt(res.length)} matches` : "Suggestions";
    if (!shown.length) { list.innerHTML = `<li class="none" role="presentation">Nothing matches “${esc(input.value)}”.</li>`; input.removeAttribute("aria-activedescendant"); return; }
    let n = 0;
    list.innerHTML = groups.map(g => `<li class="g" role="presentation">${g.label}</li>` + g.rows.map(r => {
      const id = "cp-o" + n; const h = `<li role="option" id="${id}" data-i="${n}" aria-selected="${n === sel}"><span class="k">${icon(ICON[r.it.k])}</span><span class="t">${hl(r.it.t, r.hits)}</span><span class="s">${esc(r.it.s)}</span></li>`; n++; return h; }).join("")).join("");
    input.setAttribute("aria-activedescendant", "cp-o" + sel);
  }
  function move(d) { if (!shown.length) return; sel = (sel + d + shown.length) % shown.length;
    $$("[role=option]", list).forEach(o => o.setAttribute("aria-selected", String(+o.dataset.i === sel)));
    input.setAttribute("aria-activedescendant", "cp-o" + sel); $("#cp-o" + sel, list)?.scrollIntoView({ block: "nearest" }); }
  function choose(i) { const it = shown[i]?.it; if (!it) return;
    const what = { MP: "the MP page for", Act: "the Act page for", Bill: "the bill page for", Topic: "the topic page for", Sitting: "the sitting of" }[it.k];
    said.textContent = `On the real site this opens ${what} ${it.t}.`; hide(); }
  function show() { opener = document.activeElement; box.hidden = false; input.value = ""; sel = 0; render(); input.focus(); }
  function hide() { box.hidden = true; if (opener && opener !== document.body) opener.focus(); }
  $("#cp-open", root).addEventListener("click", show);
  box.hidden = false; render();
  input.addEventListener("input", () => { sel = 0; render(); });
  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { move(1); e.preventDefault(); } else if (e.key === "ArrowUp") { move(-1); e.preventDefault(); }
    else if (e.key === "Enter") { choose(sel); e.preventDefault(); } else if (e.key === "Escape") { hide(); e.stopPropagation(); } });
  list.addEventListener("pointerdown", e => { const o = e.target.closest("[role=option]"); if (o) { e.preventDefault(); choose(+o.dataset.i); } });
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); root.closest(".frame").scrollIntoView({ block: "center", behavior: "smooth" }); show(); } });
  document.addEventListener("pointerdown", e => { if (!box.hidden && !box.contains(e.target) && !e.target.closest("#cp-open")) hide(); });
}

/* ---------------- 4. Seat map ---------------- */
const BLOCS = [["PH", "Pakatan Harapan", "--c-ph"], ["BN", "Barisan Nasional", "--c-bn"], ["GPS", "Gabungan Parti Sarawak", "--c-gps"], ["GRS", "Gabungan Rakyat Sabah", "--c-grs"], ["Other", "Other parties and independents", "--c-other"], ["PN", "Perikatan Nasional", "--c-pn"]];
const blocColor = b => `var(${(BLOCS.find(x => x[0] === b) || ["", "", "--c-chair"])[2]})`;
function seatMap(root, D) {
  const order = Object.fromEntries(BLOCS.map((b, i) => [b[0], i]));
  const seats = [...D.seats].sort((a, b) => order[a.bloc] - order[b.bloc] || a.party.localeCompare(b.party) || a.code.localeCompare(b.code));
  const N = seats.length, ROWS = 8, R = 470, R0 = 0.38, cx = 500, cy = 500;
  const radii = [...Array(ROWS)].map((_, i) => R * (R0 + (1 - R0) * i / (ROWS - 1)));
  const sum = radii.reduce((a, b) => a + b, 0);
  const counts = radii.map(r => Math.round(N * r / sum)); counts[ROWS - 1] += N - counts.reduce((a, b) => a + b, 0);
  const pos = [];
  radii.forEach((r, i) => { const n = counts[i]; for (let k = 0; k < n; k++) { const a = Math.PI - Math.PI * k / (n - 1); pos.push({ a, r, x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) }); } });
  pos.sort((p, q) => q.a - p.a || p.r - q.r);
  const dot = Math.min(13.5, (radii[1] - radii[0]) * 0.42);
  const spoke = new Set(D.debate.speeches.map(s => s.member).filter(Boolean));
  const mp = D.mp.slug;
  root.innerHTML = `<div class="sm">
      <div class="toolbar" style="justify-content:center"><div class="seg" role="group" aria-label="What to light up">
        <button type="button" data-m="all" aria-pressed="true">Whole house</button>
        <button type="button" data-m="mp" aria-pressed="false">One MP</button>
        <button type="button" data-m="spoke" aria-pressed="false">Who spoke on the Online Safety Bill</button></div></div>
      <div class="sm-wrap"><svg viewBox="0 0 1000 515" role="img" aria-labelledby="sm-cap"><title id="sm-cap">Seats of the 15th Parliament by coalition</title>
        ${seats.map((s, i) => `<circle cx="${pos[i].x.toFixed(1)}" cy="${pos[i].y.toFixed(1)}" r="${dot.toFixed(1)}" fill="${blocColor(s.bloc)}" data-i="${i}"/>`).join("")}</svg>
        <div class="sm-mid"><b id="sm-big" class="tnum">222</b><span id="sm-small">seats in the Dewan Rakyat</span></div>
        <div class="sm-tip" id="sm-tip" hidden></div></div>
      <p class="sm-said" id="sm-said" aria-live="polite"></p>
      <div class="legend">${BLOCS.map(([k, name]) => `<span><i style="--sw:${blocColor(k)}"></i>${esc(name)} <b class="tnum">${seats.filter(s => s.bloc === k).length}</b></span>`).join("")}</div>
      <div class="sm-find" style="justify-content:center"><label for="sm-in" class="hint">Find an MP or seat</label><input id="sm-in" type="search" placeholder="For example Langkawi or Anwar"></div>
      <p class="sm-note">A diagram: seats are grouped by coalition, not placed as in the real chamber. Parties are as the site's records hold them for the 15th Parliament.</p></div>`;
  const circles = $$("circle", root), tip = $("#sm-tip", root), wrap = $(".sm-wrap", root);
  const big = $("#sm-big", root), small = $("#sm-small", root), said = $("#sm-said", root);
  const light = test => circles.forEach((c, i) => { const on = test ? test(seats[i]) : true; c.classList.toggle("dim", !on); c.classList.toggle("hot", !!test && on); });
  function mode(m) {
    $$(".seg button", root).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.m === m))); $("#sm-in", root).value = "";
    if (m === "all") { light(null); circles.forEach(c => c.classList.remove("hot")); big.textContent = "222"; small.textContent = "seats in the Dewan Rakyat"; said.textContent = ""; }
    if (m === "mp") { const s = seats.find(x => x.member === mp); light(x => x.member === mp); big.textContent = s.code; small.textContent = s.seat;
      said.textContent = `${s.name}, ${s.party} (${s.bloc})`; }
    if (m === "spoke") { const n = seats.filter(x => spoke.has(x.member)).length; light(x => spoke.has(x.member)); big.textContent = n; small.textContent = "MPs spoke in this debate";
      said.textContent = `Online Safety Bill 2024, second and third reading, 11 December 2024`; }
  }
  $$(".seg button", root).forEach(b => b.addEventListener("click", () => mode(b.dataset.m)));
  $("#sm-in", root).addEventListener("input", e => { const q = e.target.value.trim().toLowerCase(); if (!q) return mode("all");
    $$(".seg button", root).forEach(b => b.setAttribute("aria-pressed", "false"));
    const hit = x => x.name.toLowerCase().includes(q) || x.seat.toLowerCase().includes(q) || x.code.toLowerCase() === q;
    const n = seats.filter(hit).length; light(hit); big.textContent = n; small.textContent = n === 1 ? "match" : "matches";
    said.textContent = n === 1 ? (s => `${s.code} ${s.seat}: ${s.name}, ${s.party}`)(seats.find(hit)) : ""; });
  wrap.addEventListener("pointermove", e => { const c = e.target.closest("circle"); if (!c) { tip.hidden = true; return; }
    const s = seats[+c.dataset.i], b = wrap.getBoundingClientRect();
    tip.innerHTML = `<b>${esc(s.name)}</b><br>${esc(s.code)} ${esc(s.seat)}<br>${esc(s.party)} · ${esc((BLOCS.find(x => x[0] === s.bloc) || [])[1] || s.bloc)}`;
    tip.hidden = false; const x = e.clientX - b.left, y = e.clientY - b.top;
    tip.style.left = Math.min(x + 14, b.width - tip.offsetWidth - 4) + "px"; tip.style.top = Math.max(0, y - tip.offsetHeight - 12) + "px"; });
  wrap.addEventListener("pointerleave", () => tip.hidden = true);
  mode("mp");
}

/* ---------------- 5. Debate timeline ---------------- */
function debateTimeline(root, D) {
  const sp = D.debate.speeches, total = sp.reduce((a, s) => a + s.chars, 0);
  let acc = 0; sp.forEach(s => { s.x = acc / total; s.w = s.chars / total; acc += s.chars; });
  const lanes = [...new Set(sp.map(s => s.bloc))].sort((a, b) => (a === "Chair") - (b === "Chair") || a.localeCompare(b));
  const laneName = { PH: "PH", PN: "PN", BN: "BN", GPS: "GPS", GRS: "GRS", Other: "Other", Chair: "Chair" };
  const hhmm = t => t && t.length === 4 ? t.slice(0, 2) + ":" + t.slice(2) : "";
  const timed = sp.filter(s => s.time);
  const ticks = timed.length ? [{ pos: "left:0", l: hhmm(timed[0].time) }, { pos: "right:0", l: hhmm(timed[timed.length - 1].time) }] : [];
  const by = b => sp.filter(s => s.bloc === b).length;
  const longest = sp.reduce((a, s) => s.chars > a.chars ? s : a, sp[0]);
  root.innerHTML = `<div class="dt-h"><h3>Online Safety Bill 2024: second and third reading</h3>
      <p>Dewan Rakyat, Wednesday 11 December 2024 · ${sp.length} turns · ${hhmm(sp[0].time)} to ${hhmm(sp[sp.length - 1].time)}</p></div>
    <div class="lanes" role="group" aria-label="Speeches in order. Use the arrow keys to move.">
      ${lanes.map(l => `<div class="lane"><span>${esc(laneName[l] || l)}</span><div class="track">${sp.map((s, i) => s.bloc !== l ? "" :
        `<button type="button" data-i="${i}" tabindex="-1" style="left:${(s.x * 100).toFixed(3)}%;width:${(s.w * 100).toFixed(3)}%;--sw:${blocColor(s.bloc)}" aria-label="${esc((s.name || s.role) + ", " + hhmm(s.time))}"></button>`).join("")}</div></div>`).join("")}
      <div class="axis"><span></span><div>${ticks.map(t => `<span style="${t.pos}">${t.l}</span>`).join("")}</div></div>
    </div>
    <p class="hint" style="margin-top:6px">Each bar is one speech. Its width shows how long the speech is.</p>
    <div class="dt-stats"><span><b>${by("PH")}</b> turns by PH members</span><span><b>${by("PN")}</b> by PN members</span><span><b>${by("Chair")}</b> by the Chair</span>
      <span>Longest: <b>${esc(longest.name || longest.role)}</b>, ${fmt(longest.chars)} characters</span></div>
    <article class="card dt-card" aria-live="polite"><div class="who"><b id="dt-name"></b><span id="dt-seat" class="hint"></span><span class="pt" id="dt-party"></span><span class="m tnum" id="dt-meta"></span></div>
      <span class="hint">Hansard, word for word (the record is in Malay)</span><blockquote class="rec" id="dt-text" lang="ms"></blockquote></article>`;
  const btns = $$(".track button", root); let cur = -1;
  function pick(i, focus) { cur = Math.max(0, Math.min(sp.length - 1, i)); const s = sp[cur];
    btns.forEach(b => { const on = +b.dataset.i === cur; b.classList.toggle("cur", on); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    $("#dt-name", root).textContent = s.name || s.role; $("#dt-seat", root).textContent = s.seat ? s.seat : (s.name ? s.role : "");
    const p = $("#dt-party", root); p.textContent = s.party; p.hidden = !s.party;
    $("#dt-meta", root).textContent = `Turn ${cur + 1} of ${sp.length} · ${hhmm(s.time)} · page ${s.page}`;
    $("#dt-text", root).textContent = s.text + (s.chars > s.text.length ? " …" : ""); }
  btns.forEach(b => b.addEventListener("click", () => pick(+b.dataset.i, true)));
  $(".lanes", root).addEventListener("keydown", e => {
    if (e.key === "ArrowRight") { pick(cur + 1, true); e.preventDefault(); } else if (e.key === "ArrowLeft") { pick(cur - 1, true); e.preventDefault(); }
    else if (e.key === "Home") { pick(0, true); e.preventDefault(); } else if (e.key === "End") { pick(sp.length - 1, true); e.preventDefault(); } });
  pick(sp.indexOf(longest), false);
}

/* ---------------- 6. Topic explorer ---------------- */
function topicExplorer(root, D) {
  const months = []; for (let y = 2018, m = 7; y < 2026 || (y === 2026 && m <= 10); m++) { if (m > 12) { m = 1; y++; } months.push(`${y}-${String(m).padStart(2, "0")}`); }
  const ser = D.topics.map((t, i) => { const map = Object.fromEntries(t.points); return { name: t.name, color: `var(--t${i + 1})`, on: true, v: months.map(m => map[m] || 0) }; });
  const EVENTS = [["2020-03", "First lockdown (MCO)"], ["2022-11", "GE15"]];
  const W = 1000, H = 340, L = 44, Rm = 16, T = 26, B = 30;
  let lo = 0, hi = months.length - 1;
  root.innerHTML = `<div class="toolbar" style="justify-content:space-between"><div class="te-legend" role="group" aria-label="Topics to show">
      ${ser.map((s, i) => `<button type="button" data-i="${i}" aria-pressed="true" style="--sw:${s.color}"><i></i>${esc(s.name[0].toUpperCase() + s.name.slice(1))}</button>`).join("")}</div>
      <button class="btn ghost" type="button" id="te-reset" hidden>Show all years</button></div>
    <div class="te-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Debates per month for six topics, July 2018 to October 2026"></svg><div class="te-tip" id="te-tip" hidden></div></div>
    <p class="hint">Point at the chart to read a month. Drag across it to zoom in. Click a month to open its debates.</p>
    <p class="te-said" id="te-said" aria-live="polite"></p>`;
  const svg = $("svg", root), tip = $("#te-tip", root), chart = $(".te-chart", root);
  const xs = i => L + (W - L - Rm) * (i - lo) / Math.max(1, hi - lo);
  const label = m => { const [y, mo] = m.split("-"); return `${MONTHS_LONG[+mo - 1]} ${y}`; };
  let ymax = 1;
  function draw(extra = "") {
    const vis = ser.filter(s => s.on);
    ymax = Math.max(10, ...vis.flatMap(s => s.v.slice(lo, hi + 1)));
    const step = ymax > 400 ? 100 : ymax > 200 ? 50 : ymax > 80 ? 20 : 10; ymax = Math.ceil(ymax / step) * step;
    const ys = v => H - B - (H - B - T) * v / ymax;
    let g = `<g class="grid">`; for (let v = 0; v <= ymax; v += step) g += `<line x1="${L}" x2="${W - Rm}" y1="${ys(v)}" y2="${ys(v)}"/><text x="${L - 6}" y="${ys(v) + 4}" text-anchor="end">${v}</text>`; g += `</g>`;
    const span = hi - lo, every = span > 60 ? 12 : span > 24 ? 6 : span > 10 ? 3 : 1;
    let xa = ""; for (let i = lo; i <= hi; i++) { const [y, mo] = months[i].split("-"); if ((+mo - 1) % every === 0) xa += `<text x="${xs(i)}" y="${H - 10}" text-anchor="middle">${every >= 12 ? y : MONTHS[+mo - 1] + (mo === "01" || every < 12 && i === lo ? " " + y.slice(2) : "")}</text>`; }
    let evs = ""; for (const [m, t] of EVENTS) { const i = months.indexOf(m); if (i >= lo && i <= hi) evs += `<g class="ev"><line x1="${xs(i)}" x2="${xs(i)}" y1="${T - 6}" y2="${H - B}"/><text x="${xs(i) + 5}" y="${T + 4}">${esc(t)}</text></g>`; }
    const lines = vis.map(s => `<path class="ser" stroke="${s.color}" d="${s.v.slice(lo, hi + 1).map((v, k) => (k ? "L" : "M") + xs(lo + k).toFixed(1) + " " + ys(v).toFixed(1)).join("")}"/>`).join("");
    svg.innerHTML = g + evs + lines + `<g class="xa">${xa}</g>` + extra;
    $("#te-reset", root).hidden = lo === 0 && hi === months.length - 1;
  }
  const idxAt = e => { const b = svg.getBoundingClientRect(); const x = (e.clientX - b.left) * W / b.width; return Math.round(lo + (x - L) / (W - L - Rm) * (hi - lo)); };
  let drag = null;
  svg.addEventListener("pointerdown", e => { drag = { a: idxAt(e), b: idxAt(e) }; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", e => {
    const i = Math.max(lo, Math.min(hi, idxAt(e)));
    if (drag) { drag.b = i; const [a, b] = [Math.min(drag.a, drag.b), Math.max(drag.a, drag.b)];
      draw(`<rect class="brush" x="${xs(a)}" y="${T}" width="${Math.max(1, xs(b) - xs(a))}" height="${H - B - T}"/>`); tip.hidden = true; return; }
    draw(`<line class="cross" x1="${xs(i)}" x2="${xs(i)}" y1="${T}" y2="${H - B}"/>`);
    const vis = ser.filter(s => s.on).map(s => ({ s, v: s.v[i] })).sort((a, b) => b.v - a.v);
    tip.innerHTML = `<b>${label(months[i])}</b>` + vis.map(({ s, v }) => `<div><span><i style="--sw:${s.color}"></i>${esc(s.name)}</span><span class="tnum">${v}</span></div>`).join("");
    tip.hidden = false; const cb = chart.getBoundingClientRect(), sb = svg.getBoundingClientRect();
    const px = sb.left - cb.left + xs(i) * sb.width / W + chart.scrollLeft;
    tip.style.left = (px + 12 + tip.offsetWidth > chart.scrollLeft + cb.width ? px - tip.offsetWidth - 12 : px + 12) + "px"; tip.style.top = "8px";
  });
  svg.addEventListener("pointerup", () => { if (!drag) return; const [a, b] = [Math.min(drag.a, drag.b), Math.max(drag.a, drag.b)]; drag = null;
    if (b - a >= 2) { lo = Math.max(0, a); hi = Math.min(months.length - 1, b); draw(); $("#te-said", root).textContent = `Showing ${label(months[lo])} to ${label(months[hi])}.`; }
    else { const i = Math.max(lo, Math.min(hi, a)); const vis = ser.filter(s => s.on); const n = vis.reduce((t, s) => t + s.v[i], 0);
      $("#te-said", root).textContent = `On the real site this opens the ${fmt(n)} debates of ${label(months[i])} on the topics you have on.`; draw(); } });
  svg.addEventListener("pointerleave", () => { if (!drag) { tip.hidden = true; draw(); } });
  $$(".te-legend button", root).forEach(b => b.addEventListener("click", () => { const s = ser[+b.dataset.i];
    if (s.on && ser.filter(x => x.on).length === 1) return; s.on = !s.on; b.setAttribute("aria-pressed", String(s.on)); draw(); }));
  $("#te-reset", root).addEventListener("click", () => { lo = 0; hi = months.length - 1; draw(); $("#te-said", root).textContent = ""; });
  draw();
}

/* ---------------- 7. How it is built ---------------- */
function howBuilt(root, D) {
  const GH = "https://github.com/Shanahan-Suresh/tanya-dewan/blob/main/";
  const M = D.meta, done = D.answer.events.find(e => e.event === "done").data;
  const N = [
    { g: "Gather", id: "acts", b: "Acts", n: `${fmt(M.acts)} Acts`, s: "From the Attorney General's Chambers", d: [`${fmt(M.sections)} sections, in Malay and English.`, "Scanned pages go through OCR, then a text check."], f: ["parlimen/acts.py", "parlimen/act_text.py", "parlimen/act_ocr.py"] },
    { g: "Gather", id: "hansard", b: "Hansard", n: "2018 to now", s: "Every sitting's PDF", d: ["Each file is fetched once and cached, politely rate-limited.", "Draft sittings are checked again each week until the final copy appears."], f: ["parlimen/fetch.py", "parlimen/sittings.py", "parlimen/drafts.py"] },
    { g: "Understand", id: "parse", b: "Parse who spoke", n: `${fmt(M.speeches)} speeches`, s: "Code, not AI, decides", d: ["The parser reads speaker lines, seats and times from the PDF text.", `It links each speaker to one of ${fmt(M.members)} MPs and their party on that date.`], f: ["parlimen/hansard.py", "parlimen/parties.py", "parlimen/links.py"] },
    { g: "Understand", id: "enrich", b: "Enrich", ai: 1, n: `${fmt(M.commitments)} commitments`, s: "Claude Batch, run once", d: [`${fmt(M.qa)} questions joined to the minister's answer.`, "Summaries and topic tags for each debate.", "A commitment is dropped when its quote is not in the Hansard text."], f: ["parlimen/enrich.py", "parlimen/commit_check.py"] },
    { g: "Find", id: "kw", b: "Keyword index", n: "BM25", s: "SQLite FTS5", d: ["Finds exact words, names and section numbers.", "Malay and English in one index."], f: ["parlimen/index.py", "parlimen/chunk.py"] },
    { g: "Find", id: "vec", b: "Meaning index", n: "Qwen3 0.6B", s: "Local embeddings", d: ["Finds passages that mean the same thing in other words.", "Runs on a CPU at search time."], f: ["parlimen/index.py", "parlimen/models.py"] },
    { g: "Find", id: "rank", b: "Merge and rerank", ai: 1, n: "20 → 8", s: "RRF, then Claude Haiku", d: ["Reciprocal rank fusion merges the two lists.", "Claude Haiku reads the top 20 and keeps the best 8."], f: ["parlimen/search.py", "parlimen/llm_rerank.py"] },
    { g: "Answer", id: "answer", b: "Write the answer", ai: 1, n: `${(done.total_ms / 1000).toFixed(1)} s`, s: "The salary answer above", d: ["Each sentence must cite a quoted passage.", "It refuses advice on a reader's own case.", "The text streams to the browser by server-sent events."], f: ["parlimen/answer.py"] },
    { g: "Serve", id: "web", b: "Website", n: "FastAPI", s: "Jinja and htmx", d: [`${fmt(M.units)} debate pages, plus MPs, Acts, bills and topics.`, "English and Malay, light and dark, phone first."], f: ["parlimen/web/app.py", "parlimen/records.py"] },
    { g: "Serve", id: "mcp", b: "MCP server", n: "Tools for Claude", s: "Search from any AI client", d: ["Claude can search the Acts and debates as tools."], f: ["parlimen/mcp_server.py"] },
    { g: "Serve", id: "demo", b: "Free demo", n: "No server", s: "GitHub Pages", d: ["Real pages, rendered once.", "Recorded answers play back as streams."], f: ["tools/static_demo.py", "tools/record_answers.py"] },
    { g: "Check", id: "eval", b: "Evals", n: "5 of 6 pass", s: "Targets set before the run", d: ["A fixed question set, a blind judge and a recall check.", "The results table is below."], f: ["parlimen/evaluate.py", "parlimen/judge.py", "parlimen/evalset.py"] },
  ];
  const groups = [...new Set(N.map(n => n.g))];
  const EV = [["Law questions: the right section is in the top 10", "0.85 or more", "0.907", 1], ["Debate questions: the right speech is in the top 10", "0.80 or more", "0.727", 0],
    ["The same question in Malay and English", "under 5 points apart", "0 points", 1], ["Search time on a CPU, 95th percentile", "under 3 s", "2.83 s", 1],
    ["Answers a blind judge marks correct", "65% or more", "77%", 1], ["Answers whose every claim has a quoted source", "80% or more", "82%", 1]];
  const PEOPLE = ["dzulkefly-ahmad", "sanisvara-nethaji-rayer-rajaji", "che-mohamad-zulkifly-jusoh"]
    .map(m => D.seats.find(s => s.member === m)).filter(Boolean).map(s => [s.name, `${s.code} ${s.seat}`, s.party]);
  const initials = n => n.replace(/^(Datuk Seri Dr\. Haji|Datuk|Tuan|Puan)\s+/, "").split(/\s+/).filter(w => !/^(bin|binti|a\/l)$/i.test(w)).slice(0, 2).map(w => w[0]).join("");
  root.innerHTML = `<div class="arch"><div class="flow">${groups.map(g => `<span class="lbl">${esc(g)}</span>` + N.filter(n => n.g === g).map(n =>
      `<button type="button" class="node${n.ai ? " ai" : ""}" data-id="${n.id}" aria-pressed="false"><b>${esc(n.b)}</b><span class="n">${esc(n.n)}</span><span>${esc(n.s)}</span></button>`).join("")).join("")}</div>
      <div class="card detail" id="hb-d" aria-live="polite"></div></div>
    <div class="evals"><table><thead><tr><th>What was measured</th><th>Target</th><th class="r">Result</th><th>Met?</th></tr></thead><tbody>
      ${EV.map(([a, t, r, ok]) => `<tr><td>${esc(a)}</td><td>${esc(t)}</td><td class="r">${esc(r)}</td><td>${ok ? `<span class="pass">${icon("check")}Yes</span>` : `<span class="miss">${icon("warn")}Missed</span>`}</td></tr>`).join("")}</tbody></table></div>
    <div class="polish">
      <div class="card"><h4>Light and dark</h4><p>The site follows the reader's system. A switch lets them choose. Try it: it changes this whole page.</p>
        <button class="btn ghost" type="button" id="hb-theme"></button></div>
      <div class="card"><h4>Smooth page changes</h4><p>Pages slide into each other, and the MP's badge moves into place. Press a name.</p>
        <div id="hb-vt"></div></div>
      <div class="card"><h4>A list of keys</h4><p>Press <kbd>?</kbd> on any page to see every shortcut.</p>
        <button class="btn ghost" type="button" id="hb-keys">Show the keys</button></div>
    </div>`;
  const d = $("#hb-d", root);
  function sel(id) { const n = N.find(x => x.id === id);
    $$(".node", root).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.id === id)));
    d.innerHTML = `<span class="hint">${esc(n.g)}</span><h3>${esc(n.b)}${n.ai ? ` <span class="label-ai">${icon("spark")}Uses Claude</span>` : ""}</h3><ul>${n.d.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
      <span class="hint">The code</span><div class="files">${n.f.map(f => `<a href="${GH + f}" target="_blank" rel="noopener">${esc(f)}</a>`).join("")}</div>`; }
  $$(".node", root).forEach(b => b.addEventListener("click", () => sel(b.dataset.id)));
  sel("parse");

  const html = document.documentElement, tb = $("#hb-theme", root);
  const THEMES = [[null, "Theme: same as your system"], ["dark", "Theme: dark"], ["light", "Theme: light"]];
  let ti = 0; const setT = () => { const [v, l] = THEMES[ti]; if (v) html.setAttribute("data-theme", v); else html.removeAttribute("data-theme");
    tb.innerHTML = icon(v === "light" ? "sun" : "moon") + esc(l); };
  tb.addEventListener("click", () => { ti = (ti + 1) % THEMES.length; setT(); }); setT();

  const vt = $("#hb-vt", root);
  const list = () => { vt.innerHTML = `<div class="vt-list">${PEOPLE.map((p, i) => `<button type="button" class="vt-item" data-i="${i}"><span class="vt-av">${esc(initials(p[0]))}</span><span>${esc(p[0])}</span></button>`).join("")}</div>`;
    $$(".vt-item", vt).forEach(b => b.addEventListener("click", () => go(() => full(+b.dataset.i), b))); };
  const full = i => { const p = PEOPLE[i]; vt.innerHTML = `<div class="vt-full"><span class="vt-av" style="view-transition-name:vt-av">${esc(initials(p[0]))}</span><h5>${esc(p[0])}</h5><span class="hint">${esc(p[1])} · ${esc(p[2])}</span><button class="btn ghost" type="button" id="vt-back">Back to the list</button></div>`;
    $("#vt-back", vt).addEventListener("click", () => go(list)); $("#vt-back", vt).focus(); };
  const go = (fn, from) => { if (from) $(".vt-av", from).style.viewTransitionName = "vt-av";
    if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) document.startViewTransition(fn); else fn(); };
  list();
  $("#hb-keys", root).addEventListener("click", () => openKeys());
}

/* ---------------- Keys sheet ---------------- */
let keysOpener = null;
function openKeys() { keysOpener = document.activeElement; $("#keys").hidden = false; $("#scrim").hidden = false; $("#keys-close").focus(); }
function closeKeys() { $("#keys").hidden = true; $("#scrim").hidden = true; if (keysOpener) keysOpener.focus(); }
$("#keys-close").addEventListener("click", closeKeys); $("#scrim").addEventListener("click", closeKeys);
document.addEventListener("keydown", e => {
  if (e.key === "?" && !typing(e)) { e.preventDefault(); openKeys(); }
  else if (e.key === "Escape" && !$("#keys").hidden) closeKeys();
  else if (e.key === "Tab" && !$("#keys").hidden) { e.preventDefault(); $("#keys-close").focus(); }
});

/* ---------------- Picks ---------------- */
const CHOICES = [["build", "Build it"], ["maybe", "Maybe"], ["skip", "Skip"]];
const sections = $$(".concept");
const picks = {};
const saveState = $("#save-state");
$("#tally-nav").innerHTML = sections.map((s, i) => `<a href="#${s.id}" data-k="${s.dataset.key}" aria-label="Upgrade ${i + 1}">${i + 1}</a>`).join("");
function paint() {
  for (const s of sections) { const c = picks[s.dataset.key];
    $$(".pick button", s).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.c === c))); }
  $$("#tally-nav a").forEach(a => { const c = picks[a.dataset.k]; if (c) a.dataset.c = c; else delete a.dataset.c;
    a.setAttribute("aria-label", `Upgrade ${a.textContent}: ${c ? CHOICES.find(x => x[0] === c)[1] : "not picked yet"}`); });
  $("#tally-n").textContent = sections.filter(s => picks[s.dataset.key]).length;
}
for (const s of sections) {
  $(".pick", s).innerHTML = `<span class="q">Your pick:</span>` + CHOICES.map(([c, l]) => `<button type="button" data-c="${c}" aria-pressed="false">${icon("check")}${l}</button>`).join("");
}
let db = null;
document.addEventListener("click", async e => {
  const b = e.target.closest(".pick button"); if (!b) return;
  const key = b.closest(".concept").dataset.key, c = b.dataset.c;
  if (picks[key] === c) return; picks[key] = c; paint();
  if (!db) { saveState.textContent = "Picks cannot be saved here. Tell me your picks in chat."; return; }
  saveState.textContent = "Saving…";
  try { await db.collection("picks").doc(key).set({ choice: c, at: new Date().toISOString() }); saveState.textContent = "Saved."; }
  catch (err) { saveState.textContent = "That pick did not save. Try again, or tell me in chat."; }
});
paint();
(async () => {
  const timer = setTimeout(() => { if (!db) saveState.textContent = "Saved picks are not reachable yet."; }, 10000);
  try { db = window.claude?.use ? await window.claude.use("db") : null; } catch { db = null; }
  if (!db) { clearTimeout(timer); saveState.textContent = "Picks cannot be saved here. Tell me your picks in chat."; return; }
  db.collection("picks").onSnapshot(snap => { clearTimeout(timer);
    for (const d of snap.docs) { const v = d.data(); if (v && v.choice) picks[d.id] = v.choice; }
    if (saveState.textContent.startsWith("Saved picks")) saveState.textContent = ""; paint(); },
    () => { clearTimeout(timer); saveState.textContent = "Saved picks could not be read. Tell me in chat."; });
})();
})();
