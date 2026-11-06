"""Convert course-schedule CSV files into iCalendar (.ics) files.

Each CSV row becomes one calendar event. See README.md for the column format.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from icalendar import Alarm, Calendar, Event, Timezone

DEFAULT_TZ = "America/Chicago"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
REQUIRED_COLUMNS = ("Subject", "Start Date")
KNOWN_COLUMNS = ("Subject", "Start Date", "Start Time", "End Date", "End Time", "Description", "Alarm", "Categories")
PROCESSED_DIRNAME = "processed"


class RowError(ValueError):
    """A CSV row that cannot be turned into an event."""


def _parse_date(value: str, column: str) -> date:
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        raise RowError(f"{column} {value!r} is not a valid YYYY-MM-DD date") from None


def _parse_time(day: date, value: str, column: str, tz: ZoneInfo) -> datetime:
    try:
        clock = datetime.strptime(value, TIME_FORMAT).time()
    except ValueError:
        raise RowError(f"{column} {value!r} is not a valid HH:MM time") from None
    return datetime.combine(day, clock, tzinfo=tz)


def make_uid(subject: str, start_date: str, start_time: str) -> str:
    """Build a UID that stays the same across runs, so re-imports can update events."""
    digest = hashlib.sha1(f"{subject}|{start_date}|{start_time}".encode("utf-8")).hexdigest()
    return f"{digest}@csv-to-ics"


def row_to_event(row: dict[str, str], tz: ZoneInfo) -> Event:
    """Turn one CSV row into an Event, raising RowError if the row is invalid."""
    values = {key: value.strip() for key, value in row.items()}
    subject = values.get("Subject", "")
    start_date_str = values.get("Start Date", "")
    start_time_str = values.get("Start Time", "")
    end_date_str = values.get("End Date", "")
    end_time_str = values.get("End Time", "")

    if not subject:
        raise RowError("Subject is empty")
    if not start_date_str:
        raise RowError("Start Date is empty")

    start_date = _parse_date(start_date_str, "Start Date")
    end_date = _parse_date(end_date_str, "End Date") if end_date_str else None

    event = Event()
    event.add("dtstamp", datetime.now(timezone.utc))
    event.add("summary", subject)

    if start_time_str:
        start = _parse_time(start_date, start_time_str, "Start Time", tz)
        if end_time_str:
            end = _parse_time(end_date or start_date, end_time_str, "End Time", tz)
        elif end_date:
            raise RowError("End Date is set but End Time is empty")
        else:
            # A point in time, e.g. "due at 23:59".
            end = start
        if end < start:
            raise RowError("event ends before it starts")
    else:
        if end_time_str:
            raise RowError("End Time is set but Start Time is empty")
        # All-day event; DTEND is exclusive, so it is the day after the last day.
        start = start_date
        end = (end_date or start_date) + timedelta(days=1)
        if end <= start:
            raise RowError("End Date is before Start Date")

    # Built from the parsed values, so 9:00 and 09:00 give the same UID.
    clock = start.strftime(TIME_FORMAT) if start_time_str else ""
    event.add("uid", make_uid(subject, start_date.isoformat(), clock))
    event.add("dtstart", start)
    # DTEND must be later than DTSTART; without it, the event ends when it starts (RFC 5545).
    if end != start:
        event.add("dtend", end)

    description = values.get("Description", "")
    if description:
        event.add("description", description)

    categories = [c.strip() for c in values.get("Categories", "").split(",") if c.strip()]
    if categories:
        event.add("categories", categories)

    alarm_str = values.get("Alarm", "")
    if alarm_str:
        try:
            minutes = int(alarm_str)
        except ValueError:
            minutes = -1
        if minutes < 0:
            raise RowError(f"Alarm {alarm_str!r} is not a non-negative whole number of minutes")
        try:
            trigger = timedelta(minutes=-minutes)
        except OverflowError:
            raise RowError(f"Alarm {alarm_str!r} is too large") from None
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", subject)
        alarm.add("trigger", trigger)
        event.add_component(alarm)

    return event


def convert_csv(csv_path: Path, tz: ZoneInfo) -> tuple[Calendar, list[str]]:
    """Read a CSV file and return its calendar plus a list of error messages.

    Invalid rows are skipped and reported; valid rows are still converted.
    """
    calendar = Calendar()
    calendar.add("prodid", "-//csv-to-ics//EN")
    calendar.add("version", "2.0")
    calendar.calendar_name = csv_path.stem
    errors: list[str] = []
    seen_uids: dict[str, int] = {}

    # utf-8-sig tolerates the byte-order mark that Excel adds.
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        # Not DictReader: it skips blank lines unseen, which hides the line a row starts on.
        reader = csv.reader(f, strict=True)
        next_line = 1  # where the row being read starts; a csv.Error's line_num is wherever the parser gave up
        try:
            header = next((cells for cells in reader if any(c.strip() for c in cells)), [])  # skip leading blank lines
            fieldnames = [name.strip() for name in header]
            while fieldnames and not fieldnames[-1]:  # spreadsheet apps may add trailing commas
                fieldnames.pop()
            missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
            if missing:
                errors.append(f"{csv_path}: missing required column(s): {', '.join(missing)}")
                return calendar, errors
            # A misspelled column would be ignored, silently turning e.g. an exam into an all-day event.
            unknown = [repr(c) for i, c in enumerate(fieldnames) if c not in KNOWN_COLUMNS or c in fieldnames[:i]]
            if unknown:
                errors.append(
                    f"{csv_path}: unknown or repeated column(s): {', '.join(unknown)} "
                    f"(expected {', '.join(KNOWN_COLUMNS)})"
                )
                return calendar, errors

            # A quoted cell can span lines, and line_num is the last line read so far.
            next_line = reader.line_num + 1
            for cells in reader:
                line, next_line = next_line, reader.line_num + 1
                if any(c.strip() for c in cells[len(fieldnames):]):
                    errors.append(f"{csv_path}:{line}: more cells than columns; quote values that contain commas")
                    continue
                row = dict(zip(fieldnames, cells))
                if not any(value.strip() for value in row.values()):
                    continue
                try:
                    event = row_to_event(row, tz)
                except (RowError, OverflowError) as exc:  # e.g. 9999-12-31 has no next day
                    errors.append(f"{csv_path}:{line}: {exc}")
                    continue
                uid = str(event["uid"])
                if uid in seen_uids:
                    errors.append(
                        f"{csv_path}:{line}: duplicate of line {seen_uids[uid]} "
                        "(same Subject, Start Date and Start Time)"
                    )
                    continue
                seen_uids[uid] = line
                calendar.add_component(event)
        except UnicodeDecodeError:
            # e.g. Excel's plain "CSV" on Chinese Windows is GBK.
            errors.append(f"{csv_path}: file is not UTF-8; re-save it as \"CSV UTF-8\"")
            return Calendar(), errors  # no events, so main() keeps the old .ics
        except csv.Error as exc:  # e.g. a quote that is never closed
            errors.append(
                f"{csv_path}:{next_line}: not valid CSV ({exc}); check this row for an unclosed quote, "
                'or a quote inside a quoted value that is not doubled ("")'
            )
            return Calendar(), errors

    days = [d.date() if isinstance(d, datetime) else d for e in calendar.events for d in (e.start, e.end)]
    # shortcut: icalendar overflows when last_date is within ~2 months of date.max, so cap at 9999-01-01.
    calendar.add_missing_timezones(
        first_date=min([Timezone.DEFAULT_FIRST_DATE, *days]),
        last_date=min(max([Timezone.DEFAULT_LAST_DATE, *days]), date(9998, 12, 31)) + timedelta(days=1),
    )
    return calendar, errors


def find_csv_files(input_path: Path) -> list[Path]:
    """List the CSV files to convert, skipping processed/ folders.

    The extension match ignores case, since Excel and other tools often write ".CSV".
    """
    if input_path.is_file():
        return [input_path]
    # Any depth: converting one file archives it next to that file, e.g. fall/processed/.
    return sorted(
        p for p in input_path.rglob("*")
        if p.suffix.lower() == ".csv" and p.is_file()
        and PROCESSED_DIRNAME not in p.relative_to(input_path).parts[:-1]
    )


def unused_path(path: Path) -> Path:
    """Return path, or path with -1, -2, ... added to its stem if that name is taken."""
    candidate = path
    n = 0
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert course-schedule CSV files into .ics calendar files."
    )
    parser.add_argument("input", type=Path, help="a .csv file, or a folder of .csv files")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("output"),
        help="folder to write .ics files to (default: ./output)",
    )
    parser.add_argument(
        "--tz", default=DEFAULT_TZ,
        help=f"IANA time zone for timed events (default: {DEFAULT_TZ})",
    )
    parser.add_argument(
        "--move-processed", action="store_true",
        help="after a CSV converts without errors, move it into a 'processed' folder next to the input",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # A redirected stdout on Windows is e.g. cp1252: printing a Chinese file name must not fail.
    with contextlib.suppress(AttributeError):  # no reconfigure: not a real text stream, or None under pythonw
        sys.stdout.reconfigure(errors="backslashreplace")

    try:
        tz = ZoneInfo(args.tz)
    except (ZoneInfoNotFoundError, ValueError):
        parser.error(f"unknown time zone {args.tz!r} (expected a name like America/Chicago)")
    if not args.input.exists():
        parser.error(f"input {str(args.input)!r} does not exist")

    input_root = args.input if args.input.is_dir() else args.input.parent
    csv_files = find_csv_files(args.input)
    if not csv_files:
        print(f"No .csv files found in {args.input}", file=sys.stderr)
        return 1

    had_errors = False
    written: dict[Path, Path] = {}
    for csv_path in csv_files:
        relative = csv_path.relative_to(input_root)
        output_path = args.output / relative.with_suffix(".ics")
        if output_path in written:
            # e.g. a.csv and a.CSV, which are different files on case-sensitive systems.
            print(
                f"error: {csv_path}: skipped, would overwrite {output_path} "
                f"(already written from {written[output_path]})",
                file=sys.stderr,
            )
            had_errors = True
            continue
        written[output_path] = csv_path

        tmp_path = output_path.with_name(output_path.name + ".tmp")
        try:
            calendar, errors = convert_csv(csv_path, tz)
            for message in errors:
                print(f"error: {message}", file=sys.stderr)
            had_errors = had_errors or bool(errors)
            if not calendar.events:
                # Keep an .ics from an earlier good run rather than replace it with an empty calendar.
                print(f"error: {csv_path}: no events converted, not writing {output_path}", file=sys.stderr)
                had_errors = True
                continue

            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Write a temp file and swap it in, so a failed write never truncates an earlier good .ics.
            tmp_path.write_bytes(calendar.to_ical())
            tmp_path.replace(output_path)
            count = len(calendar.events)
            print(f"{csv_path} -> {output_path} ({count} event{'s' if count != 1 else ''})")

            if args.move_processed and not errors:
                # Never overwrite a CSV archived by an earlier run (e.g. fixed and re-run).
                processed_path = unused_path(input_root / PROCESSED_DIRNAME / relative)
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                # rename, not shutil.move: if it fails (e.g. Excel holds the file), nothing has been copied.
                csv_path.rename(processed_path)
                print(f"moved {csv_path} -> {processed_path}")
        except Exception as exc:  # e.g. an unreadable CSV, a full disk, a CSV Excel holds open: never stop the batch
            print(f"error: {csv_path}: {exc}", file=sys.stderr)
            had_errors = True
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
