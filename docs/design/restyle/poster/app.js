/* Tanya Dewan, Poster look. Vanilla JS: theme, jump box, one-time draws, seat finder, answer replay, source reader. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- theme ---- */
  function effective() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  try { var saved = localStorage.getItem("td-poster-theme"); if (saved) root.setAttribute("data-theme", saved); } catch (e) { /* storage is a convenience */ }
  var tb = $("#theme-btn");
  if (tb) tb.addEventListener("click", function () {
    var next = effective() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("td-poster-theme", next); } catch (e) { /* ignore */ }
  });
  $$(".lang").forEach(function (g) {
    g.addEventListener("click", function (ev) {
      var b = ev.target.closest("button"); if (!b) return;
      $$("button", g).forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    });
  });

  /* ---- jump box ---- */
  var dlg = $("#jump"), jin = $("#jump-in"), opener = null;
  function openJump() {
    if (!dlg) return;
    opener = document.activeElement;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    jin.value = ""; filterJump(); jin.focus();
  }
  function filterJump() {
    var q = jin.value.trim().toLowerCase();
    $$("#jump-list li").forEach(function (li) { li.hidden = q && li.textContent.toLowerCase().indexOf(q) < 0; });
  }
  if (dlg) {
    ["#jump-btn", "#more-btn", "#keys-link"].forEach(function (s) { var b = $(s); if (b) b.addEventListener("click", function (e) { e.preventDefault(); openJump(); }); });
    jin.addEventListener("input", filterJump);
    $("#jump-x").addEventListener("click", function () { dlg.close(); });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("close", function () { if (opener && opener.focus) opener.focus(); });
  }
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openJump(); }
  });

  /* ---- one-time draws and count-ups ---- */
  function fmt(n) { return n.toLocaleString("en-US"); }
  function countUp(el) {
    var to = parseInt(el.getAttribute("data-to"), 10); if (!to || reduce) return;
    var t0 = null, dur = 900;
    function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / dur), v = Math.round(to * (1 - Math.pow(1 - p, 3)));
      el.textContent = fmt(v);
      if (p < 1) requestAnimationFrame(step);
    }
    el.textContent = "0"; requestAnimationFrame(step);
  }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        if (en.target.classList.contains("count")) countUp(en.target); else en.target.classList.add("run");
      });
    }, { threshold: 0.25 });
    $$(".count, .draw").forEach(function (el) { io.observe(el); });
  }

  /* ---- seat finder ---- */
  var find = $("#seat-find");
  if (find) find.addEventListener("input", function () {
    var q = find.value.trim().toLowerCase(), out = $("#seat-out"), map = $(".sm");
    $$(".seat.on", map).forEach(function (s) { s.classList.remove("on"); });
    map.classList.remove("has-lit"); out.textContent = "";
    if (q.length < 3) return;
    var hit = $$(".seat", map).filter(function (s) {
      return s.getAttribute("data-seat").toLowerCase() === q || s.getAttribute("data-code").toLowerCase() === q ||
        s.getAttribute("data-name").toLowerCase().indexOf(q) >= 0 || s.getAttribute("data-seat").toLowerCase().indexOf(q) === 0;
    })[0];
    if (!hit) { out.textContent = "No seat matches."; return; }
    hit.classList.add("on"); map.classList.add("has-lit");
    out.textContent = hit.getAttribute("data-code") + " " + hit.getAttribute("data-seat") + ", " + hit.getAttribute("data-name") + ", " + hit.getAttribute("data-party");
  });

  /* ---- debate page: timeline to speech, J and K ---- */
  var turns = $$(".turn");
  if (turns.length) {
    $$("#tl .track a").forEach(function (a) {
      var t = document.getElementById("t" + a.getAttribute("data-i"));
      a.addEventListener("mouseenter", function () { t.classList.add("hot"); });
      a.addEventListener("mouseleave", function () { t.classList.remove("hot"); });
      a.addEventListener("focus", function () { t.classList.add("hot"); });
      a.addEventListener("blur", function () { t.classList.remove("hot"); });
    });
    var cur = -1;
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || (dlg && dlg.open)) return;
      var k = e.key.toLowerCase();
      if (k !== "j" && k !== "k") return;
      cur = Math.max(0, Math.min(turns.length - 1, cur + (k === "j" ? 1 : -1)));
      turns[cur].scrollIntoView({ block: "start" });
      turns[cur].setAttribute("tabindex", "-1"); turns[cur].focus({ preventScroll: true });
    });
  }

  /* ---- ask and answer ---- */
  var form = $("#ask-form");
  if (!form || !window.DATA) return;
  var A = window.DATA.answer;
  var qbox = $("#q"), secAns = $("#answer"), reader = $("#reader"), scrim = $("#scrim");
  var token = 0, openSrc = 0;

  $$(".eg button").forEach(function (b) {
    b.addEventListener("click", function () { qbox.value = b.getAttribute("data-q"); qbox.focus(); });
  });
  var note = document.createElement("p");
  note.className = "err"; note.hidden = true; note.setAttribute("role", "status");
  form.insertAdjacentElement("afterend", note);

  var STEPS = [
    { key: "corpus", name: "All passages held", n: 427728, sub: "speeches and Act sections" },
    { key: "bm25", name: "By keyword", n: null },
    { key: "dense", name: "By meaning", n: null },
    { key: "fused", name: "Merged", n: null },
    { key: "reranked", name: "Kept after ranking", n: null },
    { key: "cited", name: "Cited in the answer", n: null }
  ];
  var stageBy = {};
  A.stages.forEach(function (s) { stageBy[s.name] = s; });
  STEPS[1].n = stageBy.bm25.hits; STEPS[2].n = stageBy.dense.hits; STEPS[3].n = stageBy.fused.hits;
  STEPS[4].n = stageBy.reranked.hits; STEPS[5].n = A.sources.length;
  var MAXN = STEPS[0].n;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function buildFunnel(quick) {
    var ol = $("#funnel"); ol.innerHTML = "";
    STEPS.forEach(function (s, i) {
      var li = document.createElement("li");
      li.className = "wait" + (i === STEPS.length - 1 ? " last" : "");
      var w = Math.max(3, Math.log(s.n + 1) / Math.log(MAXN + 1) * 100);
      li.innerHTML = '<span class="f-name">' + esc(s.name) + '<span class="f-ms" data-ms></span></span><b class="f-n tnum" data-n>' + fmt(s.n) + '</b><div class="f-bar"><i style="--w:' + w.toFixed(1) + '%"></i></div>';
      if (quick) li.querySelector("i").style.transitionDuration = ".2s";
      ol.appendChild(li);
    });
    return $$("li", ol);
  }
  function showStep(li, i, animate) {
    li.classList.remove("wait", "run");
    var ms = i > 0 && i < 5 ? stageBy[STEPS[i].key].ms : null;
    if (ms !== null && ms !== undefined) $("[data-ms]", li).textContent = fmt(ms) + " ms";
    var nEl = $("[data-n]", li);
    if (animate && !reduce) {
      var to = STEPS[i].n, t0 = null;
      (function step(t) { if (t0 === null) t0 = t; var p = Math.min(1, (t - t0) / 450); nEl.textContent = fmt(Math.round(to * p)); if (p < 1) requestAnimationFrame(step); })(performance.now());
    }
  }
  function buildFound() {
    var box = $("#found"); box.hidden = false;
    $("#found-list").innerHTML = A.passages.map(function (p, i) {
      return '<li style="animation-delay:' + (i * 30) + 'ms"><span class="pn tnum">' + (i + 1) + '</span><div><div class="pt">' + esc(p.title) + '</div><div class="pc">' + esc(p.cite) + '</div></div></li>';
    }).join("");
  }
  function inline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\[(\d)\]/g, '<button type="button" class="cite" data-n="$1" aria-label="Open source $1">$1</button>');
  }
  function answerDom() {
    var lines = A.text.split("\n").filter(function (l) { return l.trim(); }), html = "", inList = false;
    lines.forEach(function (l) {
      if (/^- /.test(l)) { if (!inList) { html += "<ul>"; inList = true; } html += "<li>" + inline(l.slice(2)) + "</li>"; }
      else { if (inList) { html += "</ul>"; inList = false; } html += "<p>" + inline(l) + "</p>"; }
    });
    if (inList) html += "</ul>";
    var box = $("#answer-text"); box.innerHTML = html;
    return box;
  }
  function units(box) {
    var us = [], w = document.createTreeWalker(box, NodeFilter.SHOW_ALL, null);
    var n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) { (n.nodeValue.match(/\S+\s*/g) || [n.nodeValue]).forEach(function (c) { us.push({ node: n, chunk: c }); }); }
      else if (n.nodeType === 1 && n.classList.contains("cite")) us.push({ el: n });
    }
    return us;
  }
  function finishAnswer() {
    $("#ai-note").hidden = false; $("#legal").hidden = false;
    var sg = $("#sources"); sg.hidden = false;
    $("#src-grid").innerHTML = A.sources.map(function (s, i) {
      return '<article class="src" style="animation-delay:' + (i * 70) + 'ms"><div class="num">' + s.n + '</div><div class="sb"><h4>' + esc(s.title) + '</h4><p class="sc">' + esc(s.cite) + ' · ' + esc(s.meta) + '</p><blockquote>' + esc('“' + s.quotes[0] + '”') + '</blockquote><div class="acts"><button type="button" class="btn" data-open="' + s.n + '">Read the passage</button><a class="btn alt" href="' + esc(s.pdf) + '" rel="noopener">Official PDF</a></div></div></article>';
    }).join("");
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function run(opts) {
    var quick = !!(opts && opts.quick), my = ++token;
    var q = A.question;
    note.hidden = true; closeReader(true);
    secAns.hidden = false; $("#ans-question").textContent = q;
    $("#found").hidden = true; $("#sources").hidden = true; $("#ai-note").hidden = true; $("#legal").hidden = true;
    $("#answer-text").innerHTML = '<p class="caret">Searching the record</p>';
    var rows = buildFunnel(quick);
    secAns.scrollIntoView({ block: "start" });
    var scale = quick ? 0 : 0.32;
    function at(t) { return quick ? Promise.resolve() : sleep(t * scale); }
    return (async function () {
      // corpus
      requestAnimationFrame(function () { showStep(rows[0], 0, !quick); });
      var seq = [["bm25", 1], ["dense", 2], ["fused", 3], ["reranked", 4]], prev = 0;
      for (var k = 0; k < seq.length; k++) {
        var st = A.stages.filter(function (s) { return s.name === seq[k][0]; })[0];
        if (!quick) { rows[seq[k][1]].classList.remove("wait"); rows[seq[k][1]].classList.add("run"); await sleep((st.t - prev) * scale); if (my !== token) return; }
        prev = st.t; showStep(rows[seq[k][1]], seq[k][1], !quick);
      }
      buildFound();
      var box = answerDom(), us = units(box);
      if (quick) { finishAnswer(); showStep(rows[5], 5, false); await new Promise(function (r) { requestAnimationFrame(function () { requestAnimationFrame(r); }); }); return; }
      var lis = $$("li", box), orig = us.map(function (u) { return u.chunk; });
      us.forEach(function (u) { if (u.node) u.node.nodeValue = ""; else u.el.style.display = "none"; });
      lis.forEach(function (li) { li.style.display = "none"; });
      var acc = new Map();
      for (var i = 0; i < us.length; i++) {
        var u = us[i];
        if (u.node) { acc.set(u.node, (acc.get(u.node) || "") + u.chunk); u.node.nodeValue = acc.get(u.node); } else u.el.style.display = "";
        var li = (u.node || u.el).parentElement && (u.node || u.el).parentElement.closest("li"); if (li) li.style.display = "";
        box.classList.add("caret-on");
        if (i % 2 === 0) await sleep(26);
        if (my !== token) return;
      }
      finishAnswer(); showStep(rows[5], 5, true);
    })();
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = qbox.value.trim().toLowerCase();
    if (q && q.replace(/\?$/, "") !== A.question.toLowerCase().replace(/\?$/, "")) {
      note.textContent = "This demo holds one recorded answer, for “" + A.question + "”. Choose it from the examples to see it play.";
      note.hidden = false; return;
    }
    qbox.value = A.question; run({});
  });
  window.demoAnswer = function () { qbox.value = A.question; return run({ quick: true }); };
  window.demoReader = function () { return window.demoAnswer().then(function () { openReader(1); }); };
  $("#copy-link").addEventListener("click", function () {
    var b = this; try { navigator.clipboard.writeText(location.href.split("#")[0] + "?q=" + encodeURIComponent(A.question)); } catch (e) { /* no clipboard */ }
    b.lastChild.textContent = "Copied";
    setTimeout(function () { b.lastChild.textContent = "Copy link"; }, 1500);
  });

  /* ---- source reader ---- */
  function passageFor(s) { return A.passages.filter(function (p) { return p.cite === s.cite; })[0]; }
  function renderPassage(p, s) {
    var t = p.text.replace(/\s+/g, " ").trim(), marks = [];
    s.quotes.forEach(function (q) {
      var qn = q.replace(/\s+/g, " ").trim(), i = t.indexOf(qn);
      if (i < 0) { qn = qn.replace(/^\(\d+\)\s*/, ""); i = t.indexOf(qn); }
      if (i >= 0) marks.push([i, i + qn.length]);
    });
    marks.sort(function (a, b) { return b[0] - a[0]; });
    marks.forEach(function (m) { t = t.slice(0, m[0]) + "\u0001" + t.slice(m[0], m[1]) + "\u0002" + t.slice(m[1]); });
    var h = esc(t).replace(/\u0001/g, "<mark>").replace(/\u0002/g, "</mark>");
    h = h.replace(/ (?=\((?:\d+|[a-z])\) )/g, "\n");
    return h.split("\n").map(function (x) { return "<p>" + x + "</p>"; }).join("");
  }
  function openReader(n) {
    var s = A.sources[n - 1], p = passageFor(s); if (!s || !p) return;
    openSrc = n;
    $("#rd-count").textContent = "Source " + n + " of " + A.sources.length;
    $("#rd-num").textContent = n; $("#rd-title").textContent = s.title;
    $("#rd-meta").textContent = s.cite + " · " + s.meta; $("#rd-hdr").textContent = p.header;
    $("#rd-text").innerHTML = renderPassage(p, s);
    $("#rd-pdf").href = s.pdf;
    $("#rd-prev").disabled = n === 1; $("#rd-next").disabled = n === A.sources.length;
    $("#rd-body").scrollTop = 0;
    if (!reader.classList.contains("open")) { opener = document.activeElement; }
    reader.classList.add("open"); scrim.classList.add("open"); reader.setAttribute("aria-hidden", "false");
    $("#rd-x").focus({ preventScroll: true });
  }
  function closeReader(silent) {
    if (!reader.classList.contains("open")) return;
    reader.classList.remove("open"); scrim.classList.remove("open"); reader.setAttribute("aria-hidden", "true"); openSrc = 0;
    if (!silent && opener && opener.focus) opener.focus();
  }
  document.addEventListener("click", function (e) {
    var c = e.target.closest(".cite, [data-open]");
    if (c) { e.preventDefault(); openReader(parseInt(c.getAttribute("data-n") || c.getAttribute("data-open"), 10)); }
  });
  $("#rd-x").addEventListener("click", function () { closeReader(); });
  scrim.addEventListener("click", function () { closeReader(); });
  $("#rd-prev").addEventListener("click", function () { if (openSrc > 1) openReader(openSrc - 1); });
  $("#rd-next").addEventListener("click", function () { if (openSrc < A.sources.length) openReader(openSrc + 1); });
  document.addEventListener("keydown", function (e) {
    if (!openSrc) return;
    if (e.key === "Escape") { closeReader(); return; }
    if (e.key.toLowerCase() === "j" && openSrc < A.sources.length) openReader(openSrc + 1);
    if (e.key.toLowerCase() === "k" && openSrc > 1) openReader(openSrc - 1);
    if (e.key === "Tab") {
      var f = $$("button:not([disabled]), a[href]", reader), first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
})();
