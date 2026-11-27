"""The content of the How it works page: the parts of the system, in the order data flows through
them, and the eval results. Numbers that the records hold come from `Records.meta()` at render
time; the eval rows are ROADMAP.md's results table (Goals, "Results")."""

REPO_BLOB = "https://github.com/Shanahan-Suresh/tanya-dewan/blob/main/"

# Stages in the order data flows: (key, English, Malay).
GROUPS = [("gather", "Gather", "Kumpul"), ("understand", "Understand", "Fahami"), ("find", "Find", "Cari"),
          ("answer", "Answer", "Jawab"), ("serve", "Serve", "Sajikan"), ("check", "Check", "Semak")]

# One part of the system. `n` is the big figure; "{acts}" and the like fill from the records.
# `ai` marks a part that calls Claude. `d` holds (English, Malay) lines; `f` the source files.
NODES = [
    {"g": "gather", "id": "acts", "b": ("Acts", "Akta"), "n": ("{acts} Acts", "{acts} Akta"),
     "s": ("From the Attorney General's Chambers", "Dari Jabatan Peguam Negara"),
     "d": [("{sections} sections, in Malay and English.", "{sections} seksyen, dalam bahasa Melayu dan Inggeris."),
           ("Scanned pages go through OCR, then a text check.", "Halaman imbasan melalui OCR, kemudian semakan teks.")],
     "f": ["parlimen/acts.py", "parlimen/act_text.py", "parlimen/act_ocr.py"]},
    {"g": "gather", "id": "hansard", "b": ("Hansard", "Hansard"), "n": "2018 →",
     "s": ("Every sitting's PDF", "PDF setiap persidangan"),
     "d": [("Each file is fetched once and cached, with a polite rate limit.",
            "Setiap fail diambil sekali dan disimpan, dengan had kadar yang sopan."),
           ("Draft sittings are checked each week until the final copy appears.",
            "Persidangan draf disemak setiap minggu sehingga salinan akhir terbit.")],
     "f": ["parlimen/fetch.py", "parlimen/sittings.py", "parlimen/drafts.py"]},
    {"g": "understand", "id": "parse", "b": ("Parse who spoke", "Kenal pasti penceramah"), "n": ("{speeches} speeches", "{speeches} ucapan"),
     "s": ("Code decides, not AI", "Kod yang menentukan, bukan AI"),
     "d": [("The parser reads speaker lines, seats and times from the PDF text.",
            "Penghurai membaca baris penceramah, kerusi dan masa daripada teks PDF."),
           ("It links each speaker to one of {members} MPs and their party on that date.",
            "Ia memadankan setiap penceramah dengan salah seorang daripada {members} Ahli Parlimen dan partinya pada tarikh itu.")],
     "f": ["parlimen/hansard.py", "parlimen/parties.py", "parlimen/links.py"]},
    {"g": "understand", "id": "enrich", "ai": True, "b": ("Enrich", "Perkaya"), "n": ("{commitments} commitments", "{commitments} komitmen"),
     "s": ("Claude, in one batch run", "Claude, dalam satu larian kelompok"),
     "d": [("{qa} questions joined to the minister's answer.", "{qa} soalan dipadankan dengan jawapan menteri."),
           ("A summary and topic tags for each debate.", "Ringkasan dan tag topik bagi setiap perbahasan."),
           ("A commitment is dropped when its quote is not in the Hansard text.",
            "Komitmen dibuang jika petikannya tiada dalam teks Hansard.")],
     "f": ["parlimen/enrich.py", "parlimen/commit_check.py"]},
    {"g": "find", "id": "kw", "b": ("Keyword index", "Indeks kata kunci"), "n": "BM25",
     "s": ("SQLite full-text search", "Carian teks penuh SQLite"),
     "d": [("Finds exact words, names and section numbers.", "Mencari perkataan, nama dan nombor seksyen yang tepat."),
           ("Malay and English in one index.", "Bahasa Melayu dan Inggeris dalam satu indeks.")],
     "f": ["parlimen/index.py", "parlimen/chunk.py"]},
    {"g": "find", "id": "vec", "b": ("Meaning index", "Indeks makna"), "n": "Qwen3 0.6B",
     "s": ("Embeddings made on this machine", "Benaman dibuat pada mesin ini"),
     "d": [("Finds passages that say the same thing in other words.",
            "Mencari petikan yang menyatakan perkara sama dengan perkataan lain."),
           ("It runs on a CPU at search time.", "Ia berjalan pada CPU semasa carian.")],
     "f": ["parlimen/index.py", "parlimen/models.py"]},
    {"g": "find", "id": "rank", "ai": True, "b": ("Merge and rerank", "Gabung dan susun semula"), "n": "20 → 8",
     "s": ("Rank fusion, then Claude Haiku", "Gabungan pangkat, kemudian Claude Haiku"),
     "d": [("Reciprocal rank fusion merges the two lists.", "Gabungan pangkat salingan menggabungkan dua senarai itu."),
           ("Claude Haiku reads the top 20 and keeps the best 8.", "Claude Haiku membaca 20 teratas dan menyimpan 8 terbaik.")],
     "f": ["parlimen/search.py", "parlimen/llm_rerank.py"]},
    {"g": "answer", "id": "answer", "ai": True, "b": ("Write the answer", "Tulis jawapan"), "n": "SSE",
     "s": ("Streamed to the browser", "Distrim ke pelayar"),
     "d": [("Each sentence must cite a quoted passage.", "Setiap ayat mesti memetik petikan yang disebut."),
           ("It refuses advice on a reader's own case.", "Ia menolak memberi nasihat tentang kes pembaca sendiri."),
           ("The text streams to the page as server-sent events.", "Teks distrim ke halaman sebagai acara pelayan.")],
     "f": ["parlimen/answer.py", "parlimen/web/app.py"]},
    {"g": "serve", "id": "web", "b": ("Website", "Laman web"), "n": "FastAPI",
     "s": ("Jinja and htmx", "Jinja dan htmx"),
     "d": [("{units} debate pages, plus MPs, Acts, bills and topics.",
            "{units} halaman perbahasan, serta Ahli Parlimen, Akta, rang undang-undang dan topik."),
           ("English and Malay, light and dark, phone first.", "Bahasa Inggeris dan Melayu, cerah dan gelap, telefon dahulu.")],
     "f": ["parlimen/web/app.py", "parlimen/records.py"]},
    {"g": "serve", "id": "mcp", "b": ("MCP server", "Pelayan MCP"), "n": "MCP",
     "s": ("Search from an AI assistant", "Cari dari pembantu AI"),
     "d": [("AI assistants can search the Acts and debates as tools.",
            "Pembantu AI boleh mencari Akta dan perbahasan sebagai alat.")],
     "f": ["parlimen/mcp_server.py"]},
    {"g": "serve", "id": "demo", "b": ("Free demo", "Demo percuma"), "n": "GitHub Pages",
     "s": ("No server behind it", "Tiada pelayan di belakangnya"),
     "d": [("Real pages, rendered once.", "Halaman sebenar, dijana sekali."),
           ("Recorded answers play back as streams.", "Jawapan yang dirakam dimainkan semula sebagai strim.")],
     "f": ["tools/static_demo.py", "tools/record_answers.py"]},
    {"g": "check", "id": "eval", "b": ("Evals", "Penilaian"), "n": "5 / 6",
     "s": ("Targets set before the run", "Sasaran ditetapkan sebelum larian"),
     "d": [("A fixed question set, a blind judge and a recall check.",
            "Set soalan tetap, hakim buta dan semakan dapatan semula."),
           ("The results are in the table below.", "Keputusannya dalam jadual di bawah.")],
     "f": ["parlimen/evaluate.py", "parlimen/judge.py", "parlimen/evalset.py"]},
]

