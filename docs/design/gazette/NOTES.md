# Gazette: notes

**Concept.** The site reads as a newspaper of record. The answer is a lead article with its sources as numbered footnotes in a right margin; the debate is a transcript with speakers in the margin and the AI summary as a boxed sidebar; the MP is a profile feature with a pull quote from a real commitment.

**Type.** Newsreader (headlines, verbatim record, big numerals) with Inter Tight (labels, interface, tracked uppercase section heads). Tabular lining figures throughout.

**Colour.** Paper #FBFAF6, ink #14130F, one accent chamber green #0B5D3B, warm amber-brown #8A3A00 for the draft mark only, hairline rules with a double rule under the masthead. Night edition: ink-blue #0D1526, warm off-white text, green lifted to #56C08F. Follows the system setting; the button in the masthead overrides it.

**Charts.** Ink lines and bars on hairline grids, the peak in green. Six-topic trend and per-year activity are small multiples on one shared scale. They draw once on load.

**Built as.** Plain HTML and CSS (no framework), one `app.js` for menu, theme and the scripted answer. `window.demoAnswer()` streams fast; a click streams at reading speed. Pages were generated from `data.json` by a script that is not kept here, so the HTML holds copied content.

**Hard to build.** Sources revealing in the margin as each `[n]` is cited needs the streaming script to know the citations in advance. The margin must stay beside the answer on desktop and fall under it on a phone. The debate grid reorders three blocks (summary, transcript, bill) between desktop and phone. Hansard hard-wraps lines, so the transcript text needs the parser's paragraph breaks. The bill panel shows a bill unrelated to the sample debate, since the data has none linked.
