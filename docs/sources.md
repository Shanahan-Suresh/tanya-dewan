# Sources and legal basis

Phase 0 finding for the owner's sign-off. Measured 2026-10-22 unless a line says otherwise. Raw
measurements: `data/phase0/sample.json`, the sitting list `data/sittings.csv` (both git-ignored);
the scripts are `parlimen/sittings.py` and `tools/phase0_sample.py`.

## Copyright

- **Copyright Act 1987 (Act 332), section 3, "karya sastera"**, Malay text, AGC reprint as at
  30 June 2022 (https://www.kpdn.gov.my/images/2024/awam/akta/myipo/Akta%20332.pdf). The Malay
  text is authoritative. The definition ends: "tetapi tidak termasuk teks rasmi Kerajaan atau
  badan berkanun, yang bersifat perundangan atau peraturan, atau keputusan kehakiman, atau ucapan
  politik dan debat politik, atau ucapan yang diberikan dalam perjalanan prosiding undang-undang,
  dan terjemahan rasminya".
- English, reconstructed from the 1990 amendment (https://www.wipo.int/wipolex/en/text/128854)
  and the 2012 amendment: "but does not include official texts of the Government or statutory
  bodies of a legislative or regulatory nature, or judicial decisions, or political speeches and
  political debates, or speeches delivered in the course of legal proceedings, and the official
  translation thereof".
- **Reading:** Hansard debates (political speeches and debates) and the text of Acts (official
  texts of a legislative nature) are not literary works, so they carry no copyright as text. The
  footers "Copyright Reserved Parliament of Malaysia" and "All Rights Reserved by Attorney
  General's Chambers" cover the sites and their own compilation and layout. parlimen-search
  therefore republishes extracted text, never the PDFs' page images, and links each official PDF.
- Not legal advice; a lawyer's reading is the stronger basis before any paid product.

## Terms of use

| Site | Terms found | What they say | robots.txt |
|---|---|---|---|
| parlimen.gov.my | `penafian.html` (Disclaimer) | No warranty of completeness or accuracy; no liability. No restriction on reuse | none (404) |
| lom.agc.gov.my | `tnc.php` | No warranty; "Copyright 2023 by Attorney General's Chambers, Malaysia, all rights reserved"; laws "can be accessed and downloaded at no charge"; a print-out is not a copy of the Gazette and is not prima facie evidence of it | server error (500) |
| hansard.parlimen.gov.my (Hansard Digital) | none | None found | none (404) |

Every law page in parlimen-search states that its text is not an official copy and links the
official source, as the LOM terms (items 7 to 10) require.

## Hansard (debates)

- **Listing:** Parliament's Hansard archive is a tree (Parliament > term > meeting > sitting) that
  loads as XML from `hansard-dewan-rakyat.html?uweb=dr&lang=bm&arkib=yes&ajx=1&id=<node>`. The
  meeting in progress is on the plain Hansard page. `parlimen/sittings.py` reads both.
- **Size:** 539 sitting days from 2018-07-16 to 2026-10-20: 262 in the 14th Parliament and 277 in
  the 15th, special meetings ("Mesyuarat Khas") included.
- **Special Chamber (Dewan Khas):** a second Hansard of short sittings, served by
  `hansard-dewan-khas.html` with the same tree and `KKDR-` file names. 494 sitting days from
  2018-07-18 to 2026-10-20 (234 and 260). 2018-11-15 links a file with no name, the one sitting
  with no PDF. 2023-09-05 and 2023-12-08 fall outside the dates of the meeting they are listed
  under: they are swearing-in sittings for by-election winners (Kuala Terengganu, Kemaman), held
  in the Special Chamber between meetings.
- **Parsed corpus** (measured 2026-10-22): 359,904 speeches from 1,032 sittings, 349,114 in the
  Dewan Rakyat and 10,790 in the Special Chamber. 319,312 of 319,484 named speeches resolve to a
  seat or a Senator.
- **Date checks:** the parser reads each sitting's date from the line above "Mesyuarat dimulakan"
  and reports a mismatch with the listing. All 10 mismatches are typos in the PDF's date line (a
  wrong year, day or month, or a date line copied from an earlier sitting); the cover page of
  each agrees with the listing.
- **File names are irregular:** `DR-06102026..pdf`, `DR-09102023.Pindaan20032025.pdf`,
  `DR-15102025 - BDR APRIL - DISEMAK.PM.pdf`. The PDF path comes from the listing, never from the
  date.
- **Format:** born-digital PDFs written in Microsoft Word, with a text layer. Each opens with a
  contents page ("KANDUNGAN" with page numbers per section) and an attendance list ("KEHADIRAN
  AHLI-AHLI PARLIMEN"), then ministers' question time ("WAKTU PERTANYAAN-PERTANYAAN MENTERI"),
  oral questions ("PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"), and motions and bills.
- **Speech layout** (read by `parlimen/hansard.py`): a speech opens with a bold speaker label
  ending in ":" ("Tuan Chan Foong Hin [Kota Kinabalu]:", "Menteri Kesihatan [Datuk Seri Dr.
  ...]:"), and a long label wraps over lines. An oral question opens with its number in bold.
  Headings are bold capitals. Time comes as "■1010" marks and as the clerk's "2.49 ptg." notes.
  The attendance list has three forms by year: "12. YB. Name (Seat)" (2022), "2. Office, Name
  (Seat)" (2026), "2. “ Name [Seat] – PARTY" (2018 to 2021). The Special Chamber prints no list,
  and the first sitting of a Parliament prints a swearing-in roll with no seats. Source typos
  appear in labels: "[Kuala baharu]" for "[Kuala Selangor]" (2022-12-19), "[Dr. Zulkifli bin
  Hasan:]:" (2025-10-29). Labels and lists also spell one name two ways ("Muhyiddin" and
  "Mahiaddin").
