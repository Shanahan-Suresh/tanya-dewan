// The debate page: the speaker map follows the scroll, J and K step through the speeches, and long
// speeches fold. Everything here is an addition: the page reads fine with scripts off.
(function () {
  const turns = Array.from(document.querySelectorAll(".turn"));
  if (!turns.length) return;
  const map = document.getElementById("smap");
  const now = document.getElementById("smap-now");
  const ticks = Array.from(document.querySelectorAll(".smap-ticks a"));
  const rows = Array.from(document.querySelectorAll("#smap li a"));
  const bars = Array.from(document.querySelectorAll(".lanes .track a")).sort((a, b) => a.dataset.i - b.dataset.i);
  const barSeq = bars.map((b) => b.getAttribute("href").split("seq-")[1]);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const label = (map && map.dataset.of) || "{n} / {m}";
  let cur = -1, keyed = null;

  // Fold speeches taller than about 15 lines; a button opens the rest. A link to a speech opens it.
  const more = document.documentElement.lang === "ms" ? "Baca seluruh ucapan" : "Read the whole speech";
  const less = document.documentElement.lang === "ms" ? "Papar kurang" : "Show less";
  turns.forEach((t) => {
    const rec = t.querySelector(".rec");
    if (!rec || t.classList.contains("chair")) return;
    const lim = parseFloat(getComputedStyle(rec).fontSize) * 1.7 * 15;
    if (rec.offsetHeight <= lim * 1.25) return;
    rec.classList.add("clip");
    const b = document.createElement("button");
    b.type = "button"; b.className = "linkbtn"; b.textContent = more; b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", () => {
      const open = rec.classList.toggle("clip") === false;
      b.textContent = open ? less : more; b.setAttribute("aria-expanded", String(open));
    });
    rec.after(b);
  });
  const unclip = (t) => { const b = t.querySelector(".rec.clip + button"); if (b) b.click(); };
  if (location.hash.startsWith("#seq-")) { const t = document.querySelector(location.hash); if (t) unclip(t); }

  // The speech at the top of the reading area.
  function atTop() {
    const line = 140;
    let at = -1;
    for (let i = 0; i < turns.length; i++) {
      if (turns[i].getBoundingClientRect().top <= line) at = i; else break;
    }
    return at;
  }
  function mark(i) {
    if (i === cur) return;
    cur = i;
    const t = turns[Math.max(i, 0)];
    ticks.forEach((a) => a.classList.toggle("cur", a.dataset.seq === t.dataset.seq));
    bars.forEach((b, k) => b.classList.toggle("cur", barSeq[k] === t.dataset.seq));
    rows.forEach((a) => {
      const on = a.dataset.who === t.dataset.who;
      a.classList.toggle("cur", on);
      if (on && map) { const ol = a.closest("ol"); if (ol) { const r = a.getBoundingClientRect(), o = ol.getBoundingClientRect(); if (r.top < o.top || r.bottom > o.bottom) ol.scrollTop += r.top - o.top - 40; } }
    });
    if (now) now.textContent = label.replace("{n}", Math.max(i, 0) + 1).replace("{m}", turns.length) + " · " + t.querySelector(".who b").textContent.trim();
  }
  let tick = false;
  function onScroll() { if (tick) return; tick = true; requestAnimationFrame(() => { tick = false; mark(atTop()); }); }
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll);
  mark(atTop());

  // J and K.
  function jump(i) {
    i = Math.max(0, Math.min(turns.length - 1, i));
    if (keyed) keyed.classList.remove("cur");
    keyed = turns[i]; keyed.classList.add("cur");
    keyed.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    keyed.focus({ preventScroll: true });
    history.replaceState(null, "", "#seq-" + keyed.dataset.seq);
    mark(i);
  }
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k !== "j" && k !== "k") return;
    const el = e.target;
    if (el.closest && el.closest("input, textarea, select, [contenteditable]")) return;
    if (document.querySelector("dialog[open], .reader:not([hidden])")) return;
    e.preventDefault();
    const at = atTop();
    if (k === "j") jump(at + 1);
    else jump(turns[Math.max(at, 0)].getBoundingClientRect().top < -20 ? at : at - 1);
  });

  // The timeline strip: a bar opens its speech; the arrow keys, Home and End move between bars.
  const bySeq = (seq) => turns.findIndex((x) => x.dataset.seq === seq);
  bars.forEach((b, k) => {
    b.addEventListener("click", (e) => {
      const i = bySeq(barSeq[k]);
      if (i < 0) return;
      e.preventDefault(); unclip(turns[i]); jump(i);
    });
  });
  const lanes = document.querySelector(".lanes");
  if (lanes) lanes.addEventListener("keydown", (e) => {
    const k = bars.indexOf(document.activeElement);
    if (k < 0) return;
    const to = { ArrowRight: k + 1, ArrowDown: k + 1, ArrowLeft: k - 1, ArrowUp: k - 1, Home: 0, End: bars.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const n = Math.max(0, Math.min(bars.length - 1, to));
    bars.forEach((b, i) => { b.tabIndex = i === n ? 0 : -1; });
    bars[n].focus();
  });
})();
