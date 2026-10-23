from parlimen import hansard
from parlimen.hansard import Line, Member, attendance, parse_label, parse_sitting
from parlimen.sittings import Sitting

SITTING = Sitting("2025-10-29", "DR", 15, "Penggal Keempat", "Mesyuarat Ketiga", "/x.pdf", "current")


def plain(text, page=1):
    return Line(page, text, "", False)


def bold(text, lead=None, page=1):
    return Line(page, text, text if lead is None else lead, False)


def opening(*body):
    return [plain("Rabu, 29 Oktober 2025"), plain("Mesyuarat dimulakan pada pukul 10.00 pagi"), *body]


def test_attendance_forms_of_each_year():
    lines = [
        plain("12. YB. Dato' Sri Mustapa bin Mohamed (Jeli)"),
        plain("2. Perdana Menteri dan Menteri Kewangan, Dato' Seri Anwar bin"),
        plain("Ibrahim (Tambun)"),
        plain("2. “ Tuan Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai] – PKR"),
        plain("3. Menteri Kewangan II, Senator Datuk Seri Amir Hamzah bin Azizan"),
    ]
    members = attendance(lines)
    assert members["mustapa mohamed"].seat == "Jeli"
    assert members["anwar ibrahim"].seat == "Tambun"
    assert members["ahmad fahmi mohamed fadzil"] == Member("Lembah Pantai", "PKR", False)
    assert members["amir hamzah azizan"].senator


def test_label_forms():
    seats = {"bukit bintang"}
    assert parse_label("Tuan Fong Kui Lun [Bukit Bintang]", seats) == ("", "Tuan Fong Kui Lun", "Bukit Bintang")
    assert parse_label("Menteri Kesihatan [Datuk Seri Dr. Haji Dzulkefly bin Ahmad]", seats) == (
        "Menteri Kesihatan", "Datuk Seri Dr. Haji Dzulkefly bin Ahmad", "")
    assert parse_label("Tuan Yang di-Pertua", seats) == ("Tuan Yang di-Pertua", "", "")
    assert parse_label("Dr. Zulkifli bin Hasan", seats) == ("", "Dr. Zulkifli bin Hasan", "")


def test_attendance_skips_page_furniture_and_closes_at_a_heading():
    members = attendance([
        plain("5. Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama), Senator Puan"),
        plain("DR.11.10.2021 v"),
        plain("Marhamah binti Rosli"),
        bold("PETUGAS-PETUGAS"),
        plain("Nor Yahati binti Awang"),
        plain("1. Rang Undang-undang Kastam (Pindaan) 2021"),
    ])
    assert list(members) == ["marhamah rosli"] and members["marhamah rosli"].senator


def test_chair_seat_in_parentheses_and_initials():
    seats = {"cameron highlands"}
    assert parse_label("Tuan Pengerusi [Dato' Ramli bin Dato' Mohd Nor (Cameron Highlands)]", seats) == (
        "Tuan Pengerusi", "Dato' Ramli bin Dato' Mohd Nor", "Cameron Highlands")
    speeches, _ = parse_sitting(opening(
        bold("Menteri Sumber Manusia [Datuk Seri Saravanan a/l Murugan]: Baik.",
             "Menteri Sumber Manusia [Datuk Seri Saravanan a/l Murugan]:"),
    ), SITTING, {"m saravanan": Member("Tapah", "MIC", False)})
    assert speeches[0].seat == "Tapah"


def test_wrapped_label_and_stray_colon_inside_the_bracket():
    speeches, _ = parse_sitting(opening(
        bold("Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Dr. Zulkifli"),
        bold("bin Hasan:]: Terima kasih Tuan Yang di-Pertua.", "bin Hasan:]:"),
    ), SITTING, {})
    [sp] = speeches
    assert sp.role == "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama)"
    assert sp.name == "Dr. Zulkifli bin Hasan"
    assert sp.text == "Terima kasih Tuan Yang di-Pertua."


def test_speaker_resolved_from_the_register_and_question_number_carried():
    register = {"zaliha mustafa": Member("Titiwangsa", "", False),
                "amir hamzah azizan": Member("", "", True)}
    speeches, rep = parse_sitting(opening(
        bold("PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"),
        bold("1. Tuan Fong Kui Lun [Bukit Bintang] minta Perdana Menteri menyatakan,",
             "1. Tuan Fong Kui Lun [Bukit Bintang]"),
        plain("jumlah gelandangan di Ibu Kota."),
        plain("10.32 pg."),
        bold("Datuk Seri Dr. Zaliha binti Mustafa: Terima kasih.", "Datuk Seri Dr. Zaliha binti Mustafa:"),
        bold("Datuk Seri Amir Hamzah bin Azizan: Baik.", "Datuk Seri Amir Hamzah bin Azizan:"),
        bold("RANG UNDANG-UNDANG KEWANGAN 2025"),
        bold("Tuan Yang di-Pertua: Sila.", "Tuan Yang di-Pertua:"),
    ), SITTING, register)
    question, answer, senator, chair = speeches
    assert question.question_no == answer.question_no == "1"
    assert question.text == "minta Perdana Menteri menyatakan,\njumlah gelandangan di Ibu Kota."
    assert answer.seat == "Titiwangsa" and answer.time == "1032"
    assert senator.senator and not senator.seat
    assert chair.question_no == "" and chair.topic == "RANG UNDANG-UNDANG KEWANGAN 2025"
    assert rep.named == rep.resolved == 3 and rep.date_in_pdf == "2025-10-29"


def test_clock_note_inside_a_sentence_stays_in_the_text():
    speeches, _ = parse_sitting(opening(
        bold("Tuan Yang di-Pertua: Majlis ditangguhkan pada pukul", "Tuan Yang di-Pertua:"),
        plain("2.30 ptg. Saya tangguhkan sehingga"),
        plain("2.30 ptg."),
        bold("Tuan Yang di-Pertua: Sila.", "Tuan Yang di-Pertua:"),
    ), SITTING, {})
    first, second = speeches
    assert first.text.endswith("2.30 ptg. Saya tangguhkan sehingga") and first.time == ""
    assert second.time == "1430"


def test_table_header_after_a_colon_stays_in_the_speech():
    speeches, _ = parse_sitting(opening(
        bold("JAWAPAN-JAWAPAN LISAN"),
        bold("Datuk Seri Dr. Zaliha binti Mustafa: Pecahan adalah seperti berikut:",
             "Datuk Seri Dr. Zaliha binti Mustafa:"),
        bold("NEGERI BILANGAN"),
        plain("Selangor 178 22"),
    ), SITTING, {})
    [sp] = speeches
    assert sp.topic == "JAWAPAN-JAWAPAN LISAN"
    assert "NEGERI BILANGAN" in sp.text


def test_stray_lower_case_word_before_a_heading_goes():
    speeches, _ = parse_sitting(opening(
        bold("researcher PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"),
        bold("Tuan Yang di-Pertua: Sila.", "Tuan Yang di-Pertua:"),
    ), SITTING, {})
    assert speeches[0].topic == "PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"


def test_name_spellings_and_running_heads():
    assert hansard._norm_name("Tan Sri Dato’ Sri Muhyiddin bin Mohd Yassin") == "mahiaddin mohd yassin"
    assert hansard._RUNNING_HEAD.match("DR.23.03.2022 1")
    assert hansard._RUNNING_HEAD.match("4 DR 7.10.2022")
