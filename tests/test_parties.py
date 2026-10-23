from parlimen import parties


def sp(member, party, frm="", to="", frm_text="", to_text=""):
    return parties.spell(member, party, frm, to, frm_text, to_text)


def row(*members):
    return {"parliament": 14, "code": "P001", "seat": "Seat", "members": list(members)}


def test_party_name_takes_the_party_inside_a_coalition():
    assert parties.party_name("PH ( PKR )") == "PKR"
    assert parties.party_name("GRS (BERSATU Sabah)") == "BERSATU"
    assert parties.party_name("Ind") == "IND"
    assert parties.party_name("PAS") == "PAS"


def test_clean_resolves_notes_and_drops_citations_and_colour_templates():
    notes = {":1": "Left the party on 1 May 2020."}
    cell = ('[[Ali Abu]]<ref name=":1" group="N" /><ref name=":1" />'
            '<ref>{{Cite news|title=x}}</ref>')
    assert parties.clean(cell, notes) == "Ali Abu (Note: Left the party on 1 May 2020.)"
    assert parties.clean(' bgcolor="{{party color|Malaysian Islamic Party}}" |{{Font color|white|\'\'\'PAS\'\'\'}}', {}) == "PAS"


def test_simple_row_with_a_party_change_and_no_note_has_an_undated_change():
    r = row("Ali Abu | PH ( DAP )")
    assert parties.simple(r, "DAP") == [sp("Ali Abu", "DAP")]
    assert [(s["party"], s["from"], s["to"]) for s in parties.simple(r, "PKR")] == [("PKR", "", "?"), ("DAP", "?", "")]


def test_checked_drops_coalitions_and_dates_not_in_the_row():
    r = row("Ali Abu (Note: left PKR on 24 February 2020, joined BERSATU in August, 2020.) | PN ( BERSATU )")
    keep, dropped = parties.checked(r, [
        sp("Ali Abu", "PH"), sp("Ali Abu", "PKR", to="2020-02-24", to_text="24 February 2020"),
        sp("Ali Abu", "BERSATU", frm="2020-08", frm_text="August 2020"),
        sp("Ali Abu", "PN"), sp("Ali Abu", "IND", frm="2020-03-01", frm_text="1 March 2020")])
    assert [s["party"] for s in keep] == ["PKR", "BERSATU"] and dropped == 3


def test_settle_bounds_by_election_members_and_inserts_the_election_party():
    r = row("Ali Abu since 26 January 2019 | BN ( UMNO )", "Bakar Ali until 30 November 2018 | BN ( MIC )")
    out, _ = parties.settle(r, [sp("Ali Abu", "UMNO"), sp("Bakar Ali", "MIC")], "MIC")
    assert [(s["member"], s["from"], s["to"]) for s in out] == [
        ("Ali Abu", "2019-01-26", ""), ("Bakar Ali", "", "2018-11-30")]
    r = row("Ali Abu (Note: joined PKR on 1 June 2020.) | PKR")
    out, _ = parties.settle(r, [sp("Ali Abu", "PKR", frm="2020-06-01")], "IND")
    assert [(s["party"], s["from"], s["to"]) for s in out] == [("IND", "", "2020-06-01"), ("PKR", "2020-06-01", "")]


def test_settle_drops_ind_inside_an_open_membership_and_merges_a_coalition_move():
    r = row("Ali Abu (Note: expelled from BERSATU on 21 December 2022) | GRS")
    out, _ = parties.settle(r, [sp("Ali Abu", "GRS"), sp("Ali Abu", "BERSATU", to="2022-12-21"),
                                sp("Ali Abu", "IND", frm="2022-12-21")], "BERSATU")
    assert sorted((s["party"], s["to"]) for s in out) == [("BERSATU", "2022-12-21"), ("GRS", "")]
    r = row("Ali Abu (Note: UPKO left PH in November 2025, joined GRS in June 2026) | GRS ( UPKO )")
    out, _ = parties.settle(r, [sp("Ali Abu", "UPKO", to="2025-11"), sp("Ali Abu", "IND", "2025-11", "2026-06"),
                                sp("Ali Abu", "UPKO", frm="2026-06")], "UPKO")
    assert [(s["party"], s["from"], s["to"]) for s in out] == [("UPKO", "", "")]


def test_lookup_by_seat_spelling_and_date(tmp_path):
    path = tmp_path / "parties.csv"
    path.write_text("parliament,code,seat,member,party,from,to,from_text,to_text\n"
                    "14,P064,Ipoh Timor,A,DAP,,,,\n"
                    "14,P047,Nibong Tebal,B,PKR,,2020-02-24,,\n"
                    "14,P047,Nibong Tebal,B,IND,2020-02-24,2020-08-22,,\n"
                    "14,P047,Nibong Tebal,B,BERSATU,2020-08-22,,,\n", encoding="utf-8")
    party = parties.lookup(path)
    assert party(14, "Ipoh Timur", "2019-03-01") == "DAP"
    assert [party(14, "Nibong Tebal", d) for d in ("2019-01-01", "2020-05-01", "2021-01-01")] == ["PKR", "IND", "BERSATU"]
