// The phone "More" sheet: opens from the bottom bar, closes on Escape, on a tap outside or on a link.
(function () {
  const btn = document.getElementById("more-btn");
  const sheet = document.getElementById("more-sheet");
  if (!btn || !sheet) return;
  const set = (open) => { sheet.hidden = !open; btn.setAttribute("aria-expanded", String(open)); };
  btn.addEventListener("click", () => set(sheet.hidden));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !sheet.hidden) { set(false); btn.focus(); } });
  document.addEventListener("click", (e) => { if (!sheet.hidden && !sheet.contains(e.target) && !btn.contains(e.target)) set(false); });
})();

// The Act's contents list is open on wide screens and folded on a phone.
(function () {
  const d = document.querySelector("details.toc-d");
  if (d && matchMedia("(min-width: 1000px)").matches) d.open = true;
})();

// The light and dark switch: device, dark, light, in turn; the choice stays in this browser.
(function () {
  const btn = document.getElementById("theme-btn");
  const S = JSON.parse(document.getElementById("shell-strings").textContent);
  if (!btn) return;
  const KEYS = [null, "dark", "light"];
  const now = () => Math.max(0, KEYS.indexOf(document.documentElement.dataset.theme || null));
  function paint(i) {
    btn.innerHTML = S.icons[i];
    btn.setAttribute("aria-label", S.themes[i]); btn.title = S.themes[i];
  }
  btn.addEventListener("click", () => {
    const i = (now() + 1) % KEYS.length, v = KEYS[i];
    if (v) document.documentElement.dataset.theme = v; else delete document.documentElement.dataset.theme;
    try { if (v) localStorage.setItem("theme", v); else localStorage.removeItem("theme"); } catch (e) { /* a convenience only */ }
    paint(i);
  });
  paint(now());
})();

// Jump to anything: Ctrl K (or the header button) opens a box that finds MPs, Acts, bills,
// topics and sittings by name, from /jump.json. The static demo writes its own jump.json, whose
// links are file paths inside a language folder.
(function () {
  const dlg = document.getElementById("jump"), input = document.getElementById("jump-q");
  const list = document.getElementById("jump-list"), status = document.getElementById("jump-status");
  const btn = document.getElementById("jump-btn");
  if (!dlg || !dlg.showModal) { if (btn) btn.hidden = true; return; }
  const S = JSON.parse(document.getElementById("shell-strings").textContent);
  const css = document.querySelector('link[rel="stylesheet"][href*="site.css"]');
  const root = new URL("../", css ? css.href : location.href);
  const ORDER = ["mp", "act", "bill", "topic", "sitting"];
  const MONTHS = S.lang === "ms" ? "Jan Feb Mac Apr Mei Jun Jul Ogo Sep Okt Nov Dis".split(" ") : "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  let items = null, loading = null, shown = [], sel = 0, opener = null;

  function label(x) {
    if (x.k === "sitting") { const [y, m, d] = x.t.split("-"); return { t: `${+d} ${MONTHS[+m - 1]} ${y}`, s: S.chambers[x.s] || x.s }; }
    if (x.k === "topic") return { t: x.t.charAt(0).toUpperCase() + x.t.slice(1), s: x.s };
    return { t: x.t, s: x.s };
  }
  function load() {
    if (!loading) {
      status.textContent = S.loading;
      loading = fetch(new URL("jump.json", root)).then((r) => r.json()).then((rows) => {
        items = rows.map((x) => { const l = label(x); return { ...x, ...l, hay: fold(l.t + " " + l.s + " " + x.t) }; });
        status.textContent = ""; draw();
      }).catch(() => { loading = null; status.textContent = S.failed; });
    }
    return loading;
  }
  function url(u) {
    if (u.startsWith("/")) return u;
    return new URL((S.lang === "ms" ? "ms/" : "") + u, root).href;
  }
  // Every word must appear; a title that starts with the words ranks first, then a word start.
  function score(x, words) {
    let sc = 0;
    for (const w of words) {
      const i = x.hay.indexOf(w);
      if (i < 0) return -1;
      sc += i === 0 ? 30 : (x.hay[i - 1] === " " ? 12 : 2);
    }
    return sc - x.t.length / 100;
  }
  function draw() {
    if (!items) { list.innerHTML = ""; return; }
    const q = fold(input.value.trim()), words = q.split(/\s+/).filter(Boolean);
    let hits;
    if (!words.length) hits = items.filter((x) => x.k === "topic").slice(0, 6).concat(items.filter((x) => x.k === "sitting").slice(0, 4));
    else hits = items.map((x) => [score(x, words), x]).filter((p) => p[0] >= 0).sort((a, b) => b[0] - a[0]).map((p) => p[1]);
    const groups = ORDER.map((k) => [k, hits.filter((x) => x.k === k).slice(0, 6)]).filter((g) => g[1].length);
    shown = groups.flatMap((g) => g[1]);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    let i = 0;
    list.innerHTML = groups.map(([k, xs]) => `<li role="presentation" class="jg">${esc(S.kinds[k])}</li>` + xs.map((x) => {
      const n = i++;
      return `<li role="option" id="jo-${n}" data-i="${n}" aria-selected="${n === sel}"><span class="jt">${esc(x.t)}</span>${x.s ? `<span class="js">${esc(x.s)}</span>` : ""}</li>`;
    }).join("")).join("");
    if (shown.length) input.setAttribute("aria-activedescendant", "jo-" + sel); else input.removeAttribute("aria-activedescendant");
    status.textContent = shown.length ? "" : S.none;
  }
  function move(d) {
    if (!shown.length) return;
    sel = (sel + d + shown.length) % shown.length;
    list.querySelectorAll("[role=option]").forEach((o) => o.setAttribute("aria-selected", String(+o.dataset.i === sel)));
    input.setAttribute("aria-activedescendant", "jo-" + sel);
    const o = document.getElementById("jo-" + sel); if (o) o.scrollIntoView({ block: "nearest" });
  }
  function choose(i) { const x = shown[i]; if (x) location.href = url(x.u); }
  function open() {
    if (dlg.open) return;
    opener = document.activeElement;
    input.value = ""; sel = 0; draw();
    dlg.showModal(); input.focus();
    load();
  }
  dlg.addEventListener("close", () => { if (opener && document.contains(opener)) opener.focus(); });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  input.addEventListener("input", () => { sel = 0; draw(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { move(1); e.preventDefault(); }
    else if (e.key === "ArrowUp") { move(-1); e.preventDefault(); }
    else if (e.key === "Enter") { choose(sel); e.preventDefault(); }
  });
  list.addEventListener("click", (e) => { const o = e.target.closest("[role=option]"); if (o) choose(+o.dataset.i); });
  if (btn) btn.addEventListener("click", open);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (dlg.open) dlg.close(); else open(); }
  });
})();

