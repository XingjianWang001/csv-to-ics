from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

import csv_to_ics

TZ = ZoneInfo("America/Chicago")
HEADER = "Subject,Start Date,Start Time,End Date,End Time,Description,Alarm,Categories\n"


def write_csv(path: Path, *rows: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def event_from(**row):
    return csv_to_ics.row_to_event(row, TZ)


def test_timed_event():
    event = event_from(**{
        "Subject": "CS101 Lecture", "Start Date": "2026-09-08", "Start Time": "10:00",
        "End Date": "2026-09-08", "End Time": "11:15",
    })
    assert event.decoded("dtstart") == datetime(2026, 9, 8, 10, 0, tzinfo=TZ)
    assert event.decoded("dtend") == datetime(2026, 9, 8, 11, 15, tzinfo=TZ)


def test_end_date_defaults_to_start_date():
    event = event_from(**{
        "Subject": "CS101 Lecture", "Start Date": "2026-09-08", "Start Time": "10:00",
        "End Time": "11:15",
    })
    assert event.decoded("dtend") == datetime(2026, 9, 8, 11, 15, tzinfo=TZ)


def test_all_day_event():
    event = event_from(**{"Subject": "CS101 HW1 Due", "Start Date": "2026-09-18"})
    assert event.decoded("dtstart") == date(2026, 9, 18)
    assert event.decoded("dtend") == date(2026, 9, 19)


def test_multi_day_all_day_event():
    event = event_from(**{
        "Subject": "CS101 Break", "Start Date": "2026-10-19", "End Date": "2026-10-20",
    })
    assert event.decoded("dtstart") == date(2026, 10, 19)
    assert event.decoded("dtend") == date(2026, 10, 21)


@pytest.mark.parametrize("end_time", ["", "23:59"])
def test_point_in_time_event_has_no_dtend(end_time):
    event = event_from(**{
        "Subject": "CS101 HW1 Due", "Start Date": "2026-09-18", "Start Time": "23:59",
        "End Time": end_time,
    })
    assert event.decoded("dtstart") == datetime(2026, 9, 18, 23, 59, tzinfo=TZ)
    assert "dtend" not in event  # RFC 5545: DTEND must be later than DTSTART


def test_alarm_description_and_categories():
    event = event_from(**{
        "Subject": "CS101 Quiz", "Start Date": "2026-09-11", "Description": "Online",
        "Alarm": "1440", "Categories": "Quiz, Online,",
    })
    assert str(event["description"]) == "Online"
    assert [str(c) for c in event["categories"].cats] == ["Quiz", "Online"]
    (alarm,) = event.walk("VALARM")
    assert alarm.decoded("trigger") == timedelta(minutes=-1440)


def test_optional_columns_can_be_missing():
    event = event_from(**{"Subject": "CS101 Quiz", "Start Date": "2026-09-11"})
    assert "description" not in event
    assert "categories" not in event
    assert not event.walk("VALARM")


def test_uid_is_stable():
    row = {"Subject": "CS101 Quiz", "Start Date": "2026-09-11", "Start Time": "10:00"}
    assert event_from(**row)["uid"] == event_from(**row)["uid"]
    assert event_from(**row)["uid"] != event_from(**{**row, "Start Time": "11:00"})["uid"]


# The expected UIDs are what the padded form gave before UIDs ignored padding,
# so calendars that already imported them see the same events.
@pytest.mark.parametrize("start_date, start_time, uid", [
    ("2026-09-08", "09:00", "beff53ebcbf243933d0eb48aeb1db82d51b8a028@csv-to-ics"),
    ("2026-09-08", "9:00", "beff53ebcbf243933d0eb48aeb1db82d51b8a028@csv-to-ics"),
    ("2026-9-8", "09:00", "beff53ebcbf243933d0eb48aeb1db82d51b8a028@csv-to-ics"),
    ("2026-09-08", "", "40a35a0ebee43a783ae1b8a03ae6da23b727c0d5@csv-to-ics"),
    ("2026-9-8", "", "40a35a0ebee43a783ae1b8a03ae6da23b727c0d5@csv-to-ics"),
])
def test_uid_ignores_zero_padding(start_date, start_time, uid):
    row = {"Subject": "CS101 Quiz", "Start Date": start_date, "Start Time": start_time}
    assert event_from(**row)["uid"] == uid


@pytest.mark.parametrize("row, message", [
    ({"Subject": "", "Start Date": "2026-09-11"}, "Subject is empty"),
    ({"Subject": "X", "Start Date": ""}, "Start Date is empty"),
    ({"Subject": "X", "Start Date": "09/11/2026"}, "YYYY-MM-DD"),
    ({"Subject": "X", "Start Date": "2026-02-30"}, "is not a valid YYYY-MM-DD date"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Start Time": "10am"}, "HH:MM"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Start Time": "25:00"},
     "is not a valid HH:MM time"),
    ({"Subject": "X", "Start Date": "2026-09-11", "End Time": "11:00"},
     "Start Time is empty"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Start Time": "10:00",
      "End Date": "2026-09-12"}, "End Time is empty"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Start Time": "10:00",
      "End Time": "09:00"}, "ends before it starts"),
    ({"Subject": "X", "Start Date": "2026-09-11", "End Date": "2026-09-10"},
     "End Date is before Start Date"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Alarm": "soon"}, "Alarm"),
    ({"Subject": "X", "Start Date": "2026-09-11", "Alarm": "-5"}, "Alarm"),
])
def test_invalid_rows(row, message):
    with pytest.raises(csv_to_ics.RowError, match=message):
        csv_to_ics.row_to_event(row, TZ)


