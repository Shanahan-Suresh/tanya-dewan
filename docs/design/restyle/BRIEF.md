# Restyle brief: four looks for Tanya Dewan

Tanya Dewan works and is public as a full-stack portfolio piece. The owner finds its look clean
but not modern or impressive enough. This round builds four new looks for the same three screens.
The owner picks one look, a mix, or none. Each look is a set of working HTML prototypes built to
production quality with real content, judged at real size.

## The product

Tanya Dewan answers questions about Malaysia's principal Acts and the Dewan Rakyat debates
(14th and 15th Parliaments, 2018 to 2026), in English and Malay. Every sentence of an answer cites
an Act section or a speech. Around the search sit about 32,000 record pages: Acts, sittings,
debates, MPs, bills, topics, oral questions and ministers' commitments.

Readers: law and politics students, journalists, policy trackers and curious citizens, often on a
phone. Hiring managers read it too: it is a portfolio piece, so the look must say "skilled
full-stack engineer and designer" in the first five seconds. The tone stays a trustworthy public
record: the verbatim text is the record, and AI-written text is labelled.

## What exists today (read these first)

- Screenshots of today's site: `docs/design/restyle/current/*.png` (1828 px wide).
- Today's built pages, the source of all content: `build/demo/index.html` (home and ask),
  `build/demo/mp/anwar-ibrahim.html` (MP page), `build/demo/debate/DR-2025-02-04-008.html`
  (debate page). Open them in a text editor; copy real text, numbers and names from them.
- Today's CSS and behaviour: `parlimen/web/static/site.css`, `ask.js`, `shell.js`, `debate.js`.
- Chart and map data: `docs/design/enhancements/data.json` (keys: `seats` 222 seats with `bloc`,
  `topics` monthly counts of six topics, `meta` counts, `mp`, `debate`, `bill`).
- The recorded answer to replay: `docs/demo/answers/can-my-employer-cut-my-salary.json` (stage
  events with hits and ms, text events, a done event with sources and passages).
- Settled brand, keep it: the name **Tanya Dewan** and the diamond speech-bubble logo (inline SVG
  in the header of any built page). Navy `#0A1F5C` and yellow `#F5B800` are the brand colours. A
  look may change how much of each it uses, add colours and change the type.
- Looks already tried and rejected, do not repeat: **Console** (a dark analyst terminal with mono
  type everywhere) and **Gazette** (a newspaper of record with serif headlines and rules).

## The three screens (each look builds all three)

1. **Home and Ask** (`home.html`). The ask box is the hero, with example questions in both
   languages. Below: the record in numbers, the 15th Parliament seat map (222 seats coloured by
   coalition), latest sittings, latest commitments, the topic chart. The answer state, run by a
   button and by `window.demoAnswer()`:
   - the search steps with their times and the funnel (how many passages each step kept:
     427,728 speeches and sections, 100 by keyword, 100 by meaning, 196 merged, 20 kept after
     reranking, 3 cited), drawn as the stages arrive;
   - the passages found shown as soon as ranking ends, then the answer text streaming word by
     word with citation marks, then the 3 sources;
   - a citation click opens the source reader: the whole passage with the quoted words marked,
     previous and next, close. `window.demoReader()` runs the answer and opens the reader on
     source 1. Both functions return a promise that resolves when the state is on screen; they
     may skip the delays.
2. **MP page** (`mp.html`), Dato' Seri Anwar bin Ibrahim: name, seats, party history, offices,
   the four counts, the activity grid by month, their seat lit on the seat map, top topics,
   commitments (verbatim quote first, then the labelled AI paraphrase), questions answered.
3. **Debate page** (`debate.html`), DR-2025-02-04-008: heading, sitting date and chamber, the
   debate timeline (each speech a bar in a lane by coalition, width by length), the labelled AI
   summary beside the verbatim speeches, question-answer pairs, commitments, each speaker with
   seat, party, time and PDF page, previous and next items, the speakers lit on the seat map.

Every screen has the header (logo, Ask, Acts, Sittings, Questions, Commitments, MPs, Bills,
Topics, a "Jump to" button with Ctrl K, a light and dark switch, EN and BM) and a footer with
the sources line, the AI line and the not-legal-advice line. The phone layout has the bottom tab
bar that today's site has.

## Fixed rules

- Real content only, copied into the page or a local `data.js` (no fetch from outside the
  folder). No lorem ipsum, no invented numbers. Interface copy in English; record text stays as
  the source prints it (Malay speeches stay Malay).
- AI-written text is always labelled and sits beside or under the verbatim text it came from.
- Draft mark and every status: an icon plus coloured inline text. **Never a rounded pill with a
  coloured dot**, never a pulsing or breathing animation. Motion only where something changes:
  the streaming answer, a chart drawing once, a hover, a page or panel transition, a number
  counting up once.
- No emoji. Icons are inline stroke SVG. No gradient washes, no glassmorphism blobs, no
  left-border accent cards.
- Accessible: real buttons, links and labelled inputs; text contrast 4.5:1 or better, small
  labels included; visible focus rings; 44 px touch targets.
- Phone width 390 px: menus collapse, side panels stack, wide tables scroll in their own box, no
  sideways page scroll.
- Light and dark both designed: `prefers-color-scheme` plus a `data-theme` switch on the root.
- Production stack: server-rendered Jinja with hand-written token CSS, htmx and small vanilla
  scripts. So: plain HTML, CSS and vanilla JS. No React, no component library. Fonts from Google
  Fonts are fine in the prototype (production self-hosts them). Charts in inline SVG.

## Deliverable per look

Folder `docs/design/restyle/<look>/` with `home.html`, `mp.html`, `debate.html` (standalone,
linked to each other by relative links), shared `style.css`, `app.js`, and `data.js` if needed.
Then run `python docs/design/restyle/shoot.py <look>` (from the repo root, with
`.venv/Scripts/python.exe`). Look at every shot yourself at full size, fix what is wrong, and shoot
again until the shots are clean: no sideways scroll, no errors, nothing clipped or overlapping,
both themes readable. Last, write `NOTES.md` (15 lines at most): the idea in two sentences, the
type and colour choices, what makes it feel modern, and what would be hard to build on the real
site.

Work only inside your own folder. Do not edit the site code, other looks, git, or anything else.
