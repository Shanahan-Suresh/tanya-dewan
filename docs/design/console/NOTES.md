# Console: a research instrument for Parliament

**Concept.** The site reads like an analyst terminal: one command-style search bar (Ctrl K or `/`) with typed filter tokens, answers in a split view where hovering a `[n]` mark lights its source, and record pages that behave like dashboards (activity heat grid, big mono counts) or a transcript with a speaker mini-map.

**Type.** IBM Plex Sans for the interface, IBM Plex Mono for figures, IDs, dates and cite lines, IBM Plex Serif only for verbatim record text, so the record is the one serif thing on the page.

**Colour.** Dark-first graphite ground (`#13161b`), hairline borders, one amber signal (`#F2B33D`, draft notes, citation highlight, latest year) and one teal data colour (bars, heat grid, AI labels). Light mode is cool grey paper with darker ink variants of both colours so small text keeps 4.5:1.

**Files.** `home.html`, `mp.html`, `debate.html`, `style.css`, `app.js`. Pages are static; the demo answer is embedded in `home.html` as `window.DEMO` and streams from it. `window.demoAnswer()` runs the fast version.

**Hard to build.**
- Typed filter tokens, the palette and the split view are small scripts, but tokens must round-trip to the server's filter query string and back (htmx plus a little script).
- The heat grid, minimap and per-topic bar charts are plain HTML and inline SVG, easy in Jinja; the speaker minimap's active state needs an IntersectionObserver.
- The streaming answer must render citation marks as links while text arrives (partial `**bold**` handling), and the sources panel needs the cite data before the stream ends.
- Nav links for Acts, Questions, Commitments, Bills and Topics point at the three prototype pages; the BM switch is inert. The sample debate belongs to no bill, so the bill timeline shows the sample bill with a note saying so.