- **Drafts and revisions:** every sitting of the meeting in progress is marked "BELUM DISEMAK"
  (not yet revised). Revised versions replace them months later under the same or a changed file
  name: the 2024-03-12 PDF was created 2025-02-10, the 2020-11-26 PDF 2022-01-06. The ingest job
  re-reads the listing, compares each file's name and hash, and re-processes a sitting whose file
  changed. Every record shows whether its text is a draft.
- **Publishing lag** (PDF creation date against sitting date, meeting of October 2026): 7 of 11
  sittings went up the next day, around noon; 2 after 3 days; 2 after 11 and 13 days. The server
  sends no Last-Modified header, so the lag is read from the PDF itself.
- **Also on the site:** oral answers and written answers pages, the order paper, and the members
  list.
- **Hansard Digital** (https://hansard.parlimen.gov.my/) is a Next.js app with internal routes
  (`/api/autocomplete`, `/api/count`), no published API, export or terms. parlimen-search uses the
  official PDFs, which are the authoritative record.

## Bills (the link between debates and Acts)

`bills-dewan-rakyat.html?uweb=dr&lang=bm` lists every bill with its number ("D.R.25/2026"),
title, status, first and second reading dates, who tabled it, the date it passed, and the bill
PDF (`/files/billindex/pdf/<year>/DR/<title>.pdf`), with an archive. The reading dates name the
exact sittings that debated each bill, and the bill PDF carries its explanatory statement.

## Laws of Malaysia Online (Acts)

The portal's Act lists load their rows as an encrypted payload (`{"encrypted": true, ...}`) that
only the portal's own script reads, and every link is a signed token (`processFile.php?token=...`).
The reprint list (`principal.php?type=reprint`) fails for every visitor with a server error (a
missing table, `V_LG_TIMELINE_REPRINT_ONLINE_2025`). parlimen-search never decrypts the payload.
`parlimen/acts.py` drives the installed Chrome, lets the page draw its table, reads the rows a
visitor sees, and fetches each PDF through the same browser session, one every 5 seconds.

The source is the list of updated Acts (`principal.php?type=updated`), measured 2026-10-22:

| Rows | Count |
|---|---|
| Acts listed | 887 |
| In force, with an "As At" date | 753 |
| Repealed ("Repealed by Act 805") | 122 |
| Superseded ("Superseded by Act 793") | 12 |
| English PDFs | 840 |
| Malay PDFs | 749 |
| No PDF at all | 45 (44 repealed or superseded, plus Act 135) |

- **Row shapes.** Each row has an English and a Malay title, in either order. "As At" or
  "Sebagaimana Pada" with a date follows an in-force title, and a repeal note follows a repealed
  one. 44 rows have an unlabelled Malay title and an English PDF only. Act 26 (Legal Aid Act 1971)
  lists two versions; the later one (as at 5 September 2022) is kept.
- **PDF kinds.** An icon marks each PDF as a printed reprint or an online reprint. Both carry the
  consolidated text.
- **Dates.** The "As At" date matches the PDF: the Employment Act 1955 PDF says "As at 1 August
  2023", and a revised Act's PDF says "Revised up to 20 March 2026".
- **No Malay text.** Some Malay PDFs of revised Acts are one cover page that says "Tiada teks
  bahasa kebangsaan" (no national-language text). The parser marks these Acts English only.
- **Repealed Acts.** Their PDFs are short repeal notices. They are kept, because the 14th
  Parliament debates name Acts it repealed (the Goods and Services Tax Act 2014, Act 762).
- **Files the portal cannot serve.** Three links (Act 781 Malay, Acts 175 and 150 English) return
  status 200 with nginx's "500 Internal Server Error" page instead of a PDF, checked 2026-10-22.
  The other language of each Act is cached. `parlimen/acts.py` retries them on every run.
- **Titles with an asterisk** ("*INCOME TAX ACT 1967"): the portal does not say what the mark
  means. The title is stored as listed.
- **What the files hold**, from `parlimen/act_text.py` (measured 2026-10-22):

  | Kind | Files |
  |---|---|
  | Text with sections, from the text layer | 1,368 |
  | Text with sections, from OCR of a scan (mostly Malay reprints of 2006) | 52 |
  | Notice (repealed, superseded, ceased, or without legal force) | 132 |
  | Scan of a repealed Act, not read | 23 |
  | "No Malay text" cover | 8 |
  | The other language's text under this label (Acts 337 and 104 English, 604 Malay) | 3 |

  Act 104's only PDF is labelled English and holds Malay; its sections are kept as Malay.
- **Act 175 is not in force.** The listing shows the Trade Marks Act 1976 in force, but section
  164 of the Trademarks Act 2019 (Act 815) repeals it. Its Malay file is the 1976 text with
  amendments marked by hand, dated the day Act 815 came into force.
- **Scanned files.** `parlimen/act_ocr.py` reads them (method and measurements in its docstring).
  Claude Haiku 5.5 reads each page and Tesseract 5.4 checks it. Where Tesseract gives fewer than
  97% of Haiku's words, Claude Sonnet 5.5 reads the page again and its text is kept. Measured
  2026-10-22 over 52 files: 1,600 pages, 390 of them read again by Sonnet, [amount removed] in all
  ([amount removed] Haiku, [amount removed] Sonnet). Five pages, all faded covers or arrangement pages, have
  Sonnet and Haiku disagreeing (`data/act-ocr-report.csv`, flag `check`). Sections from a scan
  carry `source: "ocr"`.
- **Coverage.** 748 of the 753 in-force Acts have text in at least one language, and 665 in both.
  Without text: Act 175 (above); Act 811 (its link serves Act 714's repeal notice); Act 756 (a
  Gazette notice that it has no force of law, Act 775 replaced it); Act 437 (a notice that Act
  865 superseded it); and Act 135 and the Malaysia Act (no PDF).

Other sources were checked and rejected: a December 2023 copy on Hugging Face
(`mesolitica/crawl-lom-agc-gov-my`, no licence, kept for cross-checks only), and an open-source
scraper that decrypts the listing with the key the page ships. No bulk download, API or open-data
release from AGC exists.

## Size and cost

Token counts from the Claude token-counting endpoint (Haiku 5.5 and Sonnet 5.5 count the same):

| Sitting | Pages | Characters | Tokens |
|---|---|---|---|
| 2018-07-16 (opening day, short) | 28 | 50,171 | 31,026 |
| 2020-11-26 | 101 | 345,180 | 185,771 |
| 2022-03-23 | 96 | 299,315 | 159,428 |
| 2024-03-12 | 99 | 337,517 | 173,565 |
| 2026-10-20 | 175 | 403,915 | 207,294 |

Special Chamber sittings, five days spread over the list (`tools/phase0_sample.py KK`):

| Sitting | Pages | Characters | Tokens |
|---|---|---|---|
| 2018-07-18 | 9 | 17,545 | 8,655 |
| 2020-08-10 | 9 | 14,328 | 7,505 |
| 2023-03-07 | 13 | 30,488 | 15,832 |
| 2024-12-05 | 20 | 57,004 | 29,261 |
| 2026-10-20 | 18 | 48,214 | 25,024 |

Malay text runs at about 1.9 characters per token. A full Dewan Rakyat sitting day is 160,000 to
210,000 tokens; at about 170,000 on average, the 539 days hold about 92 million tokens. The 494
Special Chamber days average about 17,000 tokens and add about 8.5 million. The corpus is about
100 million tokens. Enrichment output is estimated at 27 million tokens.

| Enrichment model, Batch API | Input | Output | Total |
|---|---|---|---|
| Haiku 5.5 | about [amount removed] | about [amount removed] | about [amount removed] |
| Sonnet 5.5 | about [amount removed] | about [amount removed] | about [amount removed] |

month and the 14th in the next. Re-processing a revised sitting costs about [amount removed] on Haiku and
[amount removed] on Sonnet.

## Go or no-go

- **Hansard: go** for a public demo, on the owner's sign-off of the copyright reading above.
- **Acts: go** on the same sign-off. The texts come from the portal in Chrome, as a visitor gets
  them. The LOM terms allow download at no charge and say a print-out is not a Gazette copy, so
  every Act answer shows the date and the not-legal-advice line.
