import numpy as np

from parlimen import chunk, index, links


def words(texts):
    return [len(t.split()) for t in texts]


def speech(seq, label, text, seat="Seat"):
    return {"seq": seq, "label": label, "text": text, "name": label, "seat": seat, "role": "", "senator": False}


def unit(*speeches, topic="PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"):
    return {"id": "DR-2024-03-12-001", "chamber": "DR", "date": "2024-03-12", "parliament": 15,
            "topic": topic, "speeches": list(speeches)}


def test_short_speeches_share_a_chunk_and_a_long_one_continues_with_overlap():
    long = " ".join(f"Ayat nombor {i} di sini." for i in range(120))  # 120 sentences of 5 words
    u = unit(speech(1, "Tuan A [Seat 1]", "Ya."), speech(2, "Menteri B", long), speech(3, "Tuan A [Seat 1]", "Terima kasih."))
    cs = list(chunk.debate_chunks([u], {}, lambda p, s, d: "PKR", {}, words))
    assert len(cs) > 1 and all(c.tokens <= 400 + 80 for c in cs)
    assert cs[0].text.startswith("Tuan A [Seat 1]: Ya.\n\nMenteri B: Ayat nombor 0")
    assert cs[1].text.startswith("Menteri B (continued): ")
    first_of_second = cs[1].text.split(": ", 1)[1].split(" di sini.")[0]
    assert first_of_second in cs[0].text  # the overlap repeats the end of the first chunk
    assert cs[-1].text.endswith("Tuan A [Seat 1]: Terima kasih.")
    assert cs[0].seq_first == 1 and cs[-1].seq_last == 3
    assert {s["party"] for s in cs[0].speakers} == {"PKR"}


def test_a_split_speech_label_is_not_marked_continued_twice():
    long = " ".join(f"Ayat nombor {i} di sini." for i in range(120))
    u = unit(speech(1, "Menteri B (continued, part 2 of 2)", long))
    cs = list(chunk.debate_chunks([u], {}, lambda p, s, d: "", {}, words))
    assert cs[1].text.startswith("Menteri B (continued, part 2 of 2): ")


def test_debate_header_names_the_linked_act_and_the_note_holds_the_summary():
    u = unit(speech(1, "Menteri B", "Kami akan meminda akta ini. " * 10), topic="RANG UNDANG-UNDANG KERJA (PINDAAN) 2022")
    bills = {"RANG UNDANG-UNDANG KERJA (PINDAAN) 2022": {"act": "265", "act_title_bi": "*EMPLOYMENT ACT 1955"}}
    enriched = {"DR-2024-03-12-001": {"summary_en": "The minister moved the bill.", "topics": ["labour and jobs"]}}
    [c] = chunk.debate_chunks([u], enriched, lambda p, s, d: "", bills, words)
    assert "Bill for the EMPLOYMENT ACT 1955 (Act 265)." in c.header and c.act == "265"
    assert c.note.startswith("Summary (AI): The minister moved the bill.") and c.topics == ["labour and jobs"]


def test_law_chunk_header_in_the_section_language():
    s = {"act": "265", "lang": "BM", "as_at": "2023-01-01", "number": "60A", "heading": "Waktu kerja",
         "part": "Part XII", "part_title": "", "text": "60A. (1) Pekerja tidak boleh bekerja lebih lapan￾jam.",
         "page_start": 9, "page_end": 9}
    acts = {"265": {"title_bi": "*EMPLOYMENT ACT 1955", "title_bm": "*AKTA KERJA 1955", "status": "in force"}}
    [c] = chunk.law_chunks([s], acts, words)
    assert c.header == "AKTA KERJA 1955 (Akta 265), seksyen 60A: Waktu kerja. Bahagian XII. cetakan semula pada 2023-01-01."
    assert c.key == "law:265:BM:60A"
    assert c.text == "60A. (1) Pekerja tidak boleh bekerja lebih lapan-jam."


