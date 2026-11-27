// The Ask page. Sends the question and filters to /api/ask/stream and reads the server-sent events:
// `stage` (live progress), `text` (the cited answer so far: replace, never append), then `done`
// (the final /api/ask body) or `error`. A ?q= link only fills the box; the reader presses Ask.
// In the static demo (S.demo, from tools/static_demo.py) there is no server: an example question
// plays its recorded events at their recorded times, and any other question gets a notice.
(function () {
  const S = JSON.parse(document.getElementById("strings").textContent);
  const $ = (id) => document.getElementById(id);
  const form = $("ask"), input = $("q"), go = form.querySelector(".ask-go");
  const answer = $("answer"), text = $("answer-text"), notice = $("notice"), progress = $("progress");
  const peek = $("peek");
  let sources = [], lastQuestion = "", token = 0;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ico = (d, cls) => `<svg class="i ${cls || ""}" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const I = {
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', ring: '<circle cx="12" cy="12" r="5"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    pencil: '<path d="M16 3l5 5L8 21H3v-5z"/><path d="M13 6l5 5"/>',
    sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  };
  const draft = (x) => x.draft ? `<span class="draft" title="${esc(S.draft_note)}">${ico(I.pencil, "sm")}${esc(S.draft)}</span>` : "";
  const secs = (ms) => ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;

  // ---- the answer text: short Markdown with [n] marks ----
  function markdown(src) {
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(\d+)\]/g, (_, n) => `<button type="button" class="cite" data-n="${n}" aria-label="${esc(S.source_n)} ${n}" aria-expanded="false">${n}</button>`);
    const item = /^\s*[-*] /;
    return esc(src).split(/\n{2,}/).map((b) => {
      const runs = [];
      for (const l of b.split("\n")) {
        const list = item.test(l);
        if (!runs.length || runs[runs.length - 1].list !== list) runs.push({ list, lines: [] });
        runs[runs.length - 1].lines.push(l);
      }
      return runs.map((r) => r.list
        ? "<ul>" + r.lines.map((l) => "<li>" + inline(l.replace(item, "")) + "</li>").join("") + "</ul>"
        : "<p>" + r.lines.map(inline).join("<br>") + "</p>").join("");
    }).join("");
  }

  // ---- live progress ----
  const STEPS = [
    { keys: ["bm25", "dense", "fused"], label: S.step_search },
    { keys: ["reranked"], label: S.step_rank },
    { keys: ["answer"], label: S.step_write },
  ];
  let state = [], stageMs = {};
  function drawProgress() {
    progress.innerHTML = STEPS.map((st, i) => {
      const ms = st.keys.reduce((a, k) => a + (stageMs[k] || 0), 0);
      const icon = state[i] === "done" ? ico(I.check, "sm") : state[i] === "active" ? ico(I.arrow, "sm") : ico(I.ring, "sm");
      return `<li data-s="${state[i]}">${icon}<span>${esc(st.label)}${state[i] === "active" ? "…" : ""}</span>${ms ? `<span class="t">${secs(ms)}</span>` : ""}</li>`;
    }).join("");
  }
  function startStage(name) {
    const at = STEPS.findIndex((s) => s.keys.includes(name));
    if (at < 0) return;
    state = STEPS.map((_, i) => (i < at ? "done" : i === at ? "active" : "wait"));
    drawProgress();
  }

  // ---- popover and linked highlight between marks and source cards ----
  const lit = (n, on) => document.querySelectorAll(`.cite[data-n="${n}"], .src[data-n="${n}"]`).forEach((el) => el.classList.toggle("lit", on));
  const target = (e) => e.target.closest && e.target.closest(".cite, .src");
  document.addEventListener("mouseover", (e) => { const t = target(e); if (t && sources.length) lit(t.dataset.n, true); });
  document.addEventListener("mouseout", (e) => { const t = target(e); if (t) lit(t.dataset.n, false); });
  document.addEventListener("focusin", (e) => { const t = target(e); if (t && sources.length) lit(t.dataset.n, true); });
  document.addEventListener("focusout", (e) => { const t = target(e); if (t) lit(t.dataset.n, false); });

  let openMark = null;
  function closePeek() { peek.hidden = true; if (openMark) { openMark.setAttribute("aria-expanded", "false"); openMark = null; } }
  function openPeek(mark) {
    const s = sources.find((x) => String(x.n) === mark.dataset.n);
    if (!s) return;
    closePeek();
    openMark = mark; mark.setAttribute("aria-expanded", "true");
    peek.querySelector(".num").textContent = s.n;
    peek.querySelector(".cl-t").textContent = (s.title || s.cite) + (s.meta ? " · " + s.meta : "");
    peek.querySelector("blockquote").textContent = (s.quotes && s.quotes[0]) || "";
    peek.dataset.n = s.n;
    peek.hidden = false;
    const r = mark.getBoundingClientRect(), w = peek.offsetWidth, h = peek.offsetHeight;
    peek.style.left = Math.max(12, Math.min(r.left - 12, innerWidth - w - 12)) + "px";
    peek.style.top = (r.bottom + 8 + h > innerHeight - 12 ? Math.max(12, r.top - h - 8) : r.bottom + 8) + "px";
  }
  document.addEventListener("click", (e) => {
    const mark = e.target.closest(".cite");
    if (mark) { if (openMark === mark) closePeek(); else openPeek(mark); return; }
    if (e.target.closest(".peek .go")) {
      const card = $("src-" + peek.dataset.n); closePeek();
      if (card) { card.scrollIntoView({ block: "center" }); card.focus({ preventScroll: true }); lit(peek.dataset.n, true); setTimeout(() => lit(peek.dataset.n, false), 1800); }
      return;
    }
    if (!e.target.closest(".peek")) closePeek();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !peek.hidden) { const m = openMark; closePeek(); if (m) m.focus(); } });
  addEventListener("scroll", closePeek, { passive: true });

  // ---- final state ----
  function sourceCard(s) {
    return `<li class="card src" id="src-${s.n}" data-n="${s.n}" tabindex="-1">
      <div class="top"><span class="num">${s.n}</span><div class="cl"><a href="${esc(s.url)}">${esc(s.title || s.cite)}</a>${s.meta ? `<span class="meta">${esc(s.meta)}</span>` : ""}</div></div>
      ${draft(s)}
      <div class="quotes">${(s.quotes || []).map((q) => `<blockquote class="rec" lang="ms">${esc(q)}</blockquote>`).join("")}</div>
      ${s.pdf ? `<div class="links"><a href="${esc(s.pdf)}" rel="noopener">${esc(S.pdf)}</a></div>` : ""}
    </li>`;
  }
  function render(r) {
    sources = r.sources || [];
    const answered = !!(r.answer && r.answer.trim()) && !r.budget_out;
    $("answer-state").textContent = answered ? S.done : "";
    if (answered) {
      // The answer ends with the not-legal-advice line, which the answer foot already shows.
      let body = r.answer.trim();
      for (const line of S.advice_lines || []) if (body.endsWith(line)) body = body.slice(0, -line.length).trim();
      text.innerHTML = markdown(body);
      $("answer-foot").hidden = false;
    } else {
      text.innerHTML = `<p class="wait">${esc(S.no_answer)}</p>`;
      $("answer-foot").hidden = false;
    }
    if (r.budget_out) notice.innerHTML = `<p class="notice" role="status">${ico(I.info)}<span>${esc(S.budget_out)}</span></p>`;
    $("src-count").textContent = sources.length ? `(${sources.length})` : "";
    $("src-list").innerHTML = sources.length ? sources.map(sourceCard).join("") : `<li class="card src hold">${esc(S.no_answer)}</li>`;
    // How it was found
    const most = Math.max(1, ...(r.stages || []).map((s) => s.ms || 0));
    $("how-body").innerHTML = `<div style="overflow-x:auto"><table class="stages"><thead><tr><th>${esc(S.stage)}</th><th class="r">${esc(S.hits)}</th><th class="r">${esc(S.time)}</th><th aria-hidden="true"></th></tr></thead><tbody>${
      (r.stages || []).map((s) => `<tr><td>${esc(S[s.name] || s.name)}</td><td class="r">${s.hits}</td><td class="r">${secs(s.ms)}</td><td style="width:22%"><span class="stage-bar" style="width:${Math.max(2, Math.round(100 * s.ms / most))}%"></span></td></tr>`).join("")
    }</tbody></table></div>`;
    const bits = [];
    if (r.search_ms != null) bits.push(`${secs(r.search_ms)} ${S.search}`);
    $("how-meta").textContent = bits.join(", ");
    $("how").hidden = false;
    // Passages
    const ps = r.passages || [];
    $("passages-n").textContent = ps.length ? `(${ps.length})` : "";
    $("passages-body").innerHTML = ps.map((p, i) => `<div class="passage">
      <div class="head">${i + 1}. <a href="${esc(p.url)}">${esc(p.title || p.cite)}</a>${p.meta ? " · " + esc(p.meta) : ""}${p.via ? " · " + esc(p.via) : ""}</div>
      ${draft(p)}
      <div class="muted small">${esc(p.header)}</div>
      <blockquote class="rec" lang="ms">${esc(p.text)}</blockquote>
      ${p.pdf ? `<div><a href="${esc(p.pdf)}" rel="noopener">${esc(S.pdf)}</a></div>` : ""}
    </div>`).join("");
    $("passages").hidden = !ps.length;
    $("passages").open = !!r.budget_out;
    state = STEPS.map(() => "done"); drawProgress();
  }
  function fail(msg) {
    notice.innerHTML = `<p class="notice err" role="alert">${ico(I.alert)}<span>${esc(msg || S.error)}</span></p>`;
    text.innerHTML = ""; progress.innerHTML = "";
    $("src-list").innerHTML = "";
  }

  // ---- ask ----
  function body(q) {
    const o = { question: q };
    new FormData(form).forEach((v, k) => { if (k !== "q" && String(v).trim()) o[k] = String(v).trim(); });
    return o;
  }
  // One server-sent event; true when it ends the answer.
  function onEvent(ev, d) {
    if (ev === "stage") {
      if (d.hits == null) startStage(d.name); else { stageMs[d.name] = d.ms; drawProgress(); }
    } else if (ev === "text") {
      text.innerHTML = markdown(d.text) + '<span class="caret" aria-hidden="true"></span>';
    } else if (ev === "done") { render(d); return true; }
    else if (ev === "error") { fail(d.error); return true; }
    return false;
  }
  const norm = (q) => q.trim().toLowerCase().replace(/\s+/g, " ");
  const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
  async function playRecorded(q, mine) {
    const rec = S.demo.find((x) => norm(x.q) === norm(q));
    if (!rec) {
      notice.innerHTML = `<p class="notice" role="status">${ico(I.info)}<span>${esc(S.demo_only)}</span></p>`;
      text.innerHTML = ""; progress.innerHTML = ""; $("src-list").innerHTML = "";
      return;
    }
    const events = (await (await fetch(rec.file)).json()).events;
    let at = 0;
    for (const e of events) {
      await wait(Math.min(e.t - at, 2500)); at = e.t;
      if (mine !== token) return;
      if (onEvent(e.event, e.data)) return;
    }
  }
  async function ask(q) {
    const mine = ++token;
    lastQuestion = q;
    go.disabled = true; go.setAttribute("aria-busy", "true");
    answer.hidden = false;
    $("q-echo").textContent = q;
    notice.innerHTML = ""; sources = []; closePeek();
    text.innerHTML = `<p class="wait">${esc(S.asking)}</p>`;
    $("answer-state").textContent = "";
    $("answer-foot").hidden = true; $("how").hidden = true; $("passages").hidden = true;
    $("src-count").textContent = "";
    $("src-list").innerHTML = `<li class="card src hold">${esc(S.sources_wait)}</li>`;
    state = STEPS.map(() => "wait"); stageMs = {}; drawProgress();
    if (!S.demo) try { history.replaceState(null, "", "/?q=" + encodeURIComponent(q)); } catch (e) { /* the link is a convenience */ }
    answer.scrollIntoView({ block: "start" }); answer.focus({ preventScroll: true });
    if (S.demo) {
      try { await playRecorded(q, mine); } catch (e) { if (mine === token) fail(S.error); }
      finally { if (mine === token) { go.disabled = false; go.removeAttribute("aria-busy"); } }
      return;
    }
    try {
      const res = await fetch("/api/ask/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body(q)) });
      if (!res.ok) { let m = ""; try { m = (await res.json()).error; } catch (e) { /* no body */ } fail(m); return; }
      const reader = res.body.getReader(), dec = new TextDecoder();
      let buf = "", finished = false;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, cut); buf = buf.slice(cut + 2);
          let ev = "message", data = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) ev = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (mine !== token || !data) continue;
          if (onEvent(ev, JSON.parse(data))) finished = true;
        }
      }
      if (!finished && mine === token) fail(S.error);
    } catch (e) {
      if (mine === token) fail(S.error);
    } finally {
      if (mine === token) { go.disabled = false; go.removeAttribute("aria-busy"); }
    }
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (q && !go.disabled) ask(q);
  });

  // ---- copy link ----
  $("copy-link").addEventListener("click", async () => {
    const url = S.demo ? location.href.split("#")[0] : location.origin + "/?q=" + encodeURIComponent(lastQuestion || input.value.trim());
    try { await navigator.clipboard.writeText(url); } catch (e) {
      const t = document.createElement("textarea"); t.value = url; document.body.appendChild(t); t.select();
      try { document.execCommand("copy"); } catch (x) { /* nothing more to try */ } t.remove();
    }
    const label = $("copy-link").querySelector("span");
    label.textContent = S.copied; $("copy-status").textContent = S.copied;
    setTimeout(() => { label.textContent = S.copy; $("copy-status").textContent = ""; }, 2500);
  });

  // ---- more filters ----
  const more = $("more-filters"), extra = $("extra-filters");
  more.addEventListener("click", () => {
    const open = extra.hidden;
    extra.hidden = !open; more.setAttribute("aria-expanded", String(open));
    more.querySelector(".mf-t").textContent = open ? S.less : S.more;
  });

  // ---- example questions: three at a time, both languages, rotating while nobody is using them ----
  const other = S.lang === "ms" ? "en" : "ms";
  const pool = [];
  const byLang = (lg) => S.demo ? S.demo.filter((x) => x.lang === lg).map((x) => x.q) : (S.examples[lg] || []);
  const a = byLang(S.lang), b = byLang(other);
  for (let i = 0; i < Math.max(a.length, b.length); i++) { if (a[i]) pool.push([S.lang, a[i]]); if (b[i]) pool.push([other, b[i]]); }
  const tryBox = $("try");
  let at = 0;
  function drawTry() {
    tryBox.querySelectorAll("button").forEach((x) => x.remove());
    for (let k = 0; k < Math.min(3, pool.length); k++) {
      const [lg, q] = pool[(at + k) % pool.length];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.innerHTML = `<span class="lg">${lg.toUpperCase() === "MS" ? "BM" : "EN"}</span>${esc(q)}`;
      btn.addEventListener("click", () => { input.value = q; form.requestSubmit(); });
      tryBox.appendChild(btn);
    }
  }
  if (pool.length) {
    drawTry();
    let busy = false;
    tryBox.addEventListener("mouseenter", () => { busy = true; });
    tryBox.addEventListener("mouseleave", () => { busy = false; });
    tryBox.addEventListener("focusin", () => { busy = true; });
    tryBox.addEventListener("focusout", () => { busy = false; });
    setInterval(() => { if (!busy && document.visibilityState === "visible") { at = (at + 1) % pool.length; drawTry(); } }, 9000);
  }
})();
