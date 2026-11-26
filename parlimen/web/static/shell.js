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