def test_bill_names_and_cross_references():
    b = links.bill("RANG UNDANG-UNDANG RANG UNDANG-UNDANG KASTAM (PINDAAN) (NO. 2) 2018 Bacaan Kali Yang Kedua")
    assert (b.base, b.year, b.change) == ("KASTAM", "2018", "amend")
    by_name = {"KASTAM": [{"number": "235", "title_bm": "*AKTA KASTAM 1967", "status": "in force"}]}
    assert links.match(b, by_name)["number"] == "235"
    assert links.bill("USUL MENTERI") is None
    text = "Subject to subsection 13(2) and section 14 of this Act, but not section 5 of the Contracts Act 1950."
    assert links.xrefs(text, "12") == ["13", "14"]
    assert links.xrefs("Tertakluk kepada seksyen 7 Akta ini dan seksyen 9 Akta Kontrak 1950, seksyen 12", "12") == ["7"]


def test_build_append_and_embed_parts(tmp_path):
    law = chunk.Chunk("law", "law:1:BI:2", 0, "Act 1, section 2", "2. See section 3.", 4, act="1", lang="BI", section="2")
    law3 = chunk.Chunk("law", "law:1:BI:3", 0, "Act 1, section 3", "3. Text.", 2, act="1", lang="BI", section="3")
    deb = chunk.Chunk("debate", "debate:U1", 0, "Dewan Rakyat", "Tuan A: Ya.", 2, note="Summary (AI): x.",
                      speakers=[{"name": "A", "seat": "S", "party": "DAP", "role": "", "tokens": 2}], topics=["tax"])
    db = tmp_path / "index.db"
    assert index.build([law, law3, deb], db) == 3
    con = index.connect(db)
    assert [tuple(r) for r in con.execute("SELECT section, to_section FROM xrefs")] == [("2", "3")]
    assert con.execute("SELECT rowid FROM fts_hn WHERE fts_hn MATCH 'summary'").fetchall()[0][0] == 2
    assert con.execute("SELECT COUNT(*) FROM fts_h WHERE fts_h MATCH 'summary'").fetchone()[0] == 0
    con.close()
    assert index.append([deb], db) == (3, 4)

    class Fake:
        calls = 0

        def documents(self, texts, batch_size=32):
            Fake.calls += len(texts)
            return np.ones((len(texts), 4), dtype=np.float32)

    assert index.embed("0.6b", "h", tmp_path, block=3, embedder=Fake()) == 4
    assert index.load_vectors("0.6b", "h", tmp_path).shape == (4, 4)
    Fake.calls = 0
    assert index.embed("0.6b", "hn", tmp_path, block=10, embedder=Fake()) == 4
    assert Fake.calls == 2  # the two law rows have no note: their "h" vectors are copied


def test_rebuild_embeds_only_changed_chunks(tmp_path):
    law = chunk.Chunk("law", "law:1:BI:2", 0, "Act 1, section 2", "2. See section 3.", 4, act="1", lang="BI", section="2")
    law3 = chunk.Chunk("law", "law:1:BI:3", 0, "Act 1, section 3", "3. Text.", 2, act="1", lang="BI", section="3")
    deb = chunk.Chunk("debate", "debate:U1", 0, "Dewan Rakyat", "Tuan A: Ya.", 2, note="Summary (AI): x.")

    class Fake:
        texts = []

        def documents(self, texts, batch_size=32):
            Fake.texts += texts
            return np.random.default_rng(len(Fake.texts)).random((len(texts), 4), dtype=np.float32)

    index.build([law, law3, deb], tmp_path / "index.db")
    for v in ("h", "hn"):
        index.embed("0.6b", v, tmp_path, embedder=Fake())
    old = index.load_vectors("0.6b", "hn", tmp_path)
    Fake.texts = []
    law3.text = "3. New text."
    deb2 = chunk.Chunk("debate", "debate:U2", 0, "Dewan Rakyat", "Tuan B: Tidak.", 2, note="Summary (AI): y.")
    assert index.rebuild([law, law3, deb, deb2], "0.6b", ["h"], tmp_path, embedder=Fake(), block=2) == 8
    # h: the changed section and the new debate; hn (rebuilt because the old build had it): the new debate
    assert [t.split("\n")[-1] for t in Fake.texts] == ["3. New text.", "Tuan B: Tidak.", "Tuan B: Tidak."]
    new = index.load_vectors("0.6b", "hn", tmp_path)
    assert np.array_equal(new[[0, 2]], old[[0, 2]]) and not (tmp_path / "prev").exists()
