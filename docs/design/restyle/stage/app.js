/* Stage: shared chrome, the chamber arc and the page scripts. Plain vanilla JS. */
(function () {
  "use strict";
  var TD = window.TD, NS = "http://www.w3.org/2000/svg";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var fmt = function (n) { return Number(n).toLocaleString("en-GB"); };
  var page = document.body.dataset.page;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- theme ---------- */
  var root = document.documentElement, mode = "auto";
  try { mode = localStorage.getItem("td-theme") || "auto"; } catch (e) { /* storage blocked */ }
  function applyTheme() {
    if (mode === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", mode);
    var b = $("#theme-btn"); if (!b) return;
    var lab = { auto: "Theme: same as your device", light: "Theme: light", dark: "Theme: dark" }[mode];
    b.setAttribute("aria-label", lab); b.title = lab;
    var ic = { auto: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>', light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>', dark: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>' }[mode];
    b.querySelector("svg").innerHTML = ic;
  }
  applyTheme();

  /* ---------- chrome ---------- */
  var ico = function (p, c) { return '<svg class="i ' + (c || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + p + "</svg>"; };
  var NAV = [["Ask", "home.html", "home"], ["Acts", "#", ""], ["Sittings", "debate.html", "debate"], ["Questions", "#", ""], ["Commitments", "#", ""], ["MPs", "mp.html", "mp"], ["Bills", "#", ""], ["Topics", "#", ""]];
  var navHtml = NAV.map(function (n) { return '<a href="' + n[1] + '"' + (n[2] === page ? ' aria-current="page"' : "") + ">" + n[0] + "</a>"; }).join("");
  var LOGO = '<svg viewBox="0 0 64 64" aria-hidden="true"><path class="bm-o" d="M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z" stroke-linejoin="round" stroke-width="3"/><path class="bm-r" d="M32 19 L45 32 L32 45 L19 32 Z" fill="none" stroke-width="3"/><path d="M32 26 L38 32 L32 38 L26 32 Z" fill="#F5B800"/></svg>';
  var LANG = '<div class="lang" role="group" aria-label="Language"><span lang="en" aria-current="true" title="English">EN</span><a href="#" lang="ms" hreflang="ms" title="Bahasa Melayu">BM</a></div>';
  var hdr = document.createElement("header");
  hdr.className = "hdr"; hdr.id = "hdr";
  hdr.innerHTML = '<div class="wrap"><a class="brand" href="home.html" aria-label="Tanya Dewan">' + LOGO + 'Tanya Dewan</a><nav class="nav" aria-label="Main menu">' + navHtml + '</nav><div class="tools">' +
    '<button class="tbtn" id="jump-btn" type="button" aria-haspopup="dialog">' + ico('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>', "sm") + '<span class="jt">Jump to</span><kbd>Ctrl K</kbd></button>' +
    '<button class="tbtn" id="theme-btn" type="button">' + ico("") + '</button>' + LANG +
    '<button class="tbtn menu-btn" id="menu-btn" type="button" aria-expanded="false" aria-controls="menu-panel" aria-label="Menu">' + ico('<path d="M4 7h16M4 12h16M4 17h16"/>') + '</button></div></div>' +
    '<div class="menu-panel" id="menu-panel">' + navHtml + LANG + "</div>";
  document.body.prepend(hdr);
  var skip = document.createElement("a"); skip.className = "skip"; skip.href = "#main"; skip.textContent = "Skip to the content"; document.body.prepend(skip);
  var tab = function (h, l, p, cur) { return '<a href="' + h + '"' + (cur ? ' aria-current="page"' : "") + ">" + ico(p) + l + "</a>"; };
  var tb = document.createElement("nav"); tb.className = "tabbar"; tb.setAttribute("aria-label", "Main tabs");
  tb.innerHTML = tab("home.html", "Ask", '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>', page === "home") + tab("#", "Acts", '<path d="M6 3h9l4 4v14H6z"/><path d="M9 13h7M9 17h7"/>') + tab("debate.html", "Sittings", '<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>', page === "debate") + tab("mp.html", "MPs", '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>', page === "mp") +
    '<button type="button" id="tab-jump">' + ico('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>') + "Jump to</button>";
  document.body.append(tb);
  var ft = document.createElement("footer"); ft.className = "ftr";
  ft.innerHTML = '<div class="wrap"><p>' + ico('<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>') + '<span><b>Sources.</b> Laws of Malaysia Online (Attorney General\'s Chambers) and the Hansard of the Parliament of Malaysia. Acts and parliamentary debates carry no copyright (Copyright Act 1987, section 3).</span></p>' +
    '<p>' + ico('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>') + '<span><b>AI.</b> Summaries, question matches and commitment notes are written by AI and labelled as such. Speeches and Act sections are verbatim.</span></p>' +
    '<p>' + ico('<path d="M12 4v16M6 20h12M5 8h14M5 8l-2.5 6a3 3 0 0 0 5 0zM19 8l-2.5 6a3 3 0 0 0 5 0z"/>') + '<span><b>Not legal advice.</b> This is general information from the published record, not legal advice.</span></p>' +
    '<div class="links"><a href="#">About</a><a href="#">How it works</a></div></div>';
  document.body.append(ft);
  $("#theme-btn").addEventListener("click", function () { mode = { auto: "light", light: "dark", dark: "auto" }[mode]; try { localStorage.setItem("td-theme", mode); } catch (e) { /* ignore */ } applyTheme(); });
  applyTheme();
  var mb = $("#menu-btn"), mp_ = $("#menu-panel");
  mb.addEventListener("click", function () { var o = mp_.classList.toggle("open"); mb.setAttribute("aria-expanded", o); });
  function onScroll() {
    var y = window.scrollY; hdr.classList.toggle("condensed", y > 40);
    var p = Math.min(y / 520, 1); var a = $(".hero-arc");
    if (a) { a.style.opacity = 1 - p * .85; a.style.transform = "translateY(" + p * 36 + "px)"; }
  }
  window.addEventListener("scroll", onScroll, { passive: true }); onScroll();

  /* jump dialog */
  var dlg = document.createElement("dialog"); dlg.className = "jump"; dlg.setAttribute("aria-label", "Jump to");
  dlg.innerHTML = '<label class="sr-only" for="jin">Jump to an MP, seat or page</label><input id="jin" type="text" autocomplete="off" placeholder="Jump to an MP, a seat or a page"><ul id="jlist"></ul><form method="dialog" style="margin-top:12px"><button class="btn-s" style="color:#fff">Close</button></form>';
  document.body.append(dlg);
  function jumpList() {
    var q = $("#jin").value.trim().toLowerCase(), out = [];
    NAV.forEach(function (n) { if (!q || n[0].toLowerCase().indexOf(q) > -1) out.push('<li><a href="' + n[1] + '">' + n[0] + "<span>Page</span></a></li>"); });
    if (q) TD.seats.filter(function (s) { return (s.name + " " + s.seat + " " + s.code).toLowerCase().indexOf(q) > -1; }).slice(0, 6).forEach(function (s) { out.push('<li><a href="' + (s.code === "P063" ? "mp.html" : "#") + '">' + esc(s.name) + "<span>" + s.code + " " + esc(s.seat) + "</span></a></li>"); });
    $("#jlist").innerHTML = out.slice(0, 9).join("");
  }
  function openJump() { dlg.showModal(); $("#jin").value = ""; jumpList(); $("#jin").focus(); }
  $("#jin").addEventListener("input", jumpList);
  $("#jump-btn").addEventListener("click", openJump); $("#tab-jump").addEventListener("click", openJump);
  document.addEventListener("keydown", function (e) { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openJump(); } });

  /* ---------- chamber arc ---------- */
  var BLOCS = ["PN", "Other", "GRS", "GPS", "BN", "PH"];
  var BNAME = { PH: "Pakatan Harapan", BN: "Barisan Nasional", GPS: "Gabungan Parti Sarawak", GRS: "Gabungan Rakyat Sabah", Other: "Other parties and independents", PN: "Perikatan Nasional" };
  function mk(tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function positions(o) {
    var N = TD.seats.length, rad = [], sum = 0, i, j;
    for (i = 0; i < o.rows; i++) { rad.push(o.r0 + (o.r1 - o.r0) * i / (o.rows - 1)); sum += rad[i]; }
    var cnt = rad.map(function (r) { return Math.round(N * r / sum); });
    cnt[o.rows - 1] += N - cnt.reduce(function (a, b) { return a + b; }, 0);
    var pos = [];
    for (i = 0; i < o.rows; i++) for (j = 0; j < cnt[i]; j++) { var a = Math.PI - Math.PI * j / (cnt[i] - 1); pos.push({ x: o.cx + rad[i] * Math.cos(a), y: o.cy - rad[i] * Math.sin(a), a: a, row: i }); }
    pos.sort(function (p, q) { return q.a - p.a || p.row - q.row; });
    return { pos: pos, rad: rad };
  }
  var ordered = BLOCS.reduce(function (a, b) { return a.concat(TD.seats.filter(function (s) { return s.bloc === b; }).sort(function (p, q) { return p.code < q.code ? -1 : 1; })); }, []);
  function drawArc(svg, o) {
    var L = positions(o), byCode = {};
    if (o.lines) L.rad.forEach(function (r) { mk("path", { class: "row", d: "M" + (o.cx - r) + " " + o.cy + " A" + r + " " + r + " 0 0 1 " + (o.cx + r) + " " + o.cy }, svg); });
    ordered.forEach(function (s, k) {
      var p = L.pos[k], c = mk("circle", { class: "seat" + (o.color ? " b-" + s.bloc : ""), cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: o.dot, "data-code": s.code }, svg);
      if (o.titles) mk("title", {}, c).textContent = s.name + ", " + s.code + " " + s.seat + ", " + s.party;
      byCode[s.code] = { el: c, x: p.x, y: p.y, s: s };
    });
    return byCode;
  }

  /* counters */
  function countUp(el) {
    var n = +el.dataset.n, done = false;
    function go() { if (done) return; done = true; if (reduce) { el.textContent = fmt(n); return; } var t0 = performance.now(); (function f(t) { var k = Math.min((t - t0) / 1100, 1); el.textContent = fmt(Math.round(n * (1 - Math.pow(1 - k, 3)))); if (k < 1) requestAnimationFrame(f); })(t0); }
    if ("IntersectionObserver" in window) { var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { go(); io.disconnect(); } }); io.observe(el); } else go();
  }
  function onceVisible(el, cls) {
    if (!("IntersectionObserver" in window)) { el.classList.add(cls); return; }
    var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { el.classList.add(cls); io.disconnect(); } }, { rootMargin: "0px 0px 12% 0px" }); io.observe(el);
  }

  var aiLabel = function (t) { return '<span class="label-ai">' + ico('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>', "sm") + t + "</span>"; };
  function commitCard(c) {
    var facts = (c.facts || []).map(function (f) { var p = f.split(": "); return "<span>" + esc(p[0]) + ": <b>" + esc(p.slice(1).join(": ")) + "</b></span>"; }).join("");
    return '<article class="card commit"><div class="rec q" lang="ms">' + esc(c.quote.replace(/[“”]/g, "")) + '</div><p class="who">' + esc(c.who) + '</p><div class="ai-line">' + aiLabel("Commitment (AI)") + "<span>" + esc(c.ai) + "</span>" + (facts ? '<p class="facts">' + facts + "</p>" : "") + "</div>" + (c.ctx ? '<p class="who">' + esc(c.ctx) + "</p>" : "") + "</article>";
  }
  function legendHtml() {
    var c = {}; TD.seats.forEach(function (s) { c[s.bloc] = (c[s.bloc] || 0) + 1; });
    return ["PH", "BN", "GPS", "GRS", "Other", "PN"].map(function (b) { return '<li><i class="b-' + b + '" style="background:var(--b-' + b + ')"></i><span>' + BNAME[b] + "</span><b>" + c[b] + "</b></li>"; }).join("") + '<li class="tot"><span>Seats in the Dewan Rakyat</span><b style="color:#fff">222</b></li>';
  }

  /* ================= HOME ================= */
  function home() {
    var hs = $("#hero-arc");
    drawArc(hs, { cx: 800, cy: 700, r0: 500, r1: 690, rows: 5, dot: 4.6, lines: true });
    mk("path", { class: "row", d: "M40 700 H1560" }, hs);
    $$("[data-n]").forEach(countUp);
    var cb = drawArc($("#cham-arc"), { cx: 500, cy: 505, r0: 170, r1: 480, rows: 8, dot: 13, color: true, titles: true, lines: true });
    $("#legend").innerHTML = legendHtml();
    /* finder */
    var fin = $("#find-in"), fl = $("#find-list"), pk = $("#picked"), sel = null;
    function pick(code) {
      if (sel) cb[sel].el.classList.remove("sel"); sel = code; var o = cb[code]; o.el.classList.add("sel"); $("#cham-arc").classList.add("has-lit"); o.el.classList.add("lit");
      var s = o.s; pk.hidden = false; pk.innerHTML = "<b>" + esc(s.name) + "</b><br>" + s.code + " " + esc(s.seat) + ", " + esc(s.party) + ", " + BNAME[s.bloc]; fl.innerHTML = "";
    }
    fin.addEventListener("input", function () {
      var q = fin.value.trim().toLowerCase(); if (q.length < 2) { fl.innerHTML = ""; return; }
      fl.innerHTML = TD.seats.filter(function (s) { return (s.name + " " + s.seat + " " + s.code).toLowerCase().indexOf(q) > -1; }).slice(0, 5).map(function (s) { return '<li><button type="button" data-c="' + s.code + '">' + esc(s.name) + " <span class=\"mute\">" + s.code + " " + esc(s.seat) + "</span></button></li>"; }).join("");
    });
    fl.addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) pick(b.dataset.c); });
    /* lists */
    $("#sit-list").innerHTML = TD.sittings.map(function (s) {
      var m = s.raw.match(/^(Dewan Rakyat|Special Chamber) (\d+ \w+ \d+) (\d+) debates( unrevised draft)?/);
      return '<li><a href="debate.html"><b>' + m[2] + "</b><span>" + m[3] + ' debates</span><span>' + m[1] + "</span>" + (m[4] ? '<span class="status">' + ico('<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>', "sm") + "Unrevised draft</span>" : "<span></span>") + "</a></li>";
    }).join("");
    $("#com-list").innerHTML = TD.homeCommitments.map(commitCard).join("");
    /* topics */
    var tot = {}; $("#topics").innerHTML = TD.topics.map(function (t) {
      var pts = t.points, max = Math.max.apply(null, pts.map(function (p) { return p[1]; })), sum = pts.reduce(function (a, p) { return a + p[1]; }, 0);
      var x0 = 2018 * 12 + 6, x1 = 2026 * 12 + 9, bars = pts.map(function (p) { var ym = p[0].split("-"), m = +ym[0] * 12 + +ym[1] - 1, h = Math.max(2, 106 * p[1] / max); return '<rect x="' + (2 + 296 * (m - x0) / (x1 - x0)).toFixed(1) + '" y="' + (108 - h).toFixed(1) + '" width="2.4" height="' + h.toFixed(1) + '"><title>' + p[0] + ": " + p[1] + "</title></rect>"; }).join("");
      return '<div class="topic"><h3>' + esc(t.name.charAt(0).toUpperCase() + t.name.slice(1)) + "</h3><p>" + fmt(sum) + ' debates, 2018 to 2026</p><svg viewBox="0 0 300 110" preserveAspectRatio="none" role="img" aria-label="' + esc(t.name) + ' debates by month">' + bars + '</svg><div class="ax"><span>2018</span><span>2022</span><span>2026</span></div></div>';
    }).join("");
    $$(".topic").forEach(function (t) { onceVisible(t, "in"); });
    /* ask */
    var form = $("#ask"), qin = $("#q");
    $$(".try").forEach(function (b) { b.addEventListener("click", function () { qin.value = b.dataset.q; qin.focus(); }); });
    form.addEventListener("submit", function (e) { e.preventDefault(); run(false); });
    answerInit();
  }

  /* ---------- answer ---------- */
  var A = null, running = false, reader;
  function lastEv(name) { return A.events.filter(function (e) { return e.event === "stage" && e.data.name === name && e.data.hits != null; })[0]; }
  function seatPlan() { var s = 7 | 0, idx = TD.seats.map(function (_, i) { return i; }); function r() { s = (s + 0x6D2B79F5) | 0; var t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; } for (var i = idx.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), x = idx[i]; idx[i] = idx[j]; idx[j] = x; } return idx; }
  var order = null, seatEls = [];
  function lightSeats(level, from, to, clear) {
    seatEls.forEach(function (el, i) { if (clear) el.setAttribute("class", "seat"); });
    for (var k = from; k < to; k++) seatEls[order[k]].setAttribute("class", "seat " + level);
  }
  function answerInit() {
    var g = $("#ans-arc"); drawArc(g, { cx: 500, cy: 505, r0: 170, r1: 480, rows: 8, dot: 11 });
    seatEls = $$(".seat", g); order = seatPlan();
    A = TD.answer;
    reader = { n: 1 };
    window.demoAnswer = function () { return run(true); };
    window.demoReader = function () { return run(true).then(function () { openReader(1); }); };
    $("#rd-close").addEventListener("click", closeReader); $("#scrim").addEventListener("click", closeReader);
    $("#rd-prev").addEventListener("click", function () { openReader(reader.n - 1); }); $("#rd-next").addEventListener("click", function () { openReader(reader.n + 1); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("#reader").hidden) closeReader(); });
    $("#answer").addEventListener("click", function (e) { var b = e.target.closest(".cite"); if (b) openReader(+b.dataset.n); });
  }
  function mdHtml(t) {
    if ((t.match(/\*\*/g) || []).length % 2) t += "**";
    t = t.replace(/\[\d?$/, "");
    var out = "", open = false;
    t.split("\n").forEach(function (l) {
      var li = /^- /.test(l); if (!li && open) { out += "</ul>"; open = false; }
      if (li && !open) { out += "<ul>"; open = true; }
      var h = esc(l.replace(/^- /, "")).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[(\d)\]/g, '<button class="cite" type="button" data-n="$1" aria-label="Open source $1">$1</button>');
      if (li) out += "<li>" + h + "</li>"; else if (l.trim()) out += "<p>" + h + "</p>";
    });
    return out + (open ? "</ul>" : "");
  }
  var STEPS = [["all", "Speeches and Act sections searched"], ["bm25", "Found by keyword"], ["dense", "Found by meaning"], ["fused", "Merged, duplicates removed"], ["reranked", "Kept after reranking"], ["cited", "Cited in the answer"]];
  var MAXN = 427728;
  function setStep(key, hits, ms, final) {
    var li = $('[data-step="' + key + '"]'); li.classList.add("on");
    if (hits == null) { $(".c", li).textContent = "..."; return; }
    $(".c", li).textContent = fmt(hits); if (ms != null) $(".ms", li).textContent = fmt(ms) + " ms";
    $(".bar", li).style.width = Math.max(1.5, 100 * Math.log10(hits + 1) / Math.log10(MAXN + 1)) + "%";
  }
  async function run(instant) {
    if (running && !instant) return; running = true;
    var d = A.events[A.events.length - 1].data, root_ = document.body;
    var q = $("#q").value.trim(); if (instant || !q) $("#q").value = A.question;
    root_.classList.add("asking"); root_.classList.toggle("instant", instant);
    $("#answer").hidden = false; $("#record").hidden = false; $("#sources-wrap").hidden = true; $("#passages-wrap").hidden = true;
    $("#ans-q").textContent = $("#q").value; $("#ans-text").innerHTML = ""; $("#ans-meta").hidden = true; $("#ans-foot").hidden = true;
    $("#funnel").innerHTML = STEPS.map(function (s, i) { return '<li data-step="' + s[0] + '"' + (i === 5 ? ' class="last"' : "") + '><div class="top"><span>' + s[1] + '</span><span><span class="ms"></span> <b class="c">&nbsp;</b></span></div><div class="track"><div class="bar"></div></div></li>'; }).join("");
    lightSeats("", 0, 0, true);
    var k = instant ? 0 : 0.4, t0 = A.events[0].t - 300;
    var stagesDone = function () { return $$("#funnel li.on").length; };
    setStep("all", MAXN, null);
    if (!instant) $("#answer").scrollIntoView({ block: "start", behavior: "smooth" });
    var plan = { bm25: [0, 80, "l1"], dense: [40, 130, "l1"], fused: [0, 150, "l1"], reranked: [0, 20, "l2"] };
    var prev = t0, textStarted = false;
    for (var i = 0; i < A.events.length; i++) {
      var e = A.events[i];
      if (e.event !== "stage") continue;
      if (e.data.name === "answer") continue;
      if (!instant) await sleep(Math.max(0, (e.t - prev) * k)); prev = e.t;
      setStep(e.data.name, e.data.hits, e.data.ms);
      if (e.data.hits != null) { var p = plan[e.data.name]; lightSeats(p[2], p[0], p[1], e.data.name === "reranked"); }
      if (e.data.name === "reranked" && e.data.hits != null) { renderPassages(); $("#passages-wrap").hidden = false; }
    }
    if (!instant) await sleep(500);
    setStep("cited", d.sources.length, null); lightSeats("l2", 0, 20, true); lightSeats("l3", 0, 3, false);
    $("#ans-meta").hidden = false;
    var words = d.answer.split(/(\s+)/), cur = "";
    var box = $("#ans-text");
    if (instant) { box.innerHTML = mdHtml(d.answer); }
    else { for (var w = 0; w < words.length; w++) { cur += words[w]; if (/\S/.test(words[w])) { box.innerHTML = mdHtml(cur) ; var lastEl = box.lastElementChild; if (lastEl) lastEl.insertAdjacentHTML("beforeend", '<span class="cursor"></span>'); await sleep(34); } } box.innerHTML = mdHtml(d.answer); }
    $("#ans-foot").hidden = false; $("#ans-ms").textContent = (d.total_ms / 1000).toFixed(1) + " s in all, " + (d.search_ms / 1000).toFixed(1) + " s of it searching";
    renderSources(d); $("#sources-wrap").hidden = false; running = false; return true;
  }
  function renderPassages() {
    var d = A.events[A.events.length - 1].data;
    $("#pass-list").innerHTML = d.passages.map(function (p) { return '<li class="card"><b>' + esc(p.title) + "</b><span>" + esc(p.meta) + " . " + esc(p.cite) + "</span></li>"; }).join("");
    $("#pass-n").textContent = d.passages.length;
  }
  function renderSources(d) {
    $("#src-grid").innerHTML = d.sources.map(function (s) {
      return '<article class="card src"><span class="n">' + s.n + "</span><div><h3>" + esc(s.title) + '</h3><p class="who">' + esc(s.cite) + "</p></div>" + s.quotes.map(function (q) { return '<blockquote><span class="label-rec">' + ico('<path d="M6 3h9l4 4v14H6z"/>', "sm") + 'Verbatim</span><br><q>' + esc(q) + "</q></blockquote>"; }).join("") +
        '<div class="row"><button class="btn-s" type="button" data-open="' + s.n + '">' + ico('<path d="M4 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H4zM20 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z"/>', "sm") + 'Read the full text</button><a class="btn-s" href="' + esc(s.pdf) + '" rel="noopener">' + ico('<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>', "sm") + "Official PDF</a></div></article>";
    }).join("");
    $$("[data-open]").forEach(function (b) { b.addEventListener("click", function () { openReader(+b.dataset.open); }); });
  }
  var lastFocus = null;
  function openReader(n) {
    var d = A.events[A.events.length - 1].data, s = d.sources[n - 1]; if (!s) return; reader.n = n;
    var p = d.passages.filter(function (x) { return x.cite === s.cite; })[0];
    var text = (p ? p.text : s.quotes.join(" ")).replace(/\s*\n\s*/g, " ");
    var html = esc(text);
    s.quotes.forEach(function (q) {
      var words = q.replace(/\s+/g, " ").trim().split(" ").map(function (w) { return esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
      var m = new RegExp(words.join("\\s+")).exec(html); if (m) html = html.slice(0, m.index) + "<mark>" + m[0] + "</mark>" + html.slice(m.index + m[0].length);
    });
    $("#rd-title").textContent = s.title; $("#rd-meta").textContent = s.cite + ". " + s.meta; $("#rd-text").innerHTML = html;
    $("#rd-pdf").href = s.pdf; $("#rd-pos").textContent = "Source " + n + " of " + d.sources.length;
    $("#rd-prev").disabled = n <= 1; $("#rd-next").disabled = n >= d.sources.length;
    if ($("#reader").hidden) lastFocus = document.activeElement;
    $("#reader").hidden = false; $("#scrim").hidden = false; $("#rd-close").focus();
  }
  function closeReader() { $("#reader").hidden = true; $("#scrim").hidden = true; if (lastFocus && lastFocus.focus) lastFocus.focus(); }

  /* ================= MP ================= */
  function mpPage() {
    var M = TD.mp, svg = $("#mp-arc"), cb = drawArc(svg, { cx: 500, cy: 505, r0: 170, r1: 480, rows: 8, dot: 13, color: true, titles: true });
    var o = cb.P063; o.el.classList.add("lit"); svg.classList.add("has-lit");
    var tx = Math.min(Math.max(o.x, 90), 910), t = mk("text", { x: tx, y: o.y - 24, "text-anchor": "middle" }, svg); t.textContent = "P063 Tambun";
    $("#mp-stats").innerHTML = M.stats.map(function (s) { return '<div><b data-n="' + s[0] + '">0</b><span>' + esc(s[1]) + "</span></div>"; }).join("");
    $$("[data-n]").forEach(countUp);
    var ml = Math.max.apply(null, [].concat.apply([], M.heat.map(function (r) { return r.v; })));
    var lvl = function (v) { return v === 0 ? 0 : Math.min(4, 1 + Math.floor(3.999 * v / ml)); };
    $("#heat").innerHTML = '<thead><tr><td></td>' + "JFMAMJJASOND".split("").map(function (m, i) { return '<th scope="col" aria-label="' + (i + 1) + '">' + m + "</th>"; }).join("") + '<th scope="col">Total</th></tr></thead><tbody>' + M.heat.map(function (r) {
      return '<tr><th scope="row">' + r.y + "</th>" + r.v.map(function (v, i) { return '<td class="c" data-l="' + lvl(v) + '" title="' + r.y + "-" + String(i + 1).padStart(2, "0") + ": " + v + '"><span class="sr-only">' + v + "</span></td>"; }).join("") + '<td class="tot">' + r.v.reduce(function (a, b) { return a + b; }, 0) + "</td></tr>";
    }).join("") + "</tbody>";
    var tm = M.topics[0][1];
    $("#tbars").innerHTML = M.topics.map(function (t) { return "<li><span>" + esc(t[0]) + '</span><span class="mute">' + t[1] + '</span><i style="width:' + Math.round(100 * t[1] / tm) + '%"></i></li>'; }).join("");
    $("#party").innerHTML = M.party.map(function (p) { return "<li><b>" + esc(p[0]) + '</b><span class="who">' + esc(p[1]) + "</span></li>"; }).join("");
    $("#offices").innerHTML = M.offices.map(function (p) { return "<li><b>" + esc(p[0]) + '</b><span class="who">' + esc(p[1]) + "</span></li>"; }).join("");
    $("#mp-com").innerHTML = M.commitments.slice(0, 4).map(commitCard).join("");
    $("#mp-qa").innerHTML = M.qa.map(qaCard).join("");
  }
  function qaCard(q) {
    return '<article class="card qa"><div class="pair"><div><p class="k">' + aiLabel("Q (AI)") + "</p><p>" + esc(q.q) + '</p><p class="who">' + esc(q.qwho) + '</p></div><div><p class="k">' + aiLabel("A (AI)") + "</p><p>" + esc(q.a) + '</p><p class="who">' + esc(q.awho) + "</p></div></div>" +
      (q.figs && q.figs.length ? '<details class="figs-d"><summary>Figures given (' + q.figs.length + ")</summary><ul>" + q.figs.map(function (f) { return "<li>" + esc(f) + "</li>"; }).join("") + "</ul></details>" : "") + "</article>";
  }

  /* ================= DEBATE ================= */
  function debatePage() {
    var D = TD.debate, svg = $("#db-arc"), cb = drawArc(svg, { cx: 500, cy: 505, r0: 170, r1: 480, rows: 8, dot: 13, color: true, titles: true });
    var bySeat = {}; TD.seats.forEach(function (s) { bySeat[s.member] = s; });
    var laneOf = {}; D.bars.forEach(function (b) { laneOf[b.seq] = b.lane; });
    $("#db-kick").innerHTML = D.kicker.split(" ").length ? "<span>Dewan Rakyat, 4 Feb 2025</span><span>Parliament 15</span><span>" + D.id + "</span>" : "";
    $("#db-h").textContent = D.title;
    var lanes = ["PH", "PN", "Chair"], tipEl = $("#tip");
    $("#lanes").innerHTML = lanes.map(function (l) {
      return '<div class="lane"><span class="ln">' + l + '</span><div class="track">' + D.bars.filter(function (b) { return b.lane === l; }).map(function (b) { return '<a class="b-' + l + '" href="#' + b.seq + '" style="left:' + b.left + "%;width:" + b.w + '%" data-t="' + esc(b.t) + '"><span class="sr-only">' + esc(b.t) + "</span></a>"; }).join("") + "</div></div>";
    }).join("");
    $$("#lanes a").forEach(function (a) { var s = function () { tipEl.textContent = a.dataset.t; }; a.addEventListener("mouseenter", s); a.addEventListener("focus", s); });
    /* speakers */
    var seen = {}, sp = [];
    D.turns.forEach(function (t) { if (t.mp && !seen[t.mp]) { seen[t.mp] = 1; sp.push(t); } });
    var litCodes = [];
    $("#speakers").innerHTML = sp.map(function (t) {
      var s = bySeat[t.mp], lane = laneOf[t.seq]; if (s) litCodes.push(s.code);
      return '<li><i style="background:var(--b-' + (s ? s.bloc : lane) + ')"></i><span><b>' + esc(t.who.replace(/ \[.*\]/, "")) + "</b><small>" + (s ? s.code + " " + esc(s.seat) + ", " : "") + esc(t.party || "") + ", first at " + esc(t.spans[0]) + "</small></span></li>";
    }).join("") + '<li><i style="background:var(--b-Chair)"></i><span><b>Tuan Yang di-Pertua</b><small>In the chair</small></span></li>';
    svg.classList.add("has-lit"); litCodes.forEach(function (c) { cb[c].el.classList.add("lit"); });
    /* turns */
    $("#turns").innerHTML = D.turns.map(function (t, i) {
      var lane = laneOf[t.seq], nm = t.who.replace(/ \[.*\]/, ""), dl = /^(Datuk|Dato|Tuan|Dr|Tan|Tun|Puan|Yang)/.test(nm);
      var who = t.mp === "anwar-ibrahim" ? '<a href="mp.html">' + esc(t.who) + "</a>" : esc(t.who);
      return '<article class="turn" id="' + t.seq + '" tabindex="-1" data-i="' + i + '"><span class="av ' + lane + '" aria-hidden="true">' + (lane === "Chair" ? "YP" : esc(t.av)) + '</span><div><div class="who-l"><b>' + who + "</b>" + (t.party ? '<span class="meta">' + esc(t.party) + "</span>" : "") + '<span class="meta"><span>' + esc(t.spans[0]) + '</span><a href="https://www.parlimen.gov.my/files/hindex/pd" rel="noopener">' + esc(t.spans[1] || "") + "</a><span>" + esc(t.spans[2] || "") + '</span><a href="#' + t.seq + '" aria-label="Link to this speech">#</a></span></div><div class="txt" lang="ms">' + t.paras.map(function (p) { return "<p>" + esc(p) + "</p>"; }).join("") + "</div></div></article>";
    }).join("");
    $("#sum-text").textContent = D.summary;
    $("#sum-chips").innerHTML = D.topics.map(function (c) { return '<span class="chip">' + esc(c) + "</span>"; }).join("");
    $("#db-qa").innerHTML = D.qa.map(qaCard).join("");
    $("#db-com").innerHTML = D.commitments.map(function (c) { return commitCard({ quote: c.quote, who: c.who.replace(/\s+·.*$/, "").replace(/ \*/, ""), ai: c.ai, facts: (c.facts.match(/(Deadline|Amount): [^:]*?(?= (?:Deadline|Amount):|$)/g) || []) }); }).join("");
    /* J and K */
    var cur = -1, turns = $$(".turn");
    function go(i) { if (i < 0 || i >= turns.length) return; cur = i; turns.forEach(function (t) { t.classList.remove("cur"); }); turns[i].classList.add("cur"); turns[i].focus({ preventScroll: true }); turns[i].scrollIntoView({ block: "center" }); }
    document.addEventListener("keydown", function (e) { if (/INPUT|TEXTAREA/.test(document.activeElement.tagName) || e.ctrlKey || e.metaKey) return; if (e.key === "j") go(cur + 1); if (e.key === "k") go(cur - 1); });
    function hash() { var t = location.hash && document.getElementById(location.hash.slice(1)); if (t && t.classList.contains("turn")) { cur = +t.dataset.i; turns.forEach(function (x) { x.classList.toggle("cur", x === t); }); } }
    window.addEventListener("hashchange", hash); hash();
  }
  if (page === "home") home(); else if (page === "mp") mpPage(); else if (page === "debate") debatePage();
})();
