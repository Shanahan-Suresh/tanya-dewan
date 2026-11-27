# Bento

Every screen is a grid of tiles in three surface tones, each tile a small live view of real data: the ask box is the biggest tile, the seat arc, newest commitment, topic chart, sittings, counts and the "how an answer is found" path sit around it. The answer state replaces the grid with steps and funnel, answer, passages and source tiles, and the reader slides in as a large side panel.

- Type: Geist (400 to 700), tight tracking on headlines, tabular figures for numbers. No mono.
- Colour: navy tile for the ask and identity tiles, one yellow tile for the newest quote, white and two cool-grey tones elsewhere, hairline shadow instead of borders. Dark mode lifts navy to #14338F. Six coalition colours are shared by the seat arc and the debate timeline.
- Modern feel: 24 px radii, large numbers that count up once, lift on hover, legend hover that isolates a coalition or a topic line, charts that draw once, a lit seat in yellow on a dimmed arc.
- Hard on the real site: the tile grid needs per-tile data queries and equal-height tiles at every width; the seat arc and the sticky debate side column are layout code, not templates; the reader panel needs focus handling beyond a plain page.
- Header, footer and the Jump-to list are injected by app.js in this prototype. Only Ask, MPs and Sittings are real pages; other nav links point at the nearest of the three.
