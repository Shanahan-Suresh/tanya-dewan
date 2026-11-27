# Stage

The moments that matter happen on a deep navy stage, and the record sits on light paper. Pages alternate full-width dark and light bands, so each page has a broadcast-style rhythm: hero, numbers, chamber, record, topics.

- Type: Bricolage Grotesque (display, bold, tight) with Inter for text and numbers. No mono, no serif.
- Colour: navy `#07122E` stage, warm paper `#F4F1E8`, brand yellow as the one accent; coalition colours appear only on the stage. Dark mode deepens the paper to ink (`#0E1731`) so two layers still read.
- Modern: the home hero is the Dewan Rakyat hemicycle in fine gold lines, drawn from the 222 real seats, with the ask box at the Speaker's place. The header condenses and the arc fades on scroll.
- Answer: the stage stays dark; the funnel bars narrow as stages arrive, seats light up, the answer streams in large type. Sources, passages and the reader sit on paper.
- MP and debate pages open with a dark band: counted-up numbers and the lit seat, or the full-width speech timeline and lit speakers.
- Hard to build for real: the arc and its seat order need a server-side layout helper; the dark and light bands double the colour tokens to test; the answer stage reflows the page while it streams; the seat lights are an illustration, not a data mapping, and must stay labelled so.
- Prototype shortcuts: nav entries for pages not built point to "#"; header and footer are injected by `app.js`.
