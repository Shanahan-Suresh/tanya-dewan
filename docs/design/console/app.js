/* Console direction: shared behaviour (theme, menu, command palette) and page scripts. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var isHome = !!$("#q");

  /* theme */
  var root = document.documentElement;
  try { var saved = localStorage.getItem("console-theme"); if (saved) root.setAttribute("data-theme", saved); } catch (e) {}
  var tbtn = $("#theme");
  if (tbtn) tbtn.addEventListener("click", function () {
    var dark = root.getAttribute("data-theme") ? root.getAttribute("data-theme") === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("console-theme", next); } catch (e) {}
  });

  /* menu */
  var mb = $("#menu"), nav = $("#nav");
  if (mb) mb.addEventListener("click", function () {
    var o = nav.classList.toggle("open");
    mb.setAttribute("aria-expanded", o ? "true" : "false");
  });

  /* ------------------------------------------------------------ home */
  var home = { run: function (q) { location.href = "home.html#demo"; }, addToken: function (k, v) { location.href = "home.html#f=" + k + ":" + v; } };
  var EXAMPLES = [
    ["EN", "What has the government said about targeted diesel subsidies?"],
    ["BM", "Apakah kenyataan kerajaan mengenai subsidi diesel bersasar?"],
    ["EN", "Which ministers promised new clinics in Sabah, and by when?"],
    ["BM", "Siapa yang berjanji menaik taraf jalan Persekutuan di Seremban?"]
  ];
  var KEYS = ["party", "topic", "speaker", "act", "chamber", "from", "to", "parliament"];

  if (isHome && window.DEMO) {
    var D = window.DEMO;
    var q = $("#q"), toks = $("#tokens"), form = $("#askform");
    var result = $("#result"), ansBody = $("#ansbody"), srcList = $("#srclist");
    var running = null;

    var esc = function (s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
    var inline = function (s) {
      s = esc(s);
      var n = (s.match(/\*\*/g) || []).length; if (n % 2) s += "**";
      s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      return s.replace(/\[(\d+)\]/g, '<a class="cite" href="#src-$1" data-n="$1" aria-label="Source $1">[$1]</a>');
    };
    var md = function (txt) {
      var out = "", list = false;
      txt.split("\n").forEach(function (ln) {
        if (/^\s*-\s+/.test(ln)) { if (!list) { out += "<ul>"; list = true; } out += "<li>" + inline(ln.replace(/^\s*-\s+/, "")) + "</li>"; }
        else {
          if (list) { out += "</ul>"; list = false; }
          if (ln.trim()) out += /^This is general information/.test(ln) ? '<p class="legal">' + inline(ln) + "</p>" : "<p>" + inline(ln) + "</p>";
        }
      });
      if (list) out += "</ul>";
      return out;
    };
    var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
    var fmtMs = function (ms) { return ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : ms + " ms"; };

    var icon = function (name) { return $("#ic-" + name).innerHTML; };

    function sourceCard(s, i, fast) {
      var quotes = s.quotes.map(function (t) { return "<blockquote lang=\"ms\">" + esc(t) + "</blockquote>"; }).join("");
      var d = s.draft ? '<span class="draft"><svg class="i" viewBox="0 0 24 24">' + icon("draft") + "</svg>Unrevised draft</span>" : "";
      return '<article class="sc" id="src-' + s.n + '" data-n="' + s.n + '" tabindex="-1" style="animation-delay:' + ((fast ? 0 : i * 70)) + 'ms">' +
        '<div class="h"><span class="n">' + s.n + '</span><span class="cl">' + esc(s.cite) + "</span>" + d + "</div>" + quotes +
        '<div class="lk"><a class="tl" href="debate.html">Open in the debate<svg class="i" viewBox="0 0 24 24">' + icon("arrow") + '</svg></a>' +
        '<a class="tl" href="' + s.pdf + '" rel="noopener">Official PDF<svg class="i" viewBox="0 0 24 24">' + icon("ext") + "</svg></a></div></article>";
    }

    function setStages(upTo) {
      $$(".stg").forEach(function (el, i) { el.classList.toggle("wait", i > upTo); });
    }

    function run(fast) {
      if (running) return running;
      running = (async function () {
        result.hidden = false;
        $("#qtitle").textContent = D.question;
        if (!q.value) q.value = D.question;
        ansBody.innerHTML = "";
        ansBody.classList.remove("done");
        srcList.innerHTML = '<div class="sk">Retrieving sources</div>';
        $("#srcmeta").textContent = "waiting";
        $("#ansmeta").textContent = "searching";
        setStages(-1);
        result.scrollIntoView({ behavior: fast ? "auto" : "smooth", block: "start" });
        for (var s = 0; s < 5; s++) { await wait(fast ? 0 : 420); setStages(s); }
        $("#ansmeta").textContent = "writing";
        var words = D.answer.match(/\S+\s*/g), buf = "";
        for (var i = 0; i < words.length; i++) {
          buf += words[i];
          ansBody.innerHTML = md(buf) + '<span class="stream-cursor" aria-hidden="true"></span>';
          if (i % (fast ? 3 : 1) === 0) await wait(fast ? 3 : 34);
        }
        ansBody.innerHTML = md(buf);
        ansBody.classList.add("done");
        $("#ansmeta").textContent = D.sources.length + " sources";
        srcList.innerHTML = D.sources.map(function (s, i) { return sourceCard(s, i, fast); }).join("");
        $("#srcmeta").textContent = D.sources.length + " cited";
        return true;
      })();
      running.then(function () { running = null; }, function () { running = null; });
      return running;
    }
    window.demoAnswer = function () { return run(true); };
    home.run = function () { return run(false); };

    /* hover and focus link between marks and sources */
    function hl(n, on) { $$('[data-n="' + n + '"]').forEach(function (el) { el.classList.toggle("hl", on); }); }
    document.addEventListener("mouseover", function (e) { var t = e.target.closest(".cite,.sc"); if (t) hl(t.dataset.n, true); });
    document.addEventListener("mouseout", function (e) { var t = e.target.closest(".cite,.sc"); if (t) hl(t.dataset.n, false); });
    document.addEventListener("focusin", function (e) { var t = e.target.closest(".cite,.sc"); if (t) hl(t.dataset.n, true); });
    document.addEventListener("focusout", function (e) { var t = e.target.closest(".cite,.sc"); if (t) hl(t.dataset.n, false); });
    document.addEventListener("click", function (e) {
      var c = e.target.closest(".cite"); if (!c) return;
      e.preventDefault();
      var card = $("#src-" + c.dataset.n);
      if (card) { card.scrollIntoView({ block: "nearest", behavior: "smooth" }); card.focus({ preventScroll: true }); }
    });

    /* filter tokens */
    function addToken(k, v) {
      if (!k || !v) return;
      var el = document.createElement("span");
      el.className = "tok"; el.dataset.k = k;
      el.innerHTML = "<b>" + esc(k) + ":</b>" + esc(v) + '<button type="button" aria-label="Remove filter ' + esc(k) + " " + esc(v) + '"><svg class="i" viewBox="0 0 24 24">' + icon("x") + "</svg></button>";
      el.querySelector("button").addEventListener("click", function () { el.remove(); q.focus(); });
      toks.appendChild(el);
    }
    home.addToken = addToken;
    function eatToken() {
      var m = q.value.match(/(^|\s)(\w+):(\S+)\s$/);
      if (m && KEYS.indexOf(m[2].toLowerCase()) > -1) { addToken(m[2].toLowerCase(), m[3]); q.value = q.value.slice(0, m.index).trim(); if (q.value) q.value += " "; return true; }
      return false;
    }
    q.addEventListener("input", eatToken);
    q.addEventListener("keydown", function (e) {
      if (e.key === "Backspace" && !q.value && toks.lastElementChild) toks.lastElementChild.remove();
      if (e.key === "Enter") { q.value += " "; eatToken(); q.value = q.value.replace(/\s+$/, ""); }
    });
    form.addEventListener("submit", function (e) { e.preventDefault(); home.run(); });

    var fp = $("#fpanel"), fb = $("#fbtn");
    fb.addEventListener("click", function () { var o = fp.classList.toggle("open"); fb.setAttribute("aria-expanded", o ? "true" : "false"); });
    $("#fapply").addEventListener("click", function () {
      $$("[data-f]", fp).forEach(function (f) { if (f.value) { addToken(f.dataset.f, f.value); f.value = ""; } });
      fp.classList.remove("open"); fb.setAttribute("aria-expanded", "false");
    });
    $("#fclear").addEventListener("click", function () { $$(".tok", toks).forEach(function (t) { t.remove(); }); });
    $$(".ex button").forEach(function (b) {
      b.addEventListener("click", function () { q.value = b.dataset.q; home.run(); });
    });
    var h = location.hash;
    if (h === "#demo") setTimeout(function () { home.run(); }, 200);
    if (h.indexOf("#f=") === 0) { var kv = h.slice(3).split(":"); addToken(kv[0], kv.slice(1).join(":")); }
  }

  /* ------------------------------------------------------------ palette */
  var pal = document.createElement("dialog");
  pal.className = "pal"; pal.setAttribute("aria-label", "Command palette");
  pal.innerHTML = '<form method="dialog" onsubmit="return false"><svg class="i" viewBox="0 0 24 24" style="width:20px;height:20px;color:var(--muted)"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>' +
    '<label class="sr" for="pq">Search commands, questions and filters</label><input id="pq" type="text" autocomplete="off" placeholder="Ask a question, add a filter, or jump to a page">' +
    '<kbd>Esc</kbd></form><ul id="pl" role="listbox"></ul><div class="ft"><span><kbd>Up</kbd> <kbd>Down</kbd> move</span><span><kbd>Enter</kbd> choose</span><span>Type <kbd>party:DAP</kbd> to add a filter</span></div>';
  document.body.appendChild(pal);
  var pq = $("#pq", pal), pl = $("#pl", pal), sel = 0, shown = [];
  var PAGES = [["Ask", "home.html#ask"], ["Acts", "home.html#ask"], ["Sittings", "debate.html"], ["Questions", "mp.html#answers"], ["Commitments", "mp.html#commitments"], ["MPs", "mp.html"], ["Bills", "debate.html#bill"], ["Topics", "home.html#topics"]];
  var FILTERS = [["party", "DAP"], ["party", "AMANAH"], ["party", "UMNO"], ["topic", "health"], ["topic", "education"], ["parliament", "15"], ["parliament", "14"], ["chamber", "KK"]];
  function items(term) {
    var t = term.toLowerCase(), out = [], m = term.match(/^(\w+):(\S+)$/);
    if (m && KEYS.indexOf(m[1].toLowerCase()) > -1) out.push({ g: "Filter", l: "Add filter " + m[1].toLowerCase() + ":" + m[2], k: "filter", f: function () { home.addToken(m[1].toLowerCase(), m[2]); } });
    EXAMPLES.forEach(function (e) { if (!t || e[1].toLowerCase().indexOf(t) > -1) out.push({ g: "Ask", l: e[1], k: e[0], f: function () { if (q0()) { q0().value = e[1]; } home.run(); } }); });
    FILTERS.forEach(function (f) { var s = f[0] + ":" + f[1]; if (!t || s.toLowerCase().indexOf(t) > -1) out.push({ g: "Filter", l: s, k: "filter", f: function () { home.addToken(f[0], f[1]); } }); });
    PAGES.forEach(function (p) { if (!t || p[0].toLowerCase().indexOf(t) > -1) out.push({ g: "Go to", l: p[0], k: p[1].split("#")[0], href: p[1] }); });
    return out.slice(0, 14);
  }
  function q0() { return document.getElementById("q"); }
  function draw() {
    shown = items(pq.value.trim()); if (sel >= shown.length) sel = 0;
    var last = "", html = "";
    shown.forEach(function (it, i) {
      if (it.g !== last) { html += '<li class="h" role="presentation">' + it.g + "</li>"; last = it.g; }
      var inner = '<span>' + it.l.replace(/&/g, "&amp;").replace(/</g, "&lt;") + '</span><span class="k">' + it.k + "</span>";
      html += '<li role="option" class="' + (i === sel ? "sel" : "") + '" aria-selected="' + (i === sel) + '" data-i="' + i + '">' + (it.href ? '<a href="' + it.href + '">' + inner + "</a>" : '<button type="button">' + inner + "</button>") + "</li>";
    });
    pl.innerHTML = html || '<li class="h">Nothing matches</li>';
  }
  function choose(i) {
    var it = shown[i]; if (!it) return;
    if (it.href) { location.href = it.href; return; }
    pal.close();
    if (!isHome) { if (it.g === "Ask") location.href = "home.html#demo"; else location.href = "home.html#f=" + it.l.split(":").slice(0, 2).join(":").replace("Add filter ", ""); return; }
    it.f();
  }
  function openPal() { if (!pal.open) { pal.showModal(); pq.value = ""; sel = 0; draw(); pq.focus(); } }
  $$("[data-cmdk]").forEach(function (b) { b.addEventListener("click", openPal); });
  pq.addEventListener("input", function () { sel = 0; draw(); });
  pq.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % Math.max(shown.length, 1); draw(); }
    if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + shown.length) % Math.max(shown.length, 1); draw(); }
    if (e.key === "Enter") { e.preventDefault(); choose(sel); }
  });
  pl.addEventListener("click", function (e) { var li = e.target.closest("li[data-i]"); if (li && !e.target.closest("a")) choose(+li.dataset.i); });
  pal.addEventListener("click", function (e) { if (e.target === pal) pal.close(); });
  document.addEventListener("keydown", function (e) {
    var typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); pal.open ? pal.close() : openPal(); }
    else if (e.key === "/" && !typing && !pal.open) {
      var qq = q0(); if (qq) { e.preventDefault(); qq.focus(); } else { location.href = "home.html#ask"; }
    }
  });

  /* ------------------------------------------------------------ debate */
  var sps = $$(".sp");
  if (sps.length && "IntersectionObserver" in window) {
    var links = $$("[data-mm]");
    var setOn = function (id) {
      links.forEach(function (a) { a.classList.toggle("on", a.dataset.mm === id); });
      sps.forEach(function (s) { s.classList.toggle("on", s.id === id); });
    };
    var io = new IntersectionObserver(function (en) {
      en.forEach(function (x) { if (x.isIntersecting) setOn(x.target.id); });
    }, { rootMargin: "-90px 0px -60% 0px" });
    sps.forEach(function (s) { io.observe(s); });
    setOn(sps[0].id);
    document.addEventListener("keydown", function (e) {
      if (/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) || pal.open || e.ctrlKey || e.metaKey) return;
      if (e.key !== "j" && e.key !== "k") return;
      var cur = sps.findIndex(function (s) { return s.classList.contains("on"); });
      var nx = sps[Math.max(0, Math.min(sps.length - 1, cur + (e.key === "j" ? 1 : -1)))];
      nx.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
})();
