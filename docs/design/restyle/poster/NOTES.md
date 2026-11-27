# Poster

**Idea.** Typography leads. A strict 12-column grid (drawn as faint guides in the heroes), giant condensed numerals and numbered section statements, and flat fields of brand yellow and navy as structure. It reads like a design-studio identity applied to a public record, with no masthead, serif headlines or column rules.

**Type.** Bricolage Grotesque at width 75 to 85, weight 800, uppercase, for headlines and figures. Hanken Grotesk for interface text and the answer. Source Serif 4 only for verbatim record text (speeches, Act passages, quoted commitments).

**Colour.** Navy #0A1F5C and yellow #F5B800 as solid blocks (navy text on yellow, yellow numerals on navy, never yellow text on white). Coalition colours are shared by the seat map, timeline lanes and speech numbers. Dark theme re-tones the navy field and the coalition colours.

**Modern feel.** Oversized numerals, a hemicycle seat map built from squares, thick funnel and timeline bars that draw once, count-ups once, a full-height source reader with highlighted quotes, and crisp 120 to 450 ms transitions. AI text always carries an icon label and sits under or beside the verbatim text.

**Hard on the real site.** Variable-font weight and width axes need a self-hosted font subset to stay light. The hemicycle layout is computed (here at build time) and needs a server-side port. The sticky summary and the log-scale funnel need the real stage events streamed in.

Files: home.html, mp.html, debate.html, style.css, app.js, data.js (extracted from the built demo pages by a one-off script).
