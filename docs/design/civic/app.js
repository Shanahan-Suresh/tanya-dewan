/* Civic prototype behaviour: nav sheet, rotating examples, filters, scripted answer demo,
   citation previews, summary language tabs. Plain JS, no dependencies. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* bottom nav "More" sheet */
  var more = $('#more-btn'), sheet = $('#more-sheet');
  if (more && sheet) {
    more.addEventListener('click', function () {
      var open = sheet.hidden;
      sheet.hidden = !open;
      more.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', function (e) {
      if (!sheet.hidden && !sheet.contains(e.target) && !more.contains(e.target)) { sheet.hidden = true; more.setAttribute('aria-expanded', 'false'); }
    });
  }

  /* language switch (cosmetic in the prototype) */
  $$('.lang button').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('.lang button').forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); });
    });
  });

  /* summary language tabs */
  $$('.tabs').forEach(function (tabs) {
    var targets = tabs.getAttribute('data-for');
    $$('button', tabs).forEach(function (b) {
      b.addEventListener('click', function () {
        $$('button', tabs).forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); });
        $$('[data-lang]', document.getElementById(targets)).forEach(function (t) { t.hidden = t.getAttribute('data-lang') !== b.getAttribute('data-l'); });
      });
    });
  });

  /* ---------- home only ---------- */
  var dataEl = document.getElementById('demo-data');
  if (!dataEl) return;
  var D = JSON.parse(dataEl.textContent);
  var input = $('#q'), form = $('#ask-form'), out = $('#answer');

  /* extra filters */
  var mf = $('#more-filters'), extra = $('#extra-filters');
  if (mf && extra) mf.addEventListener('click', function () {
    var open = extra.hidden; extra.hidden = !open; mf.setAttribute('aria-expanded', String(open));
    $('.mf-t', mf).textContent = open ? 'Fewer filters' : 'More filters';
  });

  /* rotating example questions, both languages */
  var examples = [
    'What has the government said about targeted diesel subsidies?',
    'Apakah kata kerajaan tentang subsidi diesel bersasar?',
    'What does the Employment Act say about maternity leave?',
    'Apakah komitmen Menteri Kesihatan mengenai jerebu?',
    'Which MPs asked about ambulances in Negeri Sembilan?',
    'Siapakah yang bertanya tentang projek jalan FT362?'
  ];
  var ei = 0, rot = null;
  function rotate() { ei = (ei + 1) % examples.length; if (!input.value && document.activeElement !== input) input.placeholder = examples[ei]; }
  input.placeholder = examples[0];
  rot = setInterval(rotate, 3800);

  /* tiny markdown: **bold**, "- " bullets, [n] citation marks */
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function inline(s) {
    s = esc(s);
    if ((s.match(/\*\*/g) || []).length % 2) s += '**';
    s = s.replace(/\[\d*$/, '');
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    return s.replace(/\[(\d+)\]/g, function (m, n) {
      return '<button type="button" class="cite" data-n="' + n + '" aria-label="Source ' + n + '" aria-expanded="false">' + n + '</button>';
    });
  }
  function md(text) {
    var html = '', list = false;
    text.split('\n').forEach(function (line) {
      if (/^- /.test(line)) { if (!list) { html += '<ul>'; list = true; } html += '<li>' + inline(line.slice(2)) + '</li>'; }
      else { if (list) { html += '</ul>'; list = false; } if (line.trim()) html += '<p>' + inline(line) + '</p>'; }
    });
    if (list) html += '</ul>';
    return html;
  }

  var ICON_EXT = '<svg class="i sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
  var ICON_DRAFT = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4"/></svg>';
  function sourceCard(s) {
    var quotes = s.quotes.map(function (q) { return '<blockquote class="rec" lang="ms">' + esc(q) + '</blockquote>'; }).join('');
    return '<li class="card src" id="src-' + s.n + '"><div class="top"><span class="num">' + s.n + '</span><div><div class="cl">' + esc(s.cite) + '</div>' +
      (s.draft ? '<div class="draft">' + ICON_DRAFT + 'Unrevised draft</div>' : '') + '</div></div>' +
      '<div class="quotes"><span class="label-rec">Verbatim from Hansard</span>' + quotes + '</div>' +
      '<div class="links"><a class="linkbtn" href="debate.html">Open the debate</a><a class="linkbtn" href="' + s.pdf + '" target="_blank" rel="noopener">Official PDF ' + ICON_EXT + '</a></div></li>';
  }

  var running = null;
  function run(fast) {
    if (running) return running;
    running = new Promise(function (resolve) {
      input.value = D.question;
      clearInterval(rot);
      out.hidden = false;
      var text = $('#answer-text'), list = $('#src-list'), srcWrap = $('#sources'), foot = $('#answer-foot'), fold = $('#how');
      text.innerHTML = ''; list.innerHTML = ''; srcWrap.hidden = true; foot.hidden = true; fold.hidden = true;
      $('#q-echo-text').textContent = D.question;
      $('#answer-card').setAttribute('aria-busy', 'true');
      if (!fast) out.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      var tokens = D.answer.split(/(\s+)/), i = 0, acc = '';
      var step = fast ? 3 : 1, delay = fast ? 16 : 42;
      function tick() {
        var n = 0;
        while (i < tokens.length && n < step * 2) { acc += tokens[i++]; n++; }
        text.innerHTML = md(acc) + (i < tokens.length ? '<span class="caret" aria-hidden="true"></span>' : '');
        if (i < tokens.length) { setTimeout(tick, delay * (fast ? 1 : 1)); return; }
        finish();
      }
      function finish() {
        $('#answer-card').setAttribute('aria-busy', 'false');
        text.innerHTML = md(D.answer);
        foot.hidden = false;
        srcWrap.hidden = false;
        var k = 0;
        function addSrc() {
          if (k >= D.sources.length) { fold.hidden = false; running = null; resolve(); return; }
          list.insertAdjacentHTML('beforeend', sourceCard(D.sources[k++]));
          if (fast) addSrc(); else setTimeout(addSrc, 110);
        }
        addSrc();
      }
      tick();
    });
    return running;
  }
  window.demoAnswer = function () { return run(true); };
  form.addEventListener('submit', function (e) { e.preventDefault(); run(false); });
  $$('[data-example]').forEach(function (b) {
    b.addEventListener('click', function () { run(false); });
  });

  /* citation preview: hover on desktop, tap or Enter elsewhere */
  var peek = $('#peek'), cur = null, closeT = null;
  function place(btn) {
    var r = btn.getBoundingClientRect(), w = peek.offsetWidth, h = peek.offsetHeight;
    var left = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 12));
    var top = r.bottom + 10;
    if (top + h > window.innerHeight - 12) top = Math.max(12, r.top - h - 10);
    peek.style.left = left + 'px'; peek.style.top = top + 'px';
  }
  function openPeek(btn) {
    var s = D.sources[+btn.getAttribute('data-n') - 1];
    if (!s) return;
    if (cur && cur !== btn) cur.setAttribute('aria-expanded', 'false');
    cur = btn; btn.setAttribute('aria-expanded', 'true');
    $('.cl-t', peek).textContent = s.cite; $('.num', peek).textContent = s.n;
    $('.rec', peek).textContent = s.quotes[0];
    $('.go', peek).setAttribute('data-n', s.n);
    peek.hidden = false; place(btn);
  }
  function closePeek() { peek.hidden = true; if (cur) cur.setAttribute('aria-expanded', 'false'); cur = null; }
  function jump(n) {
    closePeek();
    var el = document.getElementById('src-' + n);
    if (!el) return;
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    el.classList.add('flash'); setTimeout(function () { el.classList.remove('flash'); }, 1600);
  }
  document.addEventListener('click', function (e) {
    var c = e.target.closest('.cite');
    if (c) { if (cur === c && !peek.hidden) closePeek(); else openPeek(c); return; }
    if (e.target.closest('.go')) { jump(e.target.closest('.go').getAttribute('data-n')); return; }
    if (!peek.contains(e.target)) closePeek();
  });
  document.addEventListener('mouseover', function (e) {
    var c = e.target.closest && e.target.closest('.cite');
    if (c && window.matchMedia('(hover: hover)').matches) { clearTimeout(closeT); openPeek(c); }
  });
  document.addEventListener('mouseout', function (e) {
    if (!window.matchMedia('(hover: hover)').matches) return;
    var c = e.target.closest && e.target.closest('.cite, .peek');
    if (c) { closeT = setTimeout(function () { if (!peek.matches(':hover') && !(cur && cur.matches(':hover'))) closePeek(); }, 220); }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePeek(); });
  window.addEventListener('scroll', function () { if (cur && !peek.hidden) place(cur); }, { passive: true });
})();
(function () {
  var t = document.getElementById('sum-toggle'); if (!t) return;
  t.addEventListener('click', function () {
    var box = document.getElementById('sum'), open = !box.classList.contains('open');
    box.classList.toggle('open', open); t.setAttribute('aria-expanded', String(open));
    t.querySelector('.t').textContent = open ? 'Show less' : 'Read the whole summary';
  });
})();