// The keys list: ? on any page, or the button in the footer.
(function () {
  const dlg = document.getElementById("keys");
  if (!dlg || !dlg.showModal) return;
  const open = () => { if (!dlg.open) dlg.showModal(); };
  document.getElementById("keys-close").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  document.querySelectorAll("[data-keys]").forEach((b) => b.addEventListener("click", open));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
    if (document.querySelector("dialog[open]")) return;
    e.preventDefault(); open();
  });
})();

// The seat map's find box: the seats whose MP or seat name match light up.
(function () {
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  document.querySelectorAll(".seatmap").forEach((fig) => {
    const box = fig.querySelector(".sm-find input");
    if (!box) return;
    const seats = Array.from(fig.querySelectorAll("svg a"));
    const names = seats.map((a) => fold(a.querySelector("title").textContent));
    const big = fig.querySelector("[data-big]"), small = fig.querySelector("[data-small]"), said = fig.querySelector(".sm-said");
    const first = { big: big.textContent, small: small.textContent, on: seats.map((a) => a.classList.contains("on")), lit: fig.classList.contains("has-lit") };
    box.addEventListener("input", () => {
      const q = fold(box.value.trim());
      said.textContent = "";
      if (!q) {
        seats.forEach((a, i) => a.classList.toggle("on", first.on[i]));
        fig.classList.toggle("has-lit", first.lit); big.textContent = first.big; small.textContent = first.small;
        return;
      }
      let n = 0, hit = null;
      seats.forEach((a, i) => { const on = names[i].includes(q); a.classList.toggle("on", on); if (on) { n++; hit = a; } });
      fig.classList.add("has-lit");
      big.textContent = n; small.textContent = n === 1 ? box.dataset.match : box.dataset.matches;
      if (n === 1) {
        const link = document.createElement("a");
        link.href = hit.getAttribute("href"); link.textContent = hit.querySelector("title").textContent;
        said.appendChild(link);
      }
    });
  });
})();

// The header condenses once the page scrolls.
(function () {
  const h = document.querySelector(".site-header");
  if (!h) return;
  let tick = false;
  const set = () => { tick = false; h.classList.toggle("condensed", window.scrollY > 24); };
  addEventListener("scroll", () => { if (!tick) { tick = true; requestAnimationFrame(set); } }, { passive: true });
  set();
})();

// Motion, once and only when the reader allows it: numbers count up, the topic bars grow.
(function () {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
  document.documentElement.classList.add("js-reveal");
  const fmt = (n) => n.toLocaleString("en-US");
  const run = (el) => {
    const to = Number(el.dataset.count);
    if (!isFinite(to) || to < 20) return;
    const t0 = performance.now(), dur = 900;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(Math.round(to * e));
      if (k < 1) requestAnimationFrame(step); else el.textContent = fmt(to);
    };
    el.textContent = fmt(0);
    requestAnimationFrame(step);
  };
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    io.unobserve(e.target);
    if (e.target.dataset.count) run(e.target); else e.target.classList.add("in");
  }), { threshold: 0.25 });
  document.querySelectorAll("[data-count], .chart-card").forEach((el) => io.observe(el));
})();
