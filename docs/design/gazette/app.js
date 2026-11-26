/* Gazette: menu, night edition toggle, scripted answer demo */
(function () {
  var root = document.documentElement;
  try { var t = localStorage.getItem("gz-theme"); if (t) root.setAttribute("data-theme", t); } catch (e) {}

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var cur = root.getAttribute("data-theme") ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("gz-theme", next); } catch (e) {}
    });
  }

  var menu = document.getElementById("nav-menu");
  var nav = document.getElementById("nav");
  if (menu && nav) {
    menu.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.querySelectorAll(".seg [data-lang]").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll(".seg [data-lang]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
    });
  });

  /* ---------- answer demo (home only) ---------- */
  var dataEl = document.getElementById("demo-data");
  if (!dataEl) return;
  var demo = JSON.parse(dataEl.textContent);
  var sec = document.getElementById("answer");
  var body = document.getElementById("answer-body");
  var margin = document.getElementById("margin-list");
  var qEl = document.getElementById("lead-q");
  var status = document.getElementById("answer-status");
  var runId = 0;

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function inline(s) {
    s = esc(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\[(\d+)\]/g, '<sup><a href="#src-$1" aria-label="Source $1">$1</a></sup>');
    return s;
  }
  function render(text, caret) {
    if ((text.match(/\*\*/g) || []).length % 2) text += "**";
    var html = "", list = false;
    text.split("\n").forEach(function (line) {
      if (/^\s*-\s+/.test(line)) {
        if (!list) { html += "<ul>"; list = true; }
        html += "<li>" + inline(line.replace(/^\s*-\s+/, "")) + "</li>";
      } else {
        if (list) { html += "</ul>"; list = false; }
        if (line.trim()) {
          var cls = /not legal advice/.test(line) ? ' class="disc"' : "";
          html += "<p" + cls + ">" + inline(line) + "</p>";
        }
      }
    });
    if (list) html += "</ul>";
    if (caret) {
      html = html.replace(/(<\/(p|li)>)(?![\s\S]*<\/(p|li)>)/, '<span class="caret" aria-hidden="true"></span>$1');
    }
    body.innerHTML = html;
  }
  function showSources(upTo) {
    var items = margin.querySelectorAll(".fn");
    items.forEach(function (el, i) { el.hidden = i >= upTo; });
  }
  function maxCited(text) {
    var m, n = 0, re = /\[(\d+)\]/g;
    while ((m = re.exec(text))) n = Math.max(n, +m[1]);
    return n;
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function run(fast) {
    var id = ++runId;
    sec.hidden = false;
    qEl.textContent = demo.question;
    status.textContent = "Searching the record";
    margin.querySelectorAll(".fn").forEach(function (el) { el.hidden = true; });
    document.getElementById("answer-btn").disabled = true;
    body.innerHTML = "";
    sec.scrollIntoView({ behavior: fast ? "auto" : "smooth", block: "start" });
    await sleep(fast ? 30 : 700);
    status.textContent = "Writing";
    var words = demo.answer.split(/(\s+)/);
    var text = "";
    var perTick = fast ? 14 : 1, delay = fast ? 6 : 38;
    for (var i = 0; i < words.length; i += perTick) {
      if (id !== runId) return;
      text += words.slice(i, i + perTick).join("");
      render(text, true);
      showSources(maxCited(text));
      await sleep(/\n/.test(words[i] || "") && !fast ? delay * 4 : delay);
    }
    if (id !== runId) return;
    render(demo.answer, false);
    showSources(demo.sources_n);
    status.textContent = "Answer complete";
    document.getElementById("answer-btn").disabled = false;
  }

  window.demoAnswer = function () { return run(true); };

  document.getElementById("ask").addEventListener("submit", function (e) { e.preventDefault(); run(false); });
  document.querySelectorAll(".ex").forEach(function (b) {
    b.addEventListener("click", function () {
      document.getElementById("q").value = b.getAttribute("data-q");
      run(false);
    });
  });
})();
