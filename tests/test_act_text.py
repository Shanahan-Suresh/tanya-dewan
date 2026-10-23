from parlimen.act_text import Entry, Line, locate, parse_arrangement


def _lines(*texts: str) -> list[Line]:
    return [Line(1, t) for t in texts]


def _numbers(entries: list[Entry]) -> list[str]:
    return [e.number for e in entries]


# Lines between "ARRANGEMENT OF SECTIONS" and the body, as pdfium reads them.
ARRANGEMENT = _lines(
    "PART I",
    "PRELIMINARY",
    "Section",
    "1. Short title and commencement",
    "2. Interpretation",
    "2b. Power to exempt",
    "PART II",
    "ADMINISTRATION",
    "Chapter 1—Ministerial Direction",
    "3. Power of the Minister to exclude certain persons, geographical areas,",
    "etc.",
    "4-6. (Deleted)",
    "7. Power to amend",
    "Schedule",
    "8. Saving",
    "FIRST SCHEDULE",
    "FORMS",
    "1. Summons to an Accused Person",
    "2. Warrant of Arrest",
)


def test_arrangement_reads_parts_chapters_and_wrapped_headings():
    entries = parse_arrangement(ARRANGEMENT)
    assert _numbers(entries) == ["1", "2", "2B", "3", "4-6", "7", "8"]
    assert entries[0].part == "Part I" and entries[0].part_title == "PRELIMINARY"
    third = entries[3]
    assert third.heading == "Power of the Minister to exclude certain persons, geographical areas, etc."
    assert third.chapter == "Chapter 1" and third.chapter_title == "Ministerial Direction"


def test_arrangement_joins_a_heading_that_wraps_onto_schedule():
    entries = parse_arrangement(ARRANGEMENT)
    assert entries[5].heading == "Power to amend Schedule"


def test_arrangement_skips_the_numbered_forms_of_a_schedule():
    assert "1" not in _numbers(parse_arrangement(ARRANGEMENT))[1:]


def test_arrangement_goes_on_after_a_schedule_between_parts():
    entries = parse_arrangement(_lines(
        "PART II", "CONTRACTS", "10. Saving", "SCHEDULE",
        "PART III", "LIMITATION", "11. Commencement",
    ))
    assert _numbers(entries) == ["10", "11"] and entries[1].part == "Part III"


def test_arrangement_drops_a_headless_repeat_from_overprinted_type():
    entries = parse_arrangement(_lines("1. Short title", "2. Grants", "1.", "2."))
    assert [(e.number, e.heading) for e in entries] == [("1", "Short title"), ("2", "Grants")]


BODY = _lines(
    "Short title",
    "1. This Act may be cited as the Example Act.",
    "Appointment of officers",
    "*2. (1) The Minister may appoint officers.",   # "*" points to a footnote
    "(2) Appointments are published.",
    "PART II",
    "ADMINISTRATION",
    "Provision of mediation services",              # the arrangement says "Provisions of"
    "4. The Director may provide mediation.",
    "Powers",
    "5. The Director has powers.",
    "SCHEDULE",
    "3. Row of a table that is not section 3",
)


def test_locate_finds_sections_by_heading_and_number():
    entries = [Entry("1", "Short title"), Entry("2", "Appointment of officers"),
               Entry("4", "Provisions of mediation services"), Entry("5", "Powers")]
    found = {e.number: (i, how) for e, i, _, how in locate(entries, BODY)}
    assert found == {"1": (1, "exact"), "2": (3, "exact"), "4": (8, "close"), "5": (10, "exact")}


def test_locate_drops_a_stray_number_that_would_hide_later_sections():
    # Section 3 is deleted and absent from the body; the only "3." is a schedule row.
    entries = [Entry("1", "Short title"), Entry("2", "Appointment of officers"), Entry("3", "(Deleted)"),
               Entry("4", "Provisions of mediation services"), Entry("5", "Powers")]
    assert [e.number for e, *_ in locate(entries, BODY)] == ["1", "2", "4", "5"]
