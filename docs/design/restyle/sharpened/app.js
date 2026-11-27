/* Tanya Dewan, Sharpened. Shell, chamber chart, funnel, answer replay, reader, small motion. */
(function () {
  "use strict";
  var D = window.DATA;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var still = (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) || navigator.webdriver;
  var fmt = function (n) { return Number(n).toLocaleString("en-US"); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };

  var IC = {
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
    book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5M9 7h6M9 11h6"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.01"/>',
    chat: '<path d="M4 5h16v11H9l-5 4z"/>',
    gov: '<path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
    cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
    dots: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    check: '<path d="M5 12l5 5 9-10"/>'
  };
  function ic(n, c) { return '<svg class="i ' + (c || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + IC[n] + "</svg>"; }
  window.__ic = ic;

  /* Theme */
  var root = document.documentElement;
  var modes = ["auto", "dark", "light"];
  function getMode() { try { var t = localStorage.getItem("theme"); return t === "dark" || t === "light" ? t : "auto"; } catch (e) { return "auto"; } }
  function applyMode(m) {
    if (m === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", m);
    var b = $("#theme-btn"); if (!b) return;
    var lab = { auto: "Theme: same as your device", dark: "Theme: dark", light: "Theme: light" }[m];
    b.setAttribute("aria-label", lab); b.title = lab;
    b.innerHTML = ic({ auto: "monitor", dark: "moon", light: "sun" }[m]);
  }

  /* Shell */
  var page = document.body.dataset.page;
  var nav = [["Ask", "home.html", "home"], ["Acts", "#", ""], ["Sittings", "debate.html", "debate"], ["Questions", "#", ""], ["Commitments", "#", ""], ["MPs", "mp.html", "mp"], ["Bills", "#", ""], ["Topics", "#", ""]];
  var logo = '<svg viewBox="0 0 64 64" aria-hidden="true"><path class="bm-o" d="M32 5 L59 32 L32 59 L22.5 49.5 L8 57 L14.5 41.5 L5 32 Z" stroke-width="3" stroke-linejoin="round"/><path class="bm-r" d="M32 19 L45 32 L32 45 L19 32 Z" fill="none" stroke-width="3"/><path d="M32 26 L38 32 L32 38 L26 32 Z" fill="#F5B800"/></svg>';
  var header = '<a class="skip" href="#main">Skip to content</a>' +
    '<div class="demo-bar">This is a demo. It plays answers recorded on 27 Nov 2026 and holds a sample of the pages. <a href="https://github.com/">Code and setup on GitHub</a></div>' +
    '<header class="site-header" id="hdr"><div class="wrap"><a class="brand" href="home.html" aria-label="Tanya Dewan">' + logo + 'Tanya Dewan</a>' +
    '<nav class="nav" aria-label="Main menu">' + nav.map(function (n) { return '<a href="' + n[1] + '"' + (n[2] === page ? ' aria-current="page"' : "") + ">" + n[0] + "</a>"; }).join("") + "</nav>" +
    '<div class="tools"><button type="button" class="jump-btn" id="jump-btn" aria-haspopup="dialog">' + ic("search", "sm") + '<span class="jt">Jump to</span><kbd class="jk">Ctrl K</kbd></button>' +
    '<button type="button" class="icon-btn" id="theme-btn"></button>' +
    '<div class="lang" role="group" aria-label="Language"><button type="button" aria-pressed="true" data-lang="en">EN</button><button type="button" aria-pressed="false" data-lang="ms">BM</button></div></div></div></header>';
  var footer = '<footer class="site-footer"><div class="wrap"><p><b>Sources.</b> Laws of Malaysia Online (Attorney General’s Chambers) and the Hansard of the Parliament of Malaysia. Acts and parliamentary debates carry no copyright (Copyright Act 1987, section 3).</p>' +
    '<p><b>AI.</b> Summaries, question matches and commitment notes are written by AI and labelled as such. Speeches and Act sections are verbatim.</p>' +
    "<p><b>Not legal advice.</b> This is general information from the published record, not legal advice.</p></div></footer>" +
    '<nav class="tabbar" aria-label="Tabs">' + [["Ask", "home.html", "home", "search"], ["Sittings", "debate.html", "debate", "cal"], ["Questions", "#", "", "chat"], ["MPs", "mp.html", "mp", "users"], ["More", "#", "", "dots"]].map(function (t) { return '<a href="' + t[1] + '"' + (t[2] === page ? ' aria-current="page"' : "") + ">" + ic(t[3]) + t[0] + "</a>"; }).join("") + "</nav>" +
    '<dialog class="jump" id="jump" aria-label="Jump to a page"><form method="dialog"><input id="jump-in" type="text" placeholder="Jump to an MP, Act, bill, topic or sitting" aria-label="Jump to" autocomplete="off"><ul id="jump-list"></ul><div class="jump-foot">Arrow keys move, Enter opens, Esc closes.</div></form></dialog><div class="tip" id="tip" role="status"></div>';
  document.body.insertAdjacentHTML("afterbegin", header);
  document.body.insertAdjacentHTML("beforeend", footer);
  applyMode(getMode());
  $("#theme-btn").addEventListener("click", function () {
    var m = modes[(modes.indexOf(getMode()) + 1) % 3];
    try { localStorage.setItem("theme", m); } catch (e) { }
    applyMode(m);
  });

  /* Header condenses */
  var hdr = $("#hdr"), tick = false;
  function onScroll() { hdr.classList.toggle("scrolled", window.scrollY > 24); tick = false; }
  window.addEventListener("scroll", function () { if (!tick) { tick = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();

  /* Jump dialog */
  var jumpItems = [["Ask", "home.html", "Page"], ["Dato’ Seri Anwar bin Ibrahim", "mp.html", "MP, P063 Tambun"], ["Waktu Pertanyaan-Pertanyaan Menteri", "debate.html", "Sitting, 4 Feb 2025"], ["Employment Act 1955", "#", "Act 265"], ["Employees’ Social Security Act 1969", "#", "Act 4"], ["Online Safety Bill 2024", "#", "Bill"], ["Budget and spending", "#", "Topic"]];
  var jump = $("#jump"), jin = $("#jump-in"), jl = $("#jump-list");
  function drawJump() { var q = jin.value.toLowerCase(); jl.innerHTML = jumpItems.filter(function (j) { return j[0].toLowerCase().indexOf(q) > -1; }).map(function (j) { return '<li><a href="' + j[1] + '">' + esc(j[0]) + "<span>" + esc(j[2]) + "</span></a></li>"; }).join(""); }
  function openJump() { if (!jump.showModal) return; jin.value = ""; drawJump(); jump.showModal(); jin.focus(); }
  $("#jump-btn").addEventListener("click", openJump);
  jin.addEventListener("input", drawJump);
  jump.addEventListener("click", function (e) { if (e.target === jump) jump.close(); });
  document.addEventListener("keydown", function (e) { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openJump(); } });

  /* Reveal and count up */
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
    es.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target; io.unobserve(el);
      if (el.classList.contains("rv")) el.classList.add("in");
      $$("[data-count]", el).concat(el.hasAttribute("data-count") ? [el] : []).forEach(countUp);
      $$("[data-draw]", el).forEach(function (p) { p.style.strokeDashoffset = 0; });
    });
  }, { threshold: 0.15 }) : null;
  function countUp(el) {
    var to = Number(el.dataset.count); if (el.dataset.done) return; el.dataset.done = 1;
    if (still || !to) { el.textContent = fmt(to); return; }
    var t0 = performance.now(), dur = 1100;
    (function step(t) { var k = Math.min(1, (t - t0) / dur); k = 1 - Math.pow(1 - k, 3); el.textContent = fmt(Math.round(to * k)); if (k < 1) requestAnimationFrame(step); })(t0);
  }
  window.__observe = function (root2) {
    $$(".rv, [data-count], [data-draw]", root2 || document).forEach(function (el) {
      if (still || !io) { el.classList.add("in"); if (el.dataset.count) countUp(el); if (el.dataset.draw !== undefined) el.style.strokeDashoffset = 0; return; }
      if (el.dataset.count) el.textContent = "0";
      io.observe(el.dataset.count || el.dataset.draw !== undefined ? (el.closest(".rv") || el) : el);
    });
  };

  /* Chamber chart: 222 seats on arcs, grouped by coalition, left to right. */
  var BLOCS = [["PH", "Pakatan Harapan"], ["BN", "Barisan Nasional"], ["GPS", "Gabungan Parti Sarawak"], ["GRS", "Gabungan Rakyat Sabah"], ["Other", "Other parties and independents"], ["PN", "Perikatan Nasional"]];
  var order = BLOCS.map(function (b) { return b[0]; });
  var seats = D.seats.slice().sort(function (a, b) { return order.indexOf(a.b) - order.indexOf(b.b) || a.c.localeCompare(b.c); });
  function chamber(svg, o) {
    var rows = o.rows, w = o.w, h = o.h, cx = w / 2, cy = h - 12;
    var radii = [], sum = 0, i, j;
    for (i = 0; i < rows; i++) { var r = o.r0 + (o.r1 - o.r0) * i / (rows - 1); radii.push(r); sum += r; }
    var counts = radii.map(function (r) { return Math.round(222 * r / sum); });
    var diff = 222 - counts.reduce(function (a, b) { return a + b; }, 0); counts[rows - 1] += diff;
    var pts = [];
    radii.forEach(function (r, k) { for (j = 0; j < counts[k]; j++) { var th = Math.PI - Math.PI * j / (counts[k] - 1); pts.push({ x: cx + r * Math.cos(th), y: cy - r * Math.sin(th), th: th, r: r }); } });
    pts.sort(function (a, b) { return b.th - a.th || a.r - b.r; });
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    var html = "";
    pts.forEach(function (p, n) {
      var s = seats[n]; p.seat = s;
      html += '<circle class="d" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + o.dot + '" data-i="' + n + '"' + (o.color ? ' style="fill:var(--' + s.b + ')"' : "") + "/>";
    });
    svg.innerHTML = html;
    var els = $$(".d", svg); pts.forEach(function (p, n) { p.el = els[n]; });
    return pts;
  }
  window.__chamber = chamber;

  var tip = $("#tip");
  function bindTip(svg, pts) {
    svg.addEventListener("pointermove", function (e) {
      var c = e.target.closest ? e.target.closest(".d") : null;
      if (!c) { tip.classList.remove("show"); return; }
      var s = pts[+c.dataset.i].seat;
      tip.innerHTML = "<b>" + esc(s.c) + " " + esc(s.s) + "</b><br>" + esc(s.n) + ", " + esc(s.p);
      tip.style.left = Math.min(window.innerWidth - 270, e.clientX + 14) + "px"; tip.style.top = e.clientY + 16 + "px"; tip.classList.add("show");
    });
    svg.addEventListener("pointerleave", function () { tip.classList.remove("show"); });
  }
  function legend(host, pts, onChange) {
    var cnt = {}; seats.forEach(function (s) { cnt[s.b] = (cnt[s.b] || 0) + 1; });
    host.innerHTML = BLOCS.map(function (b) { return '<button type="button" class="lg" aria-pressed="false" data-b="' + b[0] + '"><i style="background:var(--' + b[0] + ')"></i>' + b[1] + " <b>" + cnt[b[0]] + "</b></button>"; }).join("");
    var cur = null;
    $$(".lg", host).forEach(function (btn) {
      btn.addEventListener("click", function () {
        cur = cur === btn.dataset.b ? null : btn.dataset.b;
        $$(".lg", host).forEach(function (x) { x.setAttribute("aria-pressed", String(x.dataset.b === cur)); });
        pts.forEach(function (p) { p.el.classList.toggle("dim", !!cur && p.seat.b !== cur); });
        if (onChange) onChange(cur);
      });
    });
  }
  window.__seatTools = { bindTip: bindTip, legend: legend, BLOCS: BLOCS };

  /* Language toggle */
  var lang = "en";
  var EX = { en: ["Can my employer cut my salary?", "What did MPs say about the Online Safety Bill?", "How many hours a week may an employee work?", "What was said about the price of rice?"], ms: ["Bolehkah majikan memotong gaji saya?", "Apa kata menteri tentang subsidi diesel?", "Apakah hukuman memandu dalam keadaan mabuk?", "Bilakah gaji minimum dinaikkan?"] };
  function setLang(l) {
    lang = l;
    $$(".lang button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.lang === l)); });
    document.dispatchEvent(new CustomEvent("langchange", { detail: l }));
  }
  $$(".lang button").forEach(function (b) { b.addEventListener("click", function () { setLang(b.dataset.lang); }); });

  /* ---------------- Home: hero, funnel, answer, reader ---------------- */
  function initHome() {
    var svg = $("#arc"), hero = $("#hero");
    var pts = chamber(svg, { rows: 7, r0: 270, r1: 540, w: 1100, h: 580, dot: 8 });
    var rnd = (function (s) { return function () { s = (s * 16807) % 2147483647; return s / 2147483647; }; })(7);
    var shuf = pts.map(function (p, i) { return i; }).sort(function () { return rnd() - 0.5; });
    function light(idx, cite) {
      pts.forEach(function (p) { p.el.classList.remove("on", "cite"); p.el.style.transitionDelay = ""; });
      idx.forEach(function (i) {
        var p = pts[shuf[i]]; p.el.style.transitionDelay = still ? "0ms" : Math.round((p.x / 1100) * 450) + "ms";
        p.el.classList.add(cite ? "cite" : "on");
        if (cite) p.el.setAttribute("r", 9);
      });
      if (!cite) pts.forEach(function (p) { p.el.setAttribute("r", 8); });
    }
    function range(a, b) { var r = []; for (var i = a; i < b; i++) r.push(i); return r; }
    var LIGHT = { bm25: range(0, 79), dense: range(40, 119), fused: range(0, 100), reranked: range(0, 38), cited: range(0, 3) };

    var q = $("#q"), note = $("#ask-note"), tries = $("#tries");
    function drawTries() {
      tries.innerHTML = '<span class="k">Try</span>' + EX[lang].map(function (t, i) { return '<button type="button" class="try" data-i="' + i + '">' + esc(t) + "</button>"; }).join("");
      q.placeholder = lang === "en" ? "Ask about a law or a debate" : "Tanya tentang undang-undang atau perbahasan";
    }
    drawTries();
    document.addEventListener("langchange", drawTries);
    tries.addEventListener("click", function (e) {
      var b = e.target.closest(".try"); if (!b) return;
      q.value = EX[lang][+b.dataset.i];
      ask();
    });
    $("#ask-form").addEventListener("submit", function (e) { e.preventDefault(); ask(); });
    function ask() {
      if (q.value.trim().toLowerCase() === D.q.toLowerCase()) { play({ fast: false }); return; }
      note.textContent = "This demo replays one recorded answer: “" + D.q + "”. Pick it from the examples to see it run. The live site answers any question.";
    }

    /* funnel */
    var fn = $("#funnel");
    var COLS = [["all", "Speeches and sections", 427728], ["bm25", "Matched by keyword"], ["dense", "Matched by meaning"], ["fused", "In the merged list"], ["reranked", "Kept after reranking"], ["cited", "Cited in the answer"]];
    var MAXL = Math.log10(427728);
    function drawFunnel() {
      fn.innerHTML = COLS.map(function (c) {
        var all = c[0] === "all";
        return '<div class="fcol ' + (all ? "" : "wait") + '" data-k="' + c[0] + '"><div class="fnum">' + (all ? fmt(c[2]) : "–") + '</div><div class="fbar"><i style="width:' + (all ? 100 : 0) + '%"></i></div><div class="flab">' + c[1] + '</div><div class="fms">&nbsp;</div></div>';
      }).join("");
    }
    drawFunnel();
    function stage(k, hits, ms) {
      var col = $('[data-k="' + k + '"]', fn); if (!col) return;
      if (hits == null) { col.classList.add("go"); col.querySelector(".fnum").textContent = "…"; col.querySelector(".fms").textContent = "searching"; return; }
      col.classList.remove("go", "wait");
      col.querySelector(".fnum").textContent = fmt(hits);
      col.querySelector(".fbar i").style.width = Math.max(2, Math.log10(Math.max(hits, 1)) / MAXL * 100) + "%";
      col.querySelector(".fms").textContent = ms == null ? "" : fmt(ms) + " ms";
      if (LIGHT[k]) light(LIGHT[k], false);
    }

    /* answer rendering */
    var ans = $("#answer"), foundBox = $("#found"), atext = $("#atext"), srcBox = $("#sources");
    function md(s) {
      if ((s.match(/\*\*/g) || []).length % 2) s = s.replace(/\*\*[^*]*$/, "");
      var lines = s.split("\n"), out = "", inList = false;
      lines.forEach(function (l) {
        var li = /^- /.test(l);
        var t = esc(l.replace(/^- /, "")).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[(\d)\]/g, '<button type="button" class="cite" data-n="$1" aria-label="Open source $1">$1</button>');
        if (li && !inList) { out += "<ul>"; inList = true; }
        if (!li && inList) { out += "</ul>"; inList = false; }
        if (li) out += "<li>" + t + "</li>"; else if (l.trim()) out += "<p" + (/not legal advice/.test(l) ? ' class="legal"' : "") + ">" + t + "</p>";
      });
      if (inList) out += "</ul>"; return out;
    }
    function drawSources() {
      srcBox.innerHTML = D.done.sources.map(function (s) {
        return '<article class="src"><div class="src-top"><span class="n">' + s.n + '</span><div><div class="src-title">' + esc(s.title) + '</div><div class="src-meta">' + esc(s.cite) + " · " + esc(s.meta) + '</div></div></div>' +
          s.quotes.map(function (t) { return '<p class="quote">“' + esc(t) + "”</p>"; }).join("") +
          '<div class="src-foot"><button type="button" class="open-src" data-n="' + s.n + '">Read the whole passage ' + ic("arrow", "sm") + '</button><a href="' + esc(s.pdf) + '" rel="noopener">Official PDF ' + ic("ext", "sm") + "</a></div></article>";
      }).join("");
    }
    function resetAnswer() {
      drawFunnel(); light([], false);
      foundBox.innerHTML = ""; atext.innerHTML = ""; srcBox.innerHTML = '<p class="empty">Sources appear here when the answer is ready.</p>';
      $("#legal").hidden = true;
      svg.classList.add("run");
    }
    var busy = null;
    function play(o) {
      if (busy) return busy;
      var fast = o.fast;
      ans.hidden = false; hero.classList.add("compact"); ans.classList.toggle("instant", fast); hero.classList.toggle("instant", fast);
      note.textContent = ""; q.value = D.q;
      resetAnswer();
      if (!fast) setTimeout(function () { var y = ans.getBoundingClientRect().top + scrollY - 90; window.scrollTo({ top: Math.max(0, y - 300), behavior: "smooth" }); }, 50);
      var scale = fast ? 0 : 0.5;
      busy = (async function () {
        var prev = 0;
        for (var i = 0; i < D.events.length; i++) {
          var e = D.events[i];
          if (e.t > 6700 && e.name !== "answer") break;
          await sleep((e.t - prev) * scale); prev = e.t;
          stage(e.name === "answer" ? "x" : e.name, e.hits, e.ms);
          if (e.name === "reranked" && e.hits != null) {
            var ps = D.done.passages;
            foundBox.innerHTML = '<div class="found-h">Found before the answer</div><ul class="found">' + ps.slice(0, 5).map(function (p) { return "<li><b>" + esc(p.title) + "</b><span>" + esc(p.meta) + "</span></li>"; }).join("") + "</ul>";
          }
        }
        var words = D.done.answer.split(/(\s+)/), acc = "";
        atext.innerHTML = '<span class="caret"></span>';
        for (var k = 0; k < words.length; k++) {
          acc += words[k];
          if (!fast && /\s/.test(words[k]) === false && k % 2 === 0) { atext.innerHTML = md(acc) + '<span class="caret"></span>'; await sleep(26); }
        }
        atext.innerHTML = md(D.done.answer); $("#legal").hidden = false;
        stage("cited", D.done.sources.length, null);
        var outer = pts.filter(function (p) { return p.r > 530; }).sort(function (a, b) { return b.th - a.th; });
        light([], false); [0.36, 0.5, 0.64].forEach(function (f) { var p = outer[Math.round(f * (outer.length - 1))]; p.el.classList.add("cite"); p.el.setAttribute("r", 12); });
        drawSources();
        if (fast) await sleep(30);
      })().then(function () { busy = null; });
      return busy;
    }
    window.demoAnswer = function () { return play({ fast: true }); };
    window.demoReader = function () { return play({ fast: true }).then(function () { openReader(1); return sleep(250); }); };
    $("#run-btn").addEventListener("click", function () { q.value = D.q; play({ fast: false }); });

    /* reader */
    var rd = $("#reader"), cur = 1;
    function openReader(n) {
      var srcs = D.done.sources; cur = Math.max(1, Math.min(srcs.length, n));
      var s = srcs[cur - 1], p = D.done.passages.filter(function (x) { return x.cite === s.cite; })[0] || { text: s.quotes.join("\n\n"), header: "" };
      var html = esc(p.text);
      s.quotes.forEach(function (qt) {
        var words = qt.replace(/^\(\d+\)\s*/, "").trim().split(/\s+/).map(function (w) { return esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
        var re = new RegExp("(" + words.join("\\s+") + ")");
        html = html.replace(re, "<mark>$1</mark>");
      });
      $("#rd-title").textContent = s.title; $("#rd-meta").textContent = s.cite + " · " + s.meta;
      $("#rd-hdr").textContent = p.header || ""; $("#rd-pass").innerHTML = html.replace(/\n/g, " ");
      $("#rd-pdf").href = s.pdf; $("#rd-pos").textContent = "Source " + cur + " of " + srcs.length;
      $("#rd-prev").disabled = cur === 1; $("#rd-next").disabled = cur === srcs.length;
      if (!rd.open) rd.showModal();
      $("#rd-pass").parentNode.scrollTop = 0;
    }
    document.addEventListener("click", function (e) {
      var c = e.target.closest(".cite, .open-src"); if (c) openReader(+c.dataset.n);
    });
    $("#rd-prev").addEventListener("click", function () { openReader(cur - 1); });
    $("#rd-next").addEventListener("click", function () { openReader(cur + 1); });
    $("#rd-close").addEventListener("click", function () { rd.close(); });
    rd.addEventListener("click", function (e) { if (e.target === rd) rd.close(); });
    document.addEventListener("keydown", function (e) {
      if (!rd.open) return;
      if (e.key === "j" || e.key === "J") openReader(cur + 1); if (e.key === "k" || e.key === "K") openReader(cur - 1);
    });

    /* Seat map section */
    var msvg = $("#map"), mpts = chamber(msvg, { rows: 8, r0: 190, r1: 500, w: 1040, h: 530, dot: 9.5, color: true });
    bindTip(msvg, mpts); legend($("#legend"), mpts);
    var mf = $("#mapfind"), mo = $("#mapout");
    mf.addEventListener("input", function () {
      var v = mf.value.trim().toLowerCase(), hit = [];
      mpts.forEach(function (p) { var m = v.length > 1 && (p.seat.s.toLowerCase().indexOf(v) > -1 || p.seat.n.toLowerCase().indexOf(v) > -1 || p.seat.c.toLowerCase() === v); p.el.classList.toggle("lit", m); p.el.classList.toggle("dim", v.length > 1 && !m); if (m) hit.push(p.seat); });
      mo.textContent = v.length < 2 ? "" : hit.length ? hit.length + (hit.length === 1 ? " match: " : " matches: ") + hit.slice(0, 3).map(function (s) { return s.c + " " + s.s + ", " + s.n; }).join(" | ") : "No match.";
    });

    /* Topics */
    $("#tgrid").innerHTML = D.topics.map(function (t) {
      var ys = Object.keys(t.years).sort(), vals = ys.map(function (y) { return t.years[y]; }), mx = Math.max.apply(null, vals);
      var W = 300, H = 90, pts2 = vals.map(function (v, i) { return [i * (W / (vals.length - 1)), H - 6 - (v / mx) * (H - 14)]; });
      var d = pts2.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
      return '<article class="card tc lift rv"><div class="tn">' + esc(t.name.charAt(0).toUpperCase() + t.name.slice(1)) + '</div><div class="tv" data-count="' + t.sum + '">' + fmt(t.sum) + '</div><div class="ts">debates, 2018 to 2026</div>' +
        '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Debates a year on ' + esc(t.name) + ', 2018 to 2026" data-t="' + esc(JSON.stringify([ys, vals])) + '"><path class="ar" d="' + d + " L" + W + " " + H + " L0 " + H + 'z"/><path class="ln" d="' + d + '" pathLength="1" data-draw style="stroke-dasharray:1;stroke-dashoffset:' + (still ? 0 : 1) + ';transition:stroke-dashoffset 1.2s var(--ease)"/></svg><div class="ro">Move over the chart to read a year.</div></article>';
    }).join("");
    $$("#tgrid .tc").forEach(function (c) {
      var s = c.querySelector("svg"), ro = c.querySelector(".ro"), dd = JSON.parse(s.dataset.t);
      function at(e) { var r = s.getBoundingClientRect(), k = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), i = Math.round(k * (dd[0].length - 1)); ro.textContent = dd[0][i] + ": " + fmt(dd[1][i]) + " debates"; }
      s.addEventListener("pointermove", at);
    });
    window.__observe();
  }

  /* ---------------- MP page ---------------- */
  function initMp() {
    var g = D.mp.grid, years = []; for (var y = 2018; y <= 2026; y++) years.push(y);
    var h = '<div></div>' + "JFMAMJJASOND".split("").map(function (m) { return '<div class="mh" aria-hidden="true">' + m + "</div>"; }).join("") + '<div class="tot">Total</div>';
    years.forEach(function (yy) {
      var tot = 0, cells = "";
      for (var m = 1; m <= 12; m++) { var k = yy + "-" + (m < 10 ? "0" : "") + m, v = g[k] || 0; tot += v; cells += '<div class="c" data-l="' + (v === 0 ? 0 : v < 5 ? 1 : v < 12 ? 2 : v < 22 ? 3 : 4) + '" title="' + k + ": " + v + '" role="img" aria-label="' + k + ": " + v + '"></div>'; }
      h += '<div class="yr">' + yy + "</div>" + cells + '<div class="tot">' + tot + "</div>";
    });
    $("#heat").innerHTML = h;
    var svg = $("#map"), pts = chamber(svg, { rows: 8, r0: 190, r1: 500, w: 1040, h: 530, dot: 9.5, color: true });
    bindTip(svg, pts);
    var lit = (svg.dataset.lit || "").split("|");
    pts.forEach(function (p) { var on = lit.indexOf(p.seat.s) > -1; p.el.classList.toggle("dim", !on); p.el.classList.toggle("lit", on); if (on) { p.el.setAttribute("r", 14); p.el.parentNode.appendChild(p.el); } });
    legend($("#legend"), pts);
    window.__observe();
  }

  /* ---------------- Debate page ---------------- */
  function initDebate() {
    var C = { PH: "var(--PH)", PN: "var(--PN)", Chair: "var(--Other)" };
    $("#lanes").innerHTML = D.lanes.map(function (l) {
      return '<div class="lane"><span class="ln">' + l.lane + '</span><div class="track">' + l.bars.map(function (b) {
        return '<a href="#seq-' + b.seq + '" style="left:' + b.left + "%;width:" + b.w + "%;--c:" + C[l.lane] + '" title="' + esc(b.title) + '" aria-label="' + esc(b.title) + '"></a>';
      }).join("") + "</div></div>";
    }).join("");
    $("#turns").innerHTML = D.turns.map(function (t) {
      var name = t.who, link = /Kiandee/.test(name) ? "#" : /Anwar/.test(name) ? "mp.html" : null;
      return '<article class="turn ' + t.cls + '" id="seq-' + t.seq + '" tabindex="-1"><span class="av" aria-hidden="true">' + esc(t.av) + '</span><div><div class="who"><b>' + (link ? '<a href="' + link + '">' + esc(name) + "</a>" : esc(name)) + "</b>" + (t.party ? '<span class="party">' + esc(t.party) + "</span>" : "") + '<span class="tm tnum"><span>' + esc(t.time) + "</span>" + (t.pdf ? '<a href="' + esc(t.pdf) + '" rel="noopener">' + esc(t.page) + "</a>" : "") + '</span></div><div class="rec" lang="ms">' + esc(t.text) + "</div></div></article>";
    }).join("");
    var svg = $("#map"), pts = chamber(svg, { rows: 8, r0: 190, r1: 500, w: 1040, h: 530, dot: 9.5, color: true });
    bindTip(svg, pts);
    var lit = svg.dataset.lit.split("|");
    pts.forEach(function (p) { var on = lit.indexOf(p.seat.s) > -1; p.el.classList.toggle("dim", !on); p.el.classList.toggle("lit", on); if (on) { p.el.setAttribute("r", 13); p.el.parentNode.appendChild(p.el); } });
    legend($("#legend"), pts);
    function hl() { $$(".turn.hl").forEach(function (x) { x.classList.remove("hl"); }); var t = location.hash && $(location.hash); if (t && t.classList.contains("turn")) t.classList.add("hl"); }
    window.addEventListener("hashchange", hl); hl();
    var turns = $$(".turn"), idx = -1;
    document.addEventListener("keydown", function (e) {
      if (e.target.matches("input, textarea") || e.ctrlKey || e.metaKey) return;
      if (e.key === "j") idx = Math.min(turns.length - 1, idx + 1); else if (e.key === "k") idx = Math.max(0, idx - 1); else return;
      turns[idx].scrollIntoView({ block: "center" }); turns[idx].focus({ preventScroll: true });
    });
    window.__observe();
  }

  if (page === "home") initHome(); else if (page === "mp") initMp(); else if (page === "debate") initDebate();
})();
