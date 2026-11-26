# Redesign brief: three design directions for parlimen-search

The owner finds the site far too plain and asked for modern, interesting designs to choose from.
Each direction is a set of working HTML prototypes of the same three screens, built to production
quality with real content, so the owner can judge them at real size.

## The product

parlimen-search searches Malaysia's principal Acts and the Dewan Rakyat debates (14th and 15th
Parliaments, 2018 to now) together, in English and Malay. A reader asks a question and gets a short
answer in which every sentence cites a source: an Act section or a speech in Hansard. Around the
search sit about 32,000 record pages: each Act, sitting, agenda item (debate), MP, bill and topic,
plus lists of oral questions (joined to the minister's answer) and ministers' commitments.

Readers: law and politics students, journalists who cover Parliament, people at consultancies and
companies who track policy, and curious citizens. Most are on a phone at least part of the time.
The tone is a trustworthy public record, not a startup: the verbatim text is the record, and the
AI-written parts are labelled as such.

## The three screens (each direction builds all three)

1. **Home and Ask** (`home.html`). The search box is the hero. Show:
   - example questions in both languages; filters as chips or a compact panel (Acts or debates,
     Parliament 14 or 15, chamber, date range, party, topic, speaker, Act);
   - **the answer state**: a button or a pre-filled question runs a scripted demo that streams
     the real answer from `data.json` (`answer.answer`) word by word, then shows its sources beside
     or under it. Citation marks `[1]` link to the sources. Sources show the cite line, the
     verbatim quote, the official PDF link, and a draft mark when `draft` is true;
   - "how it was found" (the search stages with hit counts and times from `answer.stages`), and
     the cost, folded away by default;
   - below the fold: latest sittings (with the draft mark where `draft` is 1), latest
     commitments, topics with their counts, and a small chart of the top topics by year
     (`home.topic_trend`). Real numbers from `home.meta` (agenda items, speeches, questions,
     commitments).
2. **MP page** (`mp.html`) for `mp` in `data.json`: name, seat, party by date, offices held
   (`mp.offices`), the four counts, an activity chart by month (`mp.activity_by_month`), top topics,
   recent commitments (verbatim quote first, then the AI paraphrase with its label, deadline and
   amount when present) and recent questions answered (question and answer are AI summaries:
   label them). Links to the debates (`/debate/<unit>`).
3. **Debate page** (`debate.html`) for `debate` in `data.json`: the agenda heading, sitting date and
   chamber, the draft note (the sitting is an unrevised draft: say so plainly near the top), the
   AI summary in a labelled panel beside the verbatim speeches, the question-answer pairs and the
   commitments of this item, each speaker with seat and party, time and PDF page, previous and
   next items. Also show **the bill timeline** from `bill` in `data.json` somewhere it reads
   naturally (a side panel or a section: "This bill in Parliament"), as a vertical timeline of
   its debates by date.

Every screen has the site header (brand, navigation: Ask, Acts, Sittings, Questions,
Commitments, MPs, Bills, Topics; an English or Bahasa Melayu switch) and a footer with the
sources line, the AI line and the not-legal-advice line.

## Fixed rules

- **Real content only**, from `docs/design/data.json`, copied into the page (no fetch at run
  time). No lorem ipsum, no invented numbers. Interface copy in English; record text stays as the
  source prints it (Malay speeches stay Malay).
- **AI-written text is always labelled** ("AI summary", "AI", a small mark) and always sits beside
  or under the verbatim text it came from. The verbatim text must look like the primary record.
- **Draft mark**: an icon plus a coloured inline text label ("Unrevised draft"). **Never a pill
  with a coloured dot**, never a pulsing or breathing animation on any status. Motion only where
  something really changes (the streaming answer, a chart drawing once, a hover).
- No emoji. Icons are inline stroke SVG. No gradient washes, no glassmorphism blobs, no
  left-border accent cards.
- Accessible: real `<button>`, `<a href>`, `<input>` with `<label>`; text contrast 4.5:1 or
  better (also small grey labels); focus rings visible; touch targets 44 px.
- Works at phone width (390 px): menus collapse, side panels stack under the content, wide
  tables scroll in a box, no horizontal page scroll. Check both 1440 px and 390 px.
- Light and dark: support `prefers-color-scheme: dark`, so both themes look designed.
- The production build will be server-rendered Jinja templates with Tailwind (standalone CLI) and
  htmx, plus a small script for the streaming answer. So design with plain HTML and CSS that maps
  to that stack: no React, no component library. In the prototype, Tailwind from
  `https://cdn.tailwindcss.com/3.4.17` is allowed, or hand-written CSS; fonts from Google Fonts;
  charts in inline SVG or hand-drawn canvas (no chart library needed, but
  `https://cdn.jsdelivr.net/npm/chart.js@4.4.7` is allowed).

## Deliverable per direction

A folder `docs/design/<direction>/` with `home.html`, `mp.html`, `debate.html` (each a complete
standalone page, linking to the other two by relative links) and any shared `style.css` or
`app.js`. Screenshots of each page at 1440 px wide (full page) and 390 px wide (first screen) in
`docs/design/<direction>/shots/` as `.png`. A `NOTES.md` of at most 15 lines: the concept in two
sentences, the type and colour choices, and what would be hard to build.
