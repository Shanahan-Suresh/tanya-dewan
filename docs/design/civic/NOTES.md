# Civic: notes

**Concept.** A warm, modern public-service product: a navy search panel as the hero, answers as cards with citation marks that preview their source, and the verbatim record always set apart in a serif on a paper surface. Songket-inspired diamond rows (inline SVG) act as quiet dividers and hero texture.

**Type.** Geist for interface and headings (large, tight tracking on display sizes), Literata only for verbatim Hansard text and quotes. AI-written text stays in the sans on a tinted surface with a sparkle "AI" label.

**Colour.** Warm off-white ground, navy #0A1F5C as brand, yellow #F5B800 only as a highlight (headline swatch, Ask button, citation hover, chart peaks, stepper "now"), never as text on white. Dark mode is a navy-black ground, links lift to a pale blue, yellow unchanged. Draft marks use an icon plus text in a dark amber (light) or yellow (dark).

**Layout.** Header nav on desktop, bottom nav with a "More" sheet on phone. Sources sit beside the answer from 1000 px and under it below. The bill stepper is horizontal from 900 px and vertical on phone.

**Hard to build.**
- Citation previews need the cited passages in the page (or an htmx fragment per mark) plus hover and tap handling with viewport clamping.
- The streamed answer needs the server to emit citations as it streams, with partial markdown rendered safely.
- Transcript paragraphs are rebuilt from PDF line wraps by a heuristic; the parser should store real paragraph breaks.
- The bill stepper has only two real stages in the data; a production version needs stage data (first, second, third reading, assent) from the parser.
- Example questions other than the diesel one need their own saved answers; the prototype runs one scripted answer.
