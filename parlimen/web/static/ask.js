// The ask page: sends the question and filters to /api/ask and shows the cited answer, its
// sources, the passages it read and how the search found them.
(function () {
  const S = JSON.parse(document.getElementById("strings").textContent);
  const form = document.getElementById("ask");
  const out = document.getElementById("result");
  const button = form.querySelector("button[type=submit]");

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // A shared link (?q=...) fills the box; the reader presses Ask, so a crawler spends nothing.
  // The answer is short Markdown: paragraphs, "-" lists, **bold** and [n] citation marks.
  // A block may open with a lead-in line ("... said:") and go on as a list, so each run of list
  // lines and each run of other lines becomes its own element.
  function markdown(text) {
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(\d+)\]/g, '<sup><a href="#src-$1">[$1]</a></sup>');
    const item = /^\s*[-*] /;
    return esc(text).split(/\n{2,}/).map((b) => {
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

  function render(r) {
    const sources = r.sources.map((s) => `
      <li id="src-${s.n}"><strong>[${s.n}]</strong> <a href="${esc(s.url)}">${esc(s.cite)}</a>
        ${s.pdf ? ` · <a href="${esc(s.pdf)}" rel="noopener">${esc(S.pdf)}</a>` : ""}
        ${s.quotes.map((q) => `<blockquote class="verbatim">${esc(q)}</blockquote>`).join("")}
      </li>`).join("");
    const passages = r.passages.map((p, i) => `
      <div class="passage">
        <div class="head">${i + 1}. <a href="${esc(p.url)}">${esc(p.cite)}</a>${p.via ? " · " + esc(p.via) : ""}
          ${p.pdf ? ` · <a href="${esc(p.pdf)}" rel="noopener">${esc(S.pdf)}</a>` : ""}</div>
        <div class="small muted">${esc(p.header)}</div>
        <div class="body">${esc(p.text)}</div>
      </div>`).join("");
    const most = Math.max(1, ...r.stages.map((s) => s.ms));
    const stages = r.stages.map((s) => `
      <tr><td>${esc(S[s.name] || s.name)}</td><td>${s.hits} ${esc(S.hits)}</td>
        <td>${s.ms} ms</td><td><span class="bar" style="width:${Math.max(2, Math.round(120 * s.ms / most))}px"></span></td></tr>`).join("");
    out.innerHTML = `
      <p class="ai-note">${esc(S.ai)}</p>
      <div class="answer">${markdown(r.answer)}</div>
      ${sources ? `<h2>${esc(S.sources)}</h2><ol class="plain sources">${sources}</ol>` : ""}
      <details><summary>${esc(S.passages)} (${r.passages.length})</summary>${passages}</details>
      <details><summary>${esc(S.how)}</summary>
        <table class="stages">${stages}</table>
        <p class="small muted">${esc(r.filters)} · ${r.total_ms} ms · ${esc(S.cost)} US$${r.usd.toFixed(4)}</p>
      </details>
      <p class="small muted">${esc(S.each)}</p>`;
  }

  async function ask(question) {
    const body = Object.fromEntries(new FormData(form).entries());
    body.question = question;
    button.disabled = true;
    out.hidden = false;
    out.innerHTML = `<p class="muted">${esc(S.busy)}</p>`;
    try {
      const resp = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const r = await resp.json();
      if (!resp.ok) throw new Error(r.error || resp.statusText);
      render(r);
      history.replaceState(null, "", "?q=" + encodeURIComponent(question));
    } catch (e) {
      out.innerHTML = `<p><strong>${esc(S.error)}:</strong> ${esc(e.message)}</p>`;
    } finally {
      button.disabled = false;
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = form.question.value.trim();
    if (q) ask(q);
  });
  form.question.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  form.querySelectorAll(".example").forEach((b) => b.addEventListener("click", () => {
    form.question.value = b.textContent;
    ask(b.textContent);
  }));
  const q = new URLSearchParams(location.search).get("q");
  if (q) form.question.value = q;
})();