# (what was measured, target, result, met) in English and Malay.
EVALS = [
    (("Law questions: the right section is in the top 10", "Soalan undang-undang: seksyen yang betul dalam 10 teratas"),
     ("0.85 or more", "0.85 atau lebih"), "0.907", True),
    (("Debate questions: the right speech is in the top 10", "Soalan perbahasan: ucapan yang betul dalam 10 teratas"),
     ("0.80 or more", "0.80 atau lebih"), "0.727", False),
    (("The same question in Malay and English", "Soalan yang sama dalam bahasa Melayu dan Inggeris"),
     ("under 5 points apart", "beza kurang 5 mata"), "0", True),
    (("Search time on a CPU, 95th percentile", "Masa carian pada CPU, persentil ke-95"),
     ("under 3 s", "kurang 3 s"), "2.83 s", True),
    (("Answers a blind judge marks correct", "Jawapan yang ditanda betul oleh hakim buta"),
     ("65% or more", "65% atau lebih"), "77%", True),
    (("Answers whose every claim has a quoted source", "Jawapan yang setiap dakwaannya ada sumber dipetik"),
     ("80% or more", "80% atau lebih"), "82%", True),
]


def nodes(lang: str, counts: dict) -> list[dict]:
    """The parts of the system in one language, with the counts filled in."""
    k = 1 if lang == "ms" else 0
    nums = {key: f"{int(v):,}" for key, v in counts.items()}

    def fill(s: str) -> str:
        return s.format(**nums) if "{" in s else s

    return [{"g": n["g"], "id": n["id"], "ai": n.get("ai", False), "b": n["b"][k], "n": fill(n["n"] if isinstance(n["n"], str) else n["n"][k]),
             "s": n["s"][k], "d": [fill(x[k]) for x in n["d"]], "f": [(f, REPO_BLOB + f) for f in n["f"]]}
            for n in NODES]


def groups(lang: str) -> list[tuple[str, str]]:
    k = 2 if lang == "ms" else 1
    return [(g[0], g[k]) for g in GROUPS]


def evals(lang: str) -> list[dict]:
    k = 1 if lang == "ms" else 0
    return [{"what": w[k], "target": tg[k], "result": r, "met": m} for w, tg, r, m in EVALS]
