# csv-to-ics

[中文说明](README.zh-CN.md)

Turn a course syllabus into calendar events you can import into Google Calendar, Apple Calendar or Outlook.

The workflow:

1. Give your syllabus to an LLM (ChatGPT, Claude, …) together with [the prompt](prompts/syllabus_to_csv.md). It returns a CSV of every lecture, quiz, exam and deadline.
2. Run `csv_to_ics.py` on the CSV. It writes one `.ics` file per CSV.
3. Import the `.ics` file into your calendar app.

## Requirements

Python 3.10 or newer.

## Installation

```sh
git clone https://github.com/XingjianWang001/csv-to-ics.git
cd csv-to-ics
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```sh
# Convert one file; the result goes to ./output/demo1001.ics
python csv_to_ics.py examples/demo1001.csv

# Convert every .csv in a folder (subfolders included) into another folder
python csv_to_ics.py input -o output

# Use a different time zone for timed events
python csv_to_ics.py input --tz America/New_York

# Move each CSV into input/processed/ after it converts without errors
python csv_to_ics.py input --move-processed
```

| Option | Default | Meaning |
| --- | --- | --- |
| `input` | (required) | A `.csv` file, or a folder of `.csv` files. A `processed/` subfolder is skipped. |
| `-o`, `--output` | `./output` | Folder for the `.ics` files. The input folder's subfolder layout is kept. |
| `--tz` | `America/Chicago` | [IANA time zone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for rows that have a time. |
| `--move-processed` | off | After a CSV converts with no errors, move it to `processed/` inside the input folder. If a file with that name is already there, `-1`, `-2`, … is added to the name instead of overwriting it. |

Each calendar is named after its CSV file (for example `demo1001`). Apps that support it show that name when you import.

## CSV format

The first row must be this header. Only `Subject` and `Start Date` are required; the other columns may be left blank or left out.

```csv
Subject,Start Date,Start Time,End Date,End Time,Description,Alarm,Categories
```

| Column | Format | Notes |
| --- | --- | --- |
| Subject | text | Event title, e.g. `CSCI4611 Homework 1 Due` |
| Start Date | `YYYY-MM-DD` | |
| Start Time | `HH:MM` (24-hour) | Blank means an all-day item |
| End Date | `YYYY-MM-DD` | Defaults to the Start Date |
| End Time | `HH:MM` (24-hour) | |
| Description | text | |
| Alarm | minutes | Reminder this many minutes before the start, e.g. `1440` = one day |
| Categories | comma-separated | e.g. `Quiz, Online` |

How each row becomes a calendar entry:

| Start Time | End Time | Result | Typical use |
| --- | --- | --- | --- |
| set | set | Event from start to end | Lecture, exam |
| set | blank | Point-in-time event | "Homework due 23:59" |
| blank | blank | All-day event, from Start Date to End Date | Due date with no time, break |

For an all-day item, the alarm counts back from midnight at the start of that day.

See [examples/demo1001.csv](examples/demo1001.csv) and the [`.ics` it produces](examples/demo1001.ics).

### Errors

If a row has a problem (a bad date, an end before the start, a duplicate, …), the tool prints the file name, the line number and the reason, skips that row and still converts the rest. When any row fails, the exit code is 1, and `--move-processed` leaves that CSV where it is so you can fix it and run again. If a whole file cannot be read (not UTF-8, an unclosed quote, missing required columns) or none of its rows convert, no `.ics` is written for it, so an `.ics` from an earlier run is kept.

### Re-importing

Each event gets a UID built from its Subject, Start Date and Start Time, so it stays the same every time you convert. Many calendar apps update the existing event when you import a file with the same UID, instead of adding a duplicate. Behaviour varies by app, though. Google Calendar, for example, may ignore re-imported events it already has. If you change an event's title or start, it gets a new UID and shows up as a new event.

## Development

```sh
pip install -r requirements-dev.txt
pytest
```

## License

[MIT](LICENSE)