def test_convert_csv_skips_bad_rows_and_reports_line_numbers(tmp_path):
    path = write_csv(
        tmp_path / "cs101.csv",
        '"CS101 Quiz","2026-09-11","","","","",15,"Quiz"',
        '"CS101 Bad","not-a-date","","","","","",""',
        ",,,,,,,",
        '"CS101 Quiz","2026-09-11","","","","again","",""',
    )
    calendar, errors = csv_to_ics.convert_csv(path, TZ)
    assert len(calendar.events) == 1
    assert str(calendar["x-wr-calname"]) == "cs101"
    assert len(errors) == 2
    assert errors[0].startswith(f"{path}:3:")
    assert errors[1].startswith(f"{path}:5:") and "duplicate of line 2" in errors[1]


def test_convert_csv_reports_the_first_line_of_multi_line_rows(tmp_path):
    path = write_csv(
        tmp_path / "cs101.csv",
        '"CS101 Quiz","2026-09-11","","","","Bring\na pencil","",""',  # lines 2-3
        '"CS101 Bad","not-a-date","","","","Two\nlines","",""',  # lines 4-5
        "",  # line 6
        '"CS101 Quiz","2026-09-11","","","","again","",""',  # line 7
    )
    _, errors = csv_to_ics.convert_csv(path, TZ)
    assert len(errors) == 2
    assert errors[0].startswith(f"{path}:4:")
    assert errors[1].startswith(f"{path}:7:") and "duplicate of line 2" in errors[1]


def test_convert_csv_reports_out_of_range_values_and_keeps_going(tmp_path):
    path = write_csv(
        tmp_path / "cs101.csv",
        '"CS101 Quiz","2026-09-11","","","","",99999999999999,""',
        '"CS101 Last Day","9999-12-31","","","","","",""',
        '"CS101 Exam","2026-09-12","","","","","",""',
    )
    calendar, errors = csv_to_ics.convert_csv(path, TZ)
    assert [str(event["summary"]) for event in calendar.events] == ["CS101 Exam"]
    assert len(errors) == 2
    assert errors[0].startswith(f"{path}:2:") and "Alarm" in errors[0]
    assert errors[1].startswith(f"{path}:3:")


def test_convert_csv_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Title,Date\nX,2026-09-11\n", encoding="utf-8")
    calendar, errors = csv_to_ics.convert_csv(path, TZ)
    assert not calendar.events
    assert "missing required column(s): Subject, Start Date" in errors[0]


def test_convert_csv_ignores_spaces_around_column_names(tmp_path):
    path = tmp_path / "spaced.csv"
    path.write_text("Subject, Start Date , Start Time\nCS101 Quiz,2026-09-11,10:00\n", encoding="utf-8")
    calendar, errors = csv_to_ics.convert_csv(path, TZ)
    assert errors == []
    assert calendar.events[0].decoded("dtstart") == datetime(2026, 9, 11, 10, 0, tzinfo=TZ)


