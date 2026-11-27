/* Tanya Dewan, Bento look. Shell, seat arc, charts, answer replay, reader. Plain JS, no libraries. */
(function () {
  "use strict";
  var TD = window.TD;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fmt = function (n) { return Number(n).toLocaleString("en-GB"); };
  var ico = function (n, c) { return '<svg class="i ' + (c || "") + '" aria-hidden="true"><use href="#i-' + n + '"/></svg>'; };
  var BLOCS = [
    ["PH", "Pakatan Harapan"], ["BN", "Barisan Nasional"], ["GPS", "Gabungan Parti Sarawak"],
    ["GRS", "Gabungan Rakyat Sabah"], ["Other", "Other parties and independents"], ["PN", "Perikatan Nasional"]
  ];
  var BLOC_NAME = {}; BLOCS.forEach(function (b) { BLOC_NAME[b[0]] = b[1]; });

  var SPRITE = '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>' +
    '<symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></symbol>' +
    '<symbol id="i-arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></symbol>' +
    '<symbol id="i-left" viewBox="0 0 24 24"><path d="M19 12H5M11 6l-6 6 6 6"/></symbol>' +
    '<symbol id="i-close" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>' +
    '<symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>' +
    '<symbol id="i-moon" viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"/></symbol>' +
    '<symbol id="i-doc" viewBox="0 0 24 24"><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></symbol>' +
    '<symbol id="i-spark" viewBox="0 0 24 24"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/></symbol>' +
    '<symbol id="i-pencil" viewBox="0 0 24 24"><path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 013 3L8 19z"/></symbol>' +
    '<symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></symbol>' +
    '<symbol id="i-check" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/></symbol>' +
    '<symbol id="i-ext" viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/></symbol>' +
    '<symbol id="i-more" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/></symbol>' +
    '<symbol id="i-home" viewBox="0 0 24 24"><path d="M4 11l8-7 8 7v9a1 1 0 01-1 1h-4v-6H9v6H5a1 1 0 01-1-1z"/></symbol>' +
    '<symbol id="i-cal" viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M9 3v4M15 3v4"/></symbol>' +
    '<symbol id="i-q" viewBox="0 0 24 24"><path d="M5 5h14a1 1 0 011 1v9a1 1 0 01-1 1h-8l-5 4v-4H5a1 1 0 01-1-1V6a1 1 0 011-1z"/></symbol>' +
    '<symbol id="i-user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/></symbol>' +
    '</defs></svg>';

  var PAGE = document.body.getAttribute("data-page");
  var NAV = [
    ["Ask", "home.html", "home"], ["Acts", "home.html#how", ""], ["Sittings", "debate.html", "debate"], ["Questions", "debate.html#qa", ""],
    ["Commitments", "mp.html#commitments", ""], ["MPs", "mp.html", "mp"], ["Bills", "home.html#how", ""], ["Topics", "home.html#topics", ""]
  ];
  var LOGO = '<svg viewBox="0 0 64 64" aria-hidden="true"><path class="bm-o" d="M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z" stroke-width="3" stroke-linejoin="round"/><path class="bm-r" d="M32 19 L45 32 L32 45 L19 32 Z" fill="none" stroke-width="3"/><path d="M32 26 L38 32 L32 38 L26 32 Z" fill="#F5B800"/></svg>';

  /* ---------- shell ---------- */
  function shell() {
    document.body.insertAdjacentHTML("afterbegin", SPRITE + '<a class="skip" href="#main">Skip to content</a>' +
      '<header class="site-header"><div class="wrap">' +
      '<a class="brand" href="home.html" aria-label="Tanya Dewan, home">' + LOGO + 'Tanya Dewan</a>' +
      '<nav class="nav" aria-label="Main">' + NAV.map(function (n) { return '<a href="' + n[1] + '"' + (n[2] === PAGE ? ' aria-current="page"' : "") + ">" + n[0] + "</a>"; }).join("") + "</nav>" +
      '<div class="tools">' +
      '<button class="btn" id="jump" type="button" aria-haspopup="dialog">' + ico("search") + '<span class="jump-txt">Jump to</span><kbd>Ctrl K</kbd></button>' +
      '<button class="btn icon" id="theme" type="button" aria-label="Switch between light and dark">' + ico("moon", "theme-moon") + ico("sun", "theme-sun") + "</button>" +
      '<div class="seg" role="group" aria-label="Language"><button type="button" aria-pressed="true" data-lang="en">EN</button><button type="button" aria-pressed="false" data-lang="ms">BM</button></div>' +
      "</div></div></header>");
    var tabs = [["Ask", "home.html", "home", "home"], ["Sittings", "debate.html", "debate", "cal"], ["Questions", "debate.html#qa", "", "q"], ["MPs", "mp.html", "mp", "user"]];
    var tb = '<nav class="tabs" aria-label="Tabs">' + tabs.map(function (t) { return '<a href="' + t[1] + '"' + (t[2] === PAGE ? ' aria-current="page"' : "") + ">" + ico(t[3]) + t[0] + "</a>"; }).join("") +
      '<button type="button" id="more">' + ico("more") + "More</button></nav>";
    document.body.insertAdjacentHTML("beforeend",
      '<footer class="site-footer"><div class="wrap"><div class="foot">' +
      "<p><b>Sources.</b> Laws of Malaysia Online (Attorney General's Chambers) and the Hansard of the Parliament of Malaysia. Acts and parliamentary debates carry no copyright (Copyright Act 1987, section 3).</p>" +
      "<p><b>AI.</b> Summaries, question matches and commitment notes are written by AI and labelled as such. Speeches and Act sections are verbatim.</p>" +
      "<p><b>Not legal advice.</b> This is general information from the published record, not legal advice.</p></div>" +
      '<div class="foot-links"><a href="home.html#how">How it works</a><a href="home.html">About</a><a href="https://github.com/" rel="noopener">Code and setup on GitHub</a></div></div></footer>' + tb +
      '<div class="pal" id="pal" role="dialog" aria-modal="true" aria-label="Jump to a page"><div class="pal-box"><label class="sr" for="pal-q">Jump to an MP, Act, bill, topic or sitting</label><input id="pal-q" type="search" placeholder="Jump to an MP, Act, bill, topic or sitting" autocomplete="off"><ul class="pal-list" id="pal-list"></ul></div></div>');
    var root = document.documentElement;
    try { var t = localStorage.getItem("td-theme"); if (t) root.setAttribute("data-theme", t); } catch (e) { /* storage blocked */ }
    $("#theme").addEventListener("click", function () {
      var dark = root.getAttribute("data-theme") ? root.getAttribute("data-theme") === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      var n = dark ? "light" : "dark"; root.setAttribute("data-theme", n);
      try { localStorage.setItem("td-theme", n); } catch (e) { /* storage blocked */ }
    });
    $$(".seg button").forEach(function (b) {
      b.addEventListener("click", function () {
        $$(".seg button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        document.documentElement.lang = b.dataset.lang === "ms" ? "ms" : "en";
        var inp = $("#q"); if (inp) inp.placeholder = b.dataset.lang === "ms" ? "Tanya tentang undang-undang atau perbahasan" : "Ask about a law or a debate, in English or Malay";
      });
    });
    palette();
  }

  function palette() {
    var pal = $("#pal"), inp = $("#pal-q"), list = $("#pal-list"), last = null;
    var items = [
      ["MP", "Dato’ Seri Anwar bin Ibrahim", "P063 Tambun", "mp.html"],
      ["Sitting", "Waktu Pertanyaan-Pertanyaan Menteri", "4 Feb 2025", "debate.html"],
      ["Act", "Employment Act 1955", "Act 265", "home.html#how"],
      ["Topic", "Budget and spending", "13,241 debates", "home.html#topics"],
      ["Topic", "Economy and finance", "8,100 debates", "home.html#topics"],
      ["Bill", "KERJA (PINDAAN) 2021", "Employment Act 1955", "home.html#how"],
      ["MP", "Datuk Seri Dr. Ronald Kiandee", "Beluran", "debate.html"]
    ].concat(NAV.map(function (n) { return ["Page", n[0], "", n[1]]; }));
    function draw(q) {
      q = (q || "").toLowerCase();
      list.innerHTML = items.filter(function (i) { return !q || (i[1] + " " + i[2]).toLowerCase().indexOf(q) > -1; })
        .map(function (i) { return '<li><a href="' + i[3] + '"><span class="k">' + i[0] + "</span>" + esc(i[1]) + '<span class="s">' + esc(i[2]) + "</span></a></li>"; }).join("") || '<li class="empty-note" style="padding:14px">Nothing in this prototype matches.</li>';
    }
    function open() { last = document.activeElement; pal.classList.add("on"); inp.value = ""; draw(""); inp.focus(); }
    function close() { pal.classList.remove("on"); if (last) last.focus(); }
    $("#jump").addEventListener("click", open);
    $("#more").addEventListener("click", open);
    inp.addEventListener("input", function () { draw(inp.value); });
    pal.addEventListener("click", function (e) { if (e.target === pal) close(); });
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
      else if (e.key === "Escape" && pal.classList.contains("on")) close();
    });
  }

  /* ---------- seat arc ---------- */
  function arc(host, opts) {
    opts = opts || {};
    var lit = opts.lit || [], W = 400, H = 214, cx = 200, cy = 200, R0 = 100, R1 = 192, rows = 7;
    var radii = [], i, j, sum = 0;
    for (i = 0; i < rows; i++) { radii.push(R0 + (R1 - R0) * i / (rows - 1)); sum += radii[i]; }
    var n = TD.seats.length, per = radii.map(function (r) { return Math.round(n * r / sum); });
    var tot = per.reduce(function (a, b) { return a + b; }, 0); per[rows - 1] += n - tot;
    var pos = [];
    for (i = 0; i < rows; i++) for (j = 0; j < per[i]; j++) {
      var th = Math.PI - (per[i] === 1 ? Math.PI / 2 : j * Math.PI / (per[i] - 1));
      pos.push({ a: th, r: radii[i], x: cx + radii[i] * Math.cos(th), y: cy - radii[i] * Math.sin(th) });
    }
    pos.sort(function (p, q) { return (q.a - p.a) || (p.r - q.r); });
    var order = []; BLOCS.forEach(function (b) { TD.seats.filter(function (s) { return s.b === b[0]; }).forEach(function (s) { order.push(s); }); });
    var rad = (R1 - R0) / (rows - 1) * .4;
    var out = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Dewan Rakyat seat map: 222 seats grouped by coalition' + (lit.length ? ", " + lit.length + " highlighted" : "") + '">';
    var litDots = "";
    order.forEach(function (s, k) {
      var p = pos[k], isLit = lit.indexOf(s.c) > -1;
      var t = "<title>" + esc(s.s + " (" + s.c + "), " + s.n + ", " + s.p) + "</title>";
      if (isLit) litDots += '<circle class="dot lit hl" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + (rad * 2.3).toFixed(1) + '" data-b="' + s.b + '">' + t + "</circle>";
      else out += '<circle class="dot" data-b="' + s.b + '" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + rad.toFixed(1) + '" fill="var(--b-' + s.b + ')">' + t + "</circle>";
    });
    out += litDots + "</svg>";
    var counts = {}; TD.seats.forEach(function (s) { counts[s.b] = (counts[s.b] || 0) + 1; });
    host.classList.add("arc"); if (opts.cols2) host.classList.add("cols2");
    host.innerHTML = '<div class="arc-wrap">' + out + '<div class="mid"><b>' + (opts.mid || "222") + "</b><span>" + (opts.midLabel || "seats") + "</span></div></div>" +
      '<ul class="legend">' + BLOCS.map(function (b) { return '<li><button type="button" data-b="' + b[0] + '"><span class="sw" style="background:var(--b-' + b[0] + ')"></span>' + b[1] + '<span class="n">' + counts[b[0]] + "</span></button></li>"; }).join("") + "</ul>" +
      '<p class="mute" style="font-size:13px">A diagram: seats are grouped by coalition, not placed as in the real chamber.</p>';
    $$(".legend button", host).forEach(function (b) {
      function on() { host.classList.add("dim"); $$(".dot", host).forEach(function (d) { d.classList.toggle("hl", d.dataset.b === b.dataset.b || d.classList.contains("lit")); }); }
      function off() { host.classList.toggle("dim", false); $$(".dot:not(.lit)", host).forEach(function (d) { d.classList.remove("hl"); }); }
      b.addEventListener("mouseenter", on); b.addEventListener("focus", on); b.addEventListener("mouseleave", off); b.addEventListener("blur", off);
    });
    if (lit.length) host.classList.add("dim");
  }

  /* ---------- count up once ---------- */
  function countUp() {
    var els = $$("[data-count]"); if (!els.length) return;
    function run(el) {
      var to = +el.dataset.count; if (reduce) return;
      var t0 = null; function f(t) { if (t0 === null) t0 = t; var p = Math.min(1, (t - t0) / 380); el.textContent = fmt(Math.round(to * (1 - Math.pow(1 - p, 3)))); if (p < 1) requestAnimationFrame(f); }
      requestAnimationFrame(f);
    }
    if (!("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); run(e.target); } }); });
    els.forEach(function (e) { io.observe(e); });
  }

  /* ---------- topic chart ---------- */
  function topicChart(host) {
    var years = []; for (var y = 2018; y <= 2026; y++) years.push(y);
    var series = TD.topics.map(function (t, i) {
      var by = {}; t.pts.forEach(function (p) { var yy = +p[0].slice(0, 4); by[yy] = (by[yy] || 0) + p[1]; });
      var total = t.pts.reduce(function (a, p) { return a + p[1]; }, 0);
      return { name: t.name, by: by, total: total, c: "var(--c" + (i + 1) + ")" };
    });
    var max = 0; series.forEach(function (s) { years.forEach(function (yy) { max = Math.max(max, s.by[yy] || 0); }); });
    max = Math.ceil(max / 1000) * 1000;
    var W = 640, H = 270, L = 44, B = 28, T = 10, R = 12;
    var x = function (k) { return L + (W - L - R) * k / (years.length - 1); };
    var yv = function (v) { return T + (H - T - B) * (1 - v / max); };
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Debates a year on the six biggest topics, 2018 to 2026">';
    for (var g = 0; g <= 4; g++) { var v = max * g / 4; svg += '<line class="grid-l" x1="' + L + '" x2="' + (W - R) + '" y1="' + yv(v) + '" y2="' + yv(v) + '"/><text class="axis" x="' + (L - 8) + '" y="' + (yv(v) + 4) + '" text-anchor="end">' + fmt(v) + "</text>"; }
    years.forEach(function (yy, k) { svg += '<text class="axis" x="' + x(k) + '" y="' + (H - 6) + '" text-anchor="middle">' + yy + "</text>"; });
    series.forEach(function (s, i) {
      var d = years.map(function (yy, k) { return (k ? "L" : "M") + x(k).toFixed(1) + " " + yv(s.by[yy] || 0).toFixed(1); }).join(" ");
      svg += '<path class="ln" data-i="' + i + '" pathLength="1" d="' + d + '" stroke="' + s.c + '"/>';
    });
    svg += "</svg>";
    host.innerHTML = '<div class="chart-wrap"><div class="chart draw" id="chart">' + svg + '</div><ul class="topic-leg">' +
      series.map(function (s, i) { return '<li><button type="button" data-i="' + i + '"><span class="sw" style="background:' + s.c + '"></span><span class="nm">' + s.name + '</span><span class="n">' + fmt(s.total) + "</span></button></li>"; }).join("") + "</ul></div>";
    var ch = $("#chart", host);
    $$(".topic-leg button", host).forEach(function (b) {
      function on() { ch.classList.add("dim"); $$(".ln", ch).forEach(function (l) { l.classList.toggle("hl", l.dataset.i === b.dataset.i); }); b.classList.add("on"); }
      function off() { ch.classList.remove("dim"); b.classList.remove("on"); }
      b.addEventListener("mouseenter", on); b.addEventListener("focus", on); b.addEventListener("mouseleave", off); b.addEventListener("blur", off);
    });
  }

  /* ---------- home: answer replay ---------- */
  var STAGE = { bm25: "Keyword search", dense: "Search by meaning", fused: "Merge the two lists", reranked: "Rerank by relevance" };
  var Q_EN = ["Can my employer cut my salary?", "What did MPs say about the Online Safety Bill?", "How many hours a week may an employee work?", "What was said about the price of rice?"];
  var Q_MS = ["Bolehkah majikan memotong gaji saya?", "Apa kata menteri tentang subsidi diesel?", "Apakah hukuman memandu dalam keadaan mabuk?", "Bilakah gaji minimum dinaikkan?"];
  var TOTAL = 427728;
  var running = null, lastFocus = null, curSrc = 0;

  function sleep(ms, fast) { return fast ? Promise.resolve() : new Promise(function (r) { setTimeout(r, ms); }); }
  function logw(n) { return Math.max(2, Math.log10(n + 1) / Math.log10(TOTAL) * 100); }

  function md(s, final) {
    if (!final) { if ((s.match(/\*\*/g) || []).length % 2) s += "**"; s = s.replace(/\[\d*$/, ""); }
    var blocks = s.split(/\n\n/), html = "";
    blocks.forEach(function (b) {
      var lines = b.split("\n");
      if (lines.every(function (l) { return /^- /.test(l) || !l; })) html += "<ul>" + lines.filter(Boolean).map(function (l) { return "<li>" + inline(l.slice(2)) + "</li>"; }).join("") + "</ul>";
      else {
        var pre = [], ul = [];
        lines.forEach(function (l) { if (/^- /.test(l)) ul.push(l.slice(2)); else pre.push(l); });
        if (pre.length) html += "<p>" + inline(pre.join(" ")) + "</p>";
        if (ul.length) html += "<ul>" + ul.map(function (l) { return "<li>" + inline(l) + "</li>"; }).join("") + "</ul>";
      }
    });
    return html;
  }
  function inline(t) {
    return esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[(\d)\]/g, '<button class="cite" type="button" data-n="$1" aria-label="Open source $1">$1</button>');
  }

  function demoAnswer(opts) {
    opts = opts || {}; var fast = opts.fast !== false && !opts.animate;
    var A = TD.answer;
    if (running) return running;
    var body = document.body, ans = $("#ans");
    body.classList.add("answering"); body.classList.toggle("no-anim", fast); ans.hidden = false;
    closeReader(true);
    var q = $("#q"); if (q && !q.value) q.value = A.question;
    $("#ans-q").textContent = A.question;
    var steps = $("#steps");
    var ids = ["bm25", "dense", "fused", "reranked"];
    steps.innerHTML = ids.map(function (id) {
      return '<li class="step" id="st-' + id + '"><span class="st">' + ico("clock") + '</span><span class="nm">' + STAGE[id] + '</span><span class="ms">waiting</span><span class="track"><i></i></span></li>';
    }).join("") + '<li class="step final" id="st-cited"><span class="st">' + ico("clock") + '</span><span class="nm">Cited in the answer</span><span class="ms">waiting</span><span class="track"><i></i></span></li>';
    $("#plist").innerHTML = ""; $("#passages").hidden = true;
    $("#answer-text").innerHTML = ""; $("#srcs").hidden = true; $("#srcs").innerHTML = "";
    $("#ans-state").innerHTML = ico("clock", "sm") + "Starting the search";
    var scale = fast ? 0 : .32;

    function mark(id, hits, ms, bar) {
      var li = $("#st-" + id); li.classList.add("done");
      $(".st", li).innerHTML = ico("check");
      $(".ms", li).innerHTML = (ms == null ? "" : fmt(ms) + " ms, ") + '<span class="hit">' + fmt(hits) + (id === "cited" ? " sources" : " kept") + "</span>";
      $(".track i", li).style.width = bar + "%";
    }
    running = (async function () {
      var st = A.stages;
      for (var i = 0; i < st.length; i++) {
        var s = st[i]; $("#ans-state").innerHTML = ico("clock", "sm") + STAGE[s.name] + "…";
        await sleep(s.ms * scale + 120, fast);
        mark(s.name, s.hits, s.ms, logw(s.hits));
      }
      var P = A.passages, cited = A.sources.map(function (x) { return x.cite; });
      $("#plist").innerHTML = P.map(function (p) {
        return '<li class="' + (cited.indexOf(p.cite) > -1 ? "cited" : "") + '"><span class="t">' + esc(p.cite) + '</span><span class="s">score ' + p.score + '</span><span class="snip">' + esc(p.text.replace(/\s+/g, " ")) + "</span></li>";
      }).join("");
      $("#passages").hidden = false;
      $("#ans-state").innerHTML = ico("clock", "sm") + "Writing the answer from the passages found…";
      await sleep(400, fast);
      var words = A.answer.split(/(\s+)/), out = "", at = $("#answer-text");
      if (fast) at.innerHTML = md(A.answer, true);
      else {
        for (var w = 0; w < words.length; w++) {
          out += words[w];
          if (w % 4 === 0 || w === words.length - 1) { at.innerHTML = md(out, false) + '<span class="caret"></span>'; await sleep(38, false); }
        }
        at.innerHTML = md(A.answer, true);
      }
      mark("cited", A.sources.length, null, logw(A.sources.length));
      $("#ans-state").innerHTML = ico("check", "sm") + "Done, " + A.sources.length + " sources cited";
      $("#srcs").innerHTML = A.sources.map(function (s, k) {
        return '<article class="tile c4"><div class="label"><span class="src-n">' + s.n + "</span>" + esc(s.meta) + '</div><h3 class="h-tile">' + esc(s.title) + '</h3><p class="mute" style="font-size:14px">' + esc(s.cite) + '</p><blockquote class="src-quote">' +
          s.quotes.map(function (qq) { return esc(qq); }).join('<br><br>') + '</blockquote><div class="src-actions"><button class="btn navy" type="button" data-open="' + k + '">' + ico("doc", "sm") + 'Open the record</button><a class="btn s2" href="' + esc(s.pdf) + '" rel="noopener">' + ico("ext", "sm") + "Official PDF</a></div></article>";
      }).join("");
      $("#srcs").hidden = false;
      var b = $("#srcs [data-open]"); // wire later via delegation
      running = null;
    })();
    var p = running; p.then(function () { running = null; });
    return p;
  }

  /* reader */
  function openReader(k) {
    var A = TD.answer, s = A.sources[k]; if (!s) return;
    curSrc = k; var p = null;
    A.passages.forEach(function (x) { if (x.cite === s.cite) p = x; });
    var text = (p ? p.text : s.quotes.join(" ")).replace(/\s*\n\s*/g, " ");
    var html = esc(text);
    s.quotes.forEach(function (q) {
      var words = q.replace(/\s+/g, " ").trim().split(" ").map(function (w) { return esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
      html = html.replace(new RegExp(words.join("\\s+")), function (m) { return "<mark>" + m + "</mark>"; });
    });
    var r = $("#reader");
    r.innerHTML = '<div class="reader-head"><div style="flex:1"><div class="label"><span class="src-n">' + s.n + "</span>" + esc(s.meta) + '</div><h2 id="reader-h" style="margin-top:10px">' + esc(s.title) + '</h2><p class="mute" style="font-size:14px">' + esc(s.cite) + '</p></div><button class="btn icon" type="button" id="r-close" aria-label="Close the record">' + ico("close") + "</button></div>" +
      '<div class="reader-body"><p class="rec-label" style="margin-bottom:10px">' + ico("doc", "sm") + 'Verbatim text. The quoted words the answer relied on are marked.</p><div class="reader-text">' + html + "</div></div>" +
      '<div class="reader-foot"><button class="btn s2" type="button" id="r-prev"' + (k === 0 ? " disabled" : "") + ">" + ico("left", "sm") + 'Previous</button><button class="btn s2" type="button" id="r-next"' + (k === A.sources.length - 1 ? " disabled" : "") + ">Next" + ico("arrow", "sm") + '</button><a class="btn s2" href="' + esc(s.pdf) + '" rel="noopener">' + ico("ext", "sm") + 'Official PDF</a><span class="grow"></span><span class="keys-note">J and K move between sources. Esc closes.</span></div>';
    lastFocus = lastFocus || document.activeElement;
    r.classList.add("on"); $("#scrim").classList.add("on"); r.setAttribute("aria-hidden", "false");
    $("#r-close").focus();
    $("#r-close").onclick = function () { closeReader(); };
    $("#r-prev").onclick = function () { openReader(k - 1); }; $("#r-next").onclick = function () { openReader(k + 1); };
  }
  function closeReader(quiet) {
    var r = $("#reader"); if (!r) return;
    r.classList.remove("on"); $("#scrim").classList.remove("on"); r.setAttribute("aria-hidden", "true");
    if (!quiet && lastFocus && lastFocus.focus) lastFocus.focus(); lastFocus = null;
  }

  function home() {
    var A = TD.answer;
    arc($("#arc"));
    topicChart($("#topic-chart"));
    $("#ex").innerHTML = Q_EN.map(function (q) { return '<button class="chip" type="button" data-q="' + esc(q) + '"><b>EN</b>' + esc(q) + "</button>"; }).join("") +
      Q_MS.map(function (q) { return '<button class="chip" type="button" data-q="' + esc(q) + '"><b>BM</b>' + esc(q) + "</button>"; }).join("");
    $("#ex").addEventListener("click", function (e) { var c = e.target.closest(".chip"); if (c) { $("#q").value = c.dataset.q; $("#q").focus(); } });
    $("#ask-form").addEventListener("submit", function (e) { e.preventDefault(); var q = $("#q").value.trim();
      $("#demo-q").hidden = !q || q === A.question; demoAnswer({ animate: true }); });
    document.addEventListener("click", function (e) {
      var c = e.target.closest(".cite"); if (c) { lastFocus = c; openReader(+c.dataset.n - 1); return; }
      var o = e.target.closest("[data-open]"); if (o) { lastFocus = o; openReader(+o.dataset.open); return; }
      if (e.target.closest("#new-q")) { document.body.classList.remove("answering"); $("#ans").hidden = true; closeReader(true); $("#q").focus(); }
      if (e.target.id === "scrim") closeReader();
    });
    document.addEventListener("keydown", function (e) {
      var r = $("#reader"); if (!r || !r.classList.contains("on")) return;
      if (e.key === "Escape") closeReader();
      else if (e.key.toLowerCase() === "j" && curSrc < TD.answer.sources.length - 1) openReader(curSrc + 1);
      else if (e.key.toLowerCase() === "k" && curSrc > 0) openReader(curSrc - 1);
    });
    window.demoAnswer = function () { return demoAnswer({ fast: true }); };
    window.demoReader = function () { return demoAnswer({ fast: true }).then(function () { openReader(0); }); };
    if (location.hash === "#answer") window.demoAnswer();
  }

  /* ---------- MP page ---------- */
  function mp() {
    arc($("#arc"), { cols2: true, lit: ["P063"], mid: "P063", midLabel: "Tambun, 15th Parliament" });
    var by = {}; TD.mp.activity.forEach(function (a) { by[a[0]] = a[1]; });
    var yrs = []; for (var y = 2018; y <= 2026; y++) yrs.push(y);
    var mons = "JFMAMJJASOND".split(""), mnames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var max = 0; TD.mp.activity.forEach(function (a) { max = Math.max(max, a[1]); });
    var lvl = function (n) { return n === 0 ? 0 : n <= 5 ? 1 : n <= 12 ? 2 : n <= 22 ? 3 : 4; };
    var h = '<span></span>' + mons.map(function (m, i) { return '<span class="mh" aria-hidden="true">' + m + "</span>"; }).join("") + "<span></span>";
    yrs.forEach(function (yy) {
      var tot = 0;
      h += '<span class="yr">' + yy + "</span>";
      for (var m = 1; m <= 12; m++) {
        var k = yy + "-" + (m < 10 ? "0" : "") + m, n = by[k] || 0; tot += n;
        h += '<span class="cell" data-l="' + lvl(n) + '" role="img" aria-label="' + mnames[m - 1] + " " + yy + ": " + n + ' debates"><span class="tip">' + mnames[m - 1] + " " + yy + ": " + n + "</span></span>";
      }
      h += '<span class="tot tnum">' + tot + "</span>";
    });
    $("#heat").innerHTML = h;
    $("#topics").innerHTML = TD.mp.topics.map(function (t) { var mx = TD.mp.topics[0].n; return '<li><span class="nm">' + t.name + '</span><span class="n">' + t.n + '</span><span class="b"><i style="width:' + (t.n / mx * 100) + '%"></i></span></li>'; }).join("");
    $("#qa").innerHTML = TD.mp.qa.slice(0, 2).map(function (q) {
      return '<article class="qa-card"><span class="ai-label">' + ico("spark", "sm") + 'Question (AI)</span><p class="q">' + esc(q.q) + '</p><p class="who">Asked by ' + esc(q.asker) + '</p><span class="ai-label">' + ico("spark", "sm") + 'Answer (AI)</span><p>' + esc(q.a) + '</p><p class="who">Answered by ' + esc(q.by) + "</p></article>";
    }).join("");
  }

  /* ---------- debate page ---------- */
  function debate() {
    var D = TD.debate, S = D.speeches;
    var lit = []; var seen = {};
    S.forEach(function (s) { var seat = TD.seats.filter(function (x) { return x.m === s.who; })[0]; if (seat && !seen[s.who]) { seen[s.who] = 1; lit.push(seat.c); } });
    arc($("#arc"), { lit: lit, mid: String(lit.length), midLabel: "MPs spoke" });
    // timeline
    var lanes = ["PH", "PN", "Chair"].filter(function (b) { return S.some(function (s) { return s.bloc === b; }); });
    var wts = S.map(function (s) { return Math.max(s.text.length, 90); }), sum = wts.reduce(function (a, b) { return a + b; }, 0) + S.length * 55;
    var x = 0, pos = S.map(function (s, i) { var l = x / sum * 100, w = wts[i] / sum * 100; x += wts[i] + 55; return { l: l, w: w }; });
    var html = lanes.map(function (b) {
      var nm = b === "Chair" ? "Chair" : b;
      return '<div class="lane"><span class="ln-name">' + nm + '</span><div class="track">' + S.map(function (s, i) {
        if (s.bloc !== b) return "";
        var right = pos[i].l > 60;
        return '<button type="button" class="tl-bar' + (right ? " right" : "") + '" data-b="' + b + '" data-seq="' + s.seq + '" style="left:' + pos[i].l.toFixed(2) + "%;width:" + pos[i].w.toFixed(2) + '%" aria-label="Speech ' + (i + 1) + ", " + esc(s.name) + ", " + s.time + ", " + s.text.length + ' characters"><span class="tip">' + (i + 1) + ". " + esc(s.name.replace(/ \[.*\]/, "")) + ", " + s.time + "</span></button>";
      }).join("") + "</div></div>";
    }).join("");
    var ticks = []; S.forEach(function (s, i) { if (!ticks.length || ticks[ticks.length - 1][0] !== s.time) ticks.push([s.time, pos[i].l]); });
    html += '<div class="tl-axis"><span></span><div class="ax">' + ticks.map(function (t) { return '<span style="left:' + t[1].toFixed(2) + '%">' + t[0] + "</span>"; }).join("") + "</div></div>";
    $("#tl").innerHTML = html;
    $("#tl").addEventListener("click", function (e) { var b = e.target.closest(".tl-bar"); if (b) goTo(b.dataset.seq); });
    function goTo(seq) {
      var el = document.getElementById("seq-" + seq); if (!el) return;
      el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }); el.focus({ preventScroll: true });
      el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
    }
    // transcript
    $("#turns").innerHTML = S.map(function (s, i) {
      return '<article class="turn ' + s.cls + '" id="seq-' + s.seq + '" data-i="' + i + '" tabindex="-1"><div class="who"><span class="sw" style="background:var(--b-' + s.bloc + ')" aria-hidden="true"></span><b>' + esc(s.name) + '</b><span class="meta">' + esc(s.party) + '</span><span class="meta tnum">' + s.time + '</span><a class="meta" href="' + esc(s.pdf) + '" rel="noopener">page ' + s.page + '</a><span class="badge-q">' + esc(s.q) + '</span><a class="anc" href="#seq-' + s.seq + '" aria-label="Link to this speech">#</a></div><div class="rec" lang="ms">' + esc(s.text) + "</div></article>";
    }).join("");
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || /input|textarea/i.test(document.activeElement.tagName)) return;
      var k = e.key.toLowerCase(); if (k !== "j" && k !== "k") return;
      var cur = document.activeElement.closest && document.activeElement.closest(".turn"), i = cur ? +cur.dataset.i : -1;
      i = k === "j" ? Math.min(S.length - 1, i + 1) : Math.max(0, i - 1); goTo(S[i].seq);
    });
    // speakers
    var by = {}, order = [];
    S.forEach(function (s) { if (!by[s.who]) { by[s.who] = { s: s, n: 0 }; order.push(s.who); } by[s.who].n++; });
    order.sort(function (a, b) { return by[b].n - by[a].n; });
    $("#speakers").innerHTML = order.map(function (w) {
      var o = by[w], s = o.s;
      return '<li><span class="sw" style="background:var(--b-' + s.bloc + ')" aria-hidden="true"></span><span class="nm">' + esc(s.name) + '</span><span class="n tnum">' + o.n + '</span><span class="sub">' + (s.seat ? esc(s.seat) + ", " : "") + esc(s.party || "Chair") + ", first at " + s.time + ", page " + s.page + "</span></li>";
    }).join("");
    $("#qa").innerHTML = D.qa.map(function (q) {
      var figs = q.figs.slice(0, 4);
      return '<article class="qa-card"><span class="ai-label">' + ico("spark", "sm") + 'Q (AI)</span><p class="q">' + esc(q.q) + '</p><p class="who">Asked by ' + esc(q.asker) + '</p><span class="ai-label">' + ico("spark", "sm") + 'A (AI)</span><p>' + esc(q.a) + '</p><p class="who">Answered by ' + esc(q.by) + '</p><ul class="figs">' +
        figs.map(function (f) { var m = f.match(/^(\S+(?: \S+)?)\s(.*)$/); return "<li><b>" + esc(m ? m[1] : f) + "</b> " + esc(m ? m[2] : "") + "</li>"; }).join("") + "</ul>" + (q.figs.length > 4 ? '<p class="more-figs">and ' + (q.figs.length - 4) + " more figures given</p>" : "") + "</article>";
    }).join("");
  }

  /* ---------- boot ---------- */
  function boot() {
    shell();
    if (PAGE === "home") home();
    if (PAGE === "mp") mp();
    if (PAGE === "debate") debate();
    countUp();
    if (location.hash && document.getElementById(location.hash.slice(1))) setTimeout(function () { document.getElementById(location.hash.slice(1)).scrollIntoView(); }, 50);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
