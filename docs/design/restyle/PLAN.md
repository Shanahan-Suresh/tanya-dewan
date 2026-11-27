# Plan: move Tanya Dewan to the Stage look

## Context

The owner wants a more modern, impressive look for the portfolio site. Four looks were built as
prototypes (`docs/design/restyle/`, review page https://claude.ai/artifact/XEwd2Di5Px7yPjS6NA2A16).
The owner chose **Stage, with Sharpened's polish on the record pages**:

- Deep navy bands hold the moments that matter: the hero with the chamber in gold lines, the answer
  while it streams, and the debate and MP headers.
- Light paper holds the record (sources, reader, speeches, lists), in Sharpened's calm cards with
  soft depth on a stricter grid.

Engine, routes, features and copy stay. Only the look changes. The prototype sources are
`docs/design/restyle/stage/` (`style.css` 362 lines, `app.js`, `home.html`, `mp.html`,
`debate.html`) and `docs/design/restyle/sharpened/style.css` for card polish.

## Decisions

- **Type:** Bricolage Grotesque (display: headings, big numbers) self-hosted as woff2 latin and
  latin-ext from Google Fonts, with its OFL text, beside the existing Geist (interface and body)
  and Literata (verbatim record text). Stage used Inter for text; Geist stays, because it is
  already self-hosted and close in feel.
- **Colour tokens:** Stage's palette (`#07122E` stage, `#F4F1E8` paper, brand yellow accent) added
  to `site.css` as `--stage-*` and `--paper-*` tokens in the light block and both dark blocks.
  In dark mode the paper deepens to ink (`#0E1731`), so two layers still read. Coalition colours
  `--c-*` and topic colours `--t1..6` are kept and re-tuned for the dark stage where needed.
- **Bands:** a `.band-stage` / `.band-paper` pair of full-width wrappers with an inner `.wrap`.
  Templates choose the band per section. On phones the dark bands stay short (hero, answer,
  page header).
- **Header:** always on the stage, condenses on scroll (Stage `app.js` header code, moved into
  `shell.js`).
- **The lit seats while an answer runs** are an illustration, labelled as such (Stage's caption).

## Steps

1. **Fonts and tokens.** Download Bricolage Grotesque woff2 (latin, latin-ext, weights 500 to 800
   variable) into `parlimen/web/static/fonts/` with `OFL-Bricolage.txt`; add `@font-face` and a
   `--font-display` token. Add the stage and paper tokens in all three theme blocks.
2. **Shell.** `templates/base.html`: dark header, condensing on scroll; footer on the stage. The
   demo banner, jump box, keys sheet and phone tab bar restyled to match.
3. **Home** (`templates/home.html`, `static/ask.js`): a stage hero with the chamber arc in gold
   lines from `present.seat_layout` (server-rendered SVG, no new data), the headline and the ask
   box at the Speaker's place, the record counts under it. The answer area on the stage: steps,
   funnel and streaming answer in large type, seats lighting as stages arrive (labelled
   illustration). Sources, passages, raw stream and the reader on paper. Lower sections (seat
   map, sittings, commitments, topics) alternate paper and stage as in the prototype.
4. **Debate** (`debate.html`, `_macros.debate_timeline`): a stage band with the heading, meta and
   the full-width timeline; speakers lit on the seat map; transcript and summary on paper.
5. **MP** (`member.html`): a stage band with name, seats, counts and the lit seat; the record on
   paper.
6. **Other pages** (acts, act, bills, bill, sittings, sitting, questions, commitments, members,
   topics, topic, how, about, correction, missing, demo_missing): a short stage page header
   (eyebrow, title, lead), the body on paper with Sharpened's cards: one radius scale (8, 14,
   22), layered soft shadows instead of flat borders, hover lift on link cards.
7. **Motion:** numbers count up once, charts draw once, header condenses; all off under
   `prefers-reduced-motion`. No pulsing, no pill-and-dot status.
8. **Tests and demo:** update `tests/test_web.py` where markup or token counts change (the dark
   theme block test, shell elements); run `pytest`; rebuild `tools/static_demo.py` (0 broken
   links).
9. **Check:** shoot every page type with `scratchpad/shoot_site.py` (extended to the list pages)
   at 1828 px and 390 px, light and dark, English and Malay; look at each shot; fix defects;
   compare home, debate and MP against the Stage prototype shots.
10. **Docs:** README shots (`docs/readme/*.webp`) retaken; `PROGRESS.md` Phase 9 ticked;
    `docs/design/BRIEF.md`-style note of the look in PROGRESS decisions.

Commit after the checks pass (owner asked to execute). Push and deploy only when the owner asks.

## Execution

One general-purpose agent builds steps 1 to 8 from this plan, with the prototype folders as the
reference, committing nothing. The main session then runs step 9 (looks at every shot), fixes or
sends back defects, does step 10 and commits.

## Verification

- `pytest` passes; `tools/static_demo.py` reports 0 broken links.
- Shots of home (rest, answer, reader), debate, MP, topics, how-it-works and one list page at
  1828 px and 390 px, light and dark: no sideways scroll, no console errors, text contrast
  readable on both stage and paper.
- The Malay pages show the same layout with Malay strings.
- Side by side with `docs/design/restyle/stage/shots/`, the home, debate and MP first screens
  match the prototype's composition.