def test_convert_csv_accepts_utf8_bom(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text(HEADER + '"CS101 Quiz","2026-09-11"\n', encoding="utf-8-sig")
    calendar, errors = csv_to_ics.convert_csv(path, TZ)
    assert errors == []
    assert len(calendar.events) == 1


def test_output_includes_timezone_definition(tmp_path):
    path = write_csv(tmp_path / "cs101.csv", '"CS101 Lecture","2026-09-08","10:00","","11:00"')
    calendar, _ = csv_to_ics.convert_csv(path, TZ)
    parsed = Calendar.from_ical(calendar.to_ical())
    assert [str(tz["tzid"]) for tz in parsed.walk("VTIMEZONE")] == ["America/Chicago"]


def test_main_converts_directory_and_keeps_structure(tmp_path):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "a.csv", '"A Quiz","2026-09-11"')
    write_csv(input_dir / "fall" / "b.csv", '"B Quiz","2026-09-12"')
    write_csv(input_dir / "processed" / "old.csv", '"Old Quiz","2026-01-01"')
    output_dir = tmp_path / "out"

    assert csv_to_ics.main([str(input_dir), "-o", str(output_dir)]) == 0

    assert (output_dir / "a.ics").is_file()
    assert (output_dir / "fall" / "b.ics").is_file()
    assert not (output_dir / "processed").exists()
    assert (input_dir / "a.csv").is_file()  # not moved by default


def test_main_move_processed_only_moves_clean_files(tmp_path):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "good.csv", '"A Quiz","2026-09-11"')
    write_csv(input_dir / "bad.csv", '"B Quiz","oops"')

    exit_code = csv_to_ics.main(
        [str(input_dir), "-o", str(tmp_path / "out"), "--move-processed"]
    )

    assert exit_code == 1
    assert (input_dir / "processed" / "good.csv").is_file()
    assert not (input_dir / "good.csv").exists()
    assert (input_dir / "bad.csv").is_file()


def test_main_single_file(tmp_path):
    path = write_csv(tmp_path / "cs101.csv", '"CS101 Quiz","2026-09-11"')
    assert csv_to_ics.main([str(path), "-o", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "cs101.ics").is_file()


def test_main_rejects_unknown_time_zone(tmp_path):
    path = write_csv(tmp_path / "cs101.csv", '"CS101 Quiz","2026-09-11"')
    with pytest.raises(SystemExit) as exc:
        csv_to_ics.main([str(path), "--tz", "Mars/Olympus"])
    assert exc.value.code == 2


def test_main_move_processed_keeps_existing_archived_file(tmp_path):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "a.csv", '"New Quiz","2026-09-11"')
    archived = write_csv(input_dir / "processed" / "a.csv", '"Old Quiz","2026-01-01"')

    assert csv_to_ics.main([str(input_dir), "-o", str(tmp_path / "out"), "--move-processed"]) == 0

    assert "Old Quiz" in archived.read_text(encoding="utf-8")
    assert "New Quiz" in (input_dir / "processed" / "a-1.csv").read_text(encoding="utf-8")
    assert not (input_dir / "a.csv").exists()


def test_main_finds_uppercase_csv_extension(tmp_path):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "CS101.CSV", '"CS101 Quiz","2026-09-11"')
    output_dir = tmp_path / "out"

    assert csv_to_ics.main([str(input_dir), "-o", str(output_dir)]) == 0

    assert (output_dir / "CS101.ics").is_file()


def test_main_reports_csv_files_that_would_share_an_output_file(tmp_path):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "a.csv", '"Lower Quiz","2026-09-11"')
    write_csv(input_dir / "a.CSV", '"Upper Quiz","2026-09-12"')
    output_dir = tmp_path / "out"

    assert csv_to_ics.main([str(input_dir), "-o", str(output_dir)]) == 1

    ics = (output_dir / "a.ics").read_text(encoding="utf-8")
    assert ("Lower Quiz" in ics) != ("Upper Quiz" in ics)  # one written, the other skipped


def test_main_reports_non_utf8_csv_and_converts_the_rest(tmp_path, capsys):
    input_dir = tmp_path / "input"
    write_csv(input_dir / "a.csv", '"A Quiz","2026-09-11"')
    (input_dir / "b.csv").write_bytes((HEADER + '"作业","2026-09-12"\n').encode("gbk"))  # Chinese Excel default
    write_csv(input_dir / "c.csv", '"C Quiz","2026-09-13"')

    exit_code = csv_to_ics.main([str(input_dir), "-o", str(tmp_path / "out"), "--move-processed"])

    assert exit_code == 1
    assert "not UTF-8" in capsys.readouterr().err
    assert (tmp_path / "out" / "c.ics").is_file()
    assert (input_dir / "b.csv").is_file()  # not archived
