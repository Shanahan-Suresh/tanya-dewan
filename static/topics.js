// The topics page chart: debates a month on the biggest topics. Point to read a month, drag to
// zoom, click to open that topic's debates of the month (the line nearest the pointer). The page's
// table holds the same numbers for readers who cannot use the chart.
(function () {
  const root = document.getElementById("te");
  if (!root) return;
  const D = JSON.parse(document.getElementById("te-data").textContent);
  const $ = (s) => root.querySelector(s), $$ = (s) => Array.from(root.querySelectorAll(s));
  const svg = $("svg"), tip = $(".te-tip"), chart = $(".te-chart"), said = $(".te-said");
  const links = Object.fromEntries($$(".te-link").map((a) => [a.dataset.topic, a.getAttribute("href")]));
  const MON = D.lang === "ms" ? "Jan Feb Mac Apr Mei Jun Jul Ogo Sep Okt Nov Dis".split(" ") : "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  const all = D.series.flatMap((s) => s.points.map((p) => p[0])).sort();
  const months = [];
  if (all.length) {
    let [y, m] = all[0].split("-").map(Number);
    const [y1, m1] = all[all.length - 1].split("-").map(Number);
    while (y < y1 || (y === y1 && m <= m1)) { months.push(`${y}-${String(m).padStart(2, "0")}`); if (++m > 12) { m = 1; y++; } }
  }
  const ser = D.series.map((s, i) => { const map = Object.fromEntries(s.points); return { topic: s.topic, name: s.name, color: `var(--t${i + 1})`, on: true, v: months.map((m) => map[m] || 0) }; });
  const W = 1000, H = 340, L = 44, R = 16, T = 26, B = 30;
  let lo = 0, hi = months.length - 1, ymax = 1, drag = null;
  const xs = (i) => L + (W - L - R) * (i - lo) / Math.max(1, hi - lo);
  const ys = (v) => H - B - (H - B - T) * v / ymax;
  const label = (m) => { const [y, mo] = m.split("-"); return `${MON[+mo - 1]} ${y}`; };

  function draw(extra) {
    const vis = ser.filter((s) => s.on);
    ymax = Math.max(10, ...vis.flatMap((s) => s.v.slice(lo, hi + 1)));
    const step = ymax > 400 ? 100 : ymax > 200 ? 50 : ymax > 80 ? 20 : 10;
    ymax = Math.ceil(ymax / step) * step;
    let g = '<g class="grid">';
    for (let v = 0; v <= ymax; v += step) g += `<line x1="${L}" x2="${W - R}" y1="${ys(v)}" y2="${ys(v)}"/><text x="${L - 6}" y="${ys(v) + 4}" text-anchor="end">${v}</text>`;
    g += "</g>";
    const span = hi - lo, every = span > 60 ? 12 : span > 24 ? 6 : span > 10 ? 3 : 1;
    let xa = "";
    for (let i = lo; i <= hi; i++) {
      const [y, mo] = months[i].split("-");
      if ((+mo - 1) % every === 0) xa += `<text x="${xs(i)}" y="${H - 10}" text-anchor="middle">${every >= 12 ? y : MON[+mo - 1] + (mo === "01" || i === lo ? " " + y.slice(2) : "")}</text>`;
    }
    let ev = "";
    for (const [m, name] of D.events) { const i = months.indexOf(m); if (i >= lo && i <= hi) ev += `<g class="ev"><line x1="${xs(i)}" x2="${xs(i)}" y1="${T - 6}" y2="${H - B}"/><text x="${xs(i) + 5}" y="${T + 4}">${esc(name)}</text></g>`; }
    const lines = vis.map((s) => `<path class="ser" style="stroke:${s.color}" d="${s.v.slice(lo, hi + 1).map((v, k) => (k ? "L" : "M") + xs(lo + k).toFixed(1) + " " + ys(v).toFixed(1)).join("")}"/>`).join("");
    svg.innerHTML = g + ev + lines + `<g class="xa">${xa}</g>` + (extra || "");
    $("#te-reset").hidden = lo === 0 && hi === months.length - 1;
  }
  const pointAt = (e) => { const b = svg.getBoundingClientRect(); return { x: (e.clientX - b.left) * W / b.width, y: (e.clientY - b.top) * H / b.height }; };
  const idxAt = (e) => Math.max(lo, Math.min(hi, Math.round(lo + (pointAt(e).x - L) / (W - L - R) * (hi - lo))));

  svg.addEventListener("pointerdown", (e) => { drag = { a: idxAt(e), b: idxAt(e), y: pointAt(e).y }; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", (e) => {
    const i = idxAt(e);
    if (drag) {
      drag.b = i;
      const a = Math.min(drag.a, drag.b), b = Math.max(drag.a, drag.b);
      if (b - a >= 1) { draw(`<rect class="brush" x="${xs(a)}" y="${T}" width="${Math.max(1, xs(b) - xs(a))}" height="${H - B - T}"/>`); tip.hidden = true; return; }
    }
    draw(`<line class="cross" x1="${xs(i)}" x2="${xs(i)}" y1="${T}" y2="${H - B}"/>`);
    const vis = ser.filter((s) => s.on).map((s) => ({ s, v: s.v[i] })).sort((a, b) => b.v - a.v);
    tip.innerHTML = `<b>${esc(label(months[i]))}</b>` + vis.map(({ s, v }) => `<div><span><i style="background:${s.color}"></i>${esc(cap(s.name))}</span><span class="tnum">${v}</span></div>`).join("");
    tip.hidden = false;
    const cb = chart.getBoundingClientRect(), sb = svg.getBoundingClientRect();
    const px = sb.left - cb.left + xs(i) * sb.width / W + chart.scrollLeft;
    tip.style.left = (px + 12 + tip.offsetWidth > chart.scrollLeft + cb.width ? px - tip.offsetWidth - 12 : px + 12) + "px";
    tip.style.top = "8px";
  });
  svg.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const a = Math.min(drag.a, drag.b), b = Math.max(drag.a, drag.b), y = drag.y;
    drag = null;
    if (b - a >= 2) {
      lo = a; hi = b; draw();
      said.textContent = D.showing.replace("{a}", label(months[lo])).replace("{b}", label(months[hi]));
      return;
    }
    // A click: the visible line nearest the pointer at that month.
    const vis = ser.filter((s) => s.on);
    const near = vis.reduce((best, s) => Math.abs(ys(s.v[a]) - y) < Math.abs(ys(best.v[a]) - y) ? s : best, vis[0]);
    const href = links[near.topic];
    if (!href) return;
    location.href = D.demo ? href : `${href}?month=${months[a]}`;
  });
  svg.addEventListener("pointerleave", () => { if (!drag) { tip.hidden = true; draw(); } });
  $$(".te-legend button").forEach((b) => b.addEventListener("click", () => {
    const s = ser[+b.dataset.i];
    if (s.on && ser.filter((x) => x.on).length === 1) return;
    s.on = !s.on; b.setAttribute("aria-pressed", String(s.on)); draw();
  }));
  $("#te-reset").addEventListener("click", () => { lo = 0; hi = months.length - 1; draw(); said.textContent = ""; });
  draw();
})();
