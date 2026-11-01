Your task is to convert the provided text, which contains a course schedule or syllabus, into a CSV file. The CSV file should capture all important events, including lectures, exams, quizzes, homework assignments, project deadlines, and lab submissions.

The CSV file must contain the following columns, in this order:

- Subject: The title of the event. IMPORTANT: The subject must start with the course number (e.g., "CSCI4611 Homework 1").
- Start Date: The date of the event, or the due date of a task (YYYY-MM-DD).
- Start Time (Optional): The start time of an event, or the exact due time of a task (HH:MM, 24-hour). Leave blank for an all-day item.
- End Date (Optional): The last day of the event (YYYY-MM-DD). Leave blank if it is the same as the Start Date.
- End Time (Optional): The end time of an event (HH:MM, 24-hour). Leave blank for tasks and due dates.
- Description: A brief description.
- Alarm (Optional): Reminder time in whole minutes before the event or due time (e.g., 15 for a quiz, 1440 for one day before).
- Categories (Optional): Comma-separated list of categories (e.g., "Quiz, Online", "Homework", "Project").

How rows become calendar entries:

- Start Time and End Time set: an event with that duration (e.g., a lecture or exam).
- Start Time set, End Time blank: a point in time, for tasks with an exact deadline (e.g., "due 11:59 PM" becomes 23:59).
- Start Time blank: an all-day item. Set End Date to make it span several days (e.g., a break).

Only output one row per distinct event. Do not output two rows with the same Subject, Start Date and Start Time.

**CRITICAL: You must strictly adhere to the specified date and time formats (`YYYY-MM-DD` and `HH:MM`) to ensure the program can parse them correctly. Output only the CSV, starting with the header row.**

Example:

```csv
Subject,Start Date,Start Time,End Date,End Time,Description,Alarm,Categories
"CSCI4801 First Day of Class","2025-09-03","14:30","2025-09-03","15:45","Attendance required",60,"Lecture"
"CSCI4801 Syllabus Quiz","2025-09-05","","","","Syllabus Quiz",15,"Quiz, Online"
"CSCI4801 Homework 1 Due","2025-09-12","23:59","","","Complete exercises 1-5 from Chapter 1",1440,"Homework"
"CSCI4801 Fall Break","2025-11-24","","2025-11-25","","No class","","Holiday"
"CSCI4801 Midterm Exam","2025-10-21","14:30","2025-10-21","15:45","In person during class",10080,"Exam"
"CSCI4801 Final Exam","2025-12-18","10:30","2025-12-18","12:30","In person, room TBD",10080,"Exam"
```
