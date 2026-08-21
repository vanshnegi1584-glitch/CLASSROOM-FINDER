from flask import Flask, render_template, request, jsonify
import csv
from datetime import datetime, time
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

app = Flask(__name__)

@dataclass
class TimetableEntry:
    course: str
    semester: str
    section: str
    subject: str
    day: str
    start_time: time
    end_time: time
    room_number: str
    raw_room: str

@dataclass
class ClassSchedule:
    start_time: time
    end_time: time
    course: str
    semester: str
    section: str
    subject: str

COLLEGE_START = time(8, 0)
COLLEGE_END = time(17, 0)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_MAP = {d.lower(): d for d in WEEKDAYS}

def normalize_room(room: str) -> str:
    if not room:
        return ""
    room = room.strip()
    room = room.replace(" ", "")
    room = room.replace("-", "")
    room = room.replace("(", "")
    room = room.replace(")", "")
    room = room.upper()

    std_match = re.match(r'^(\d+)([A-Z]+)$', room)
    if std_match:
        return std_match.group(1) + std_match.group(2)

    rev_match = re.match(r'^([A-Z]+)(\d+)$', room)
    if rev_match:
        return rev_match.group(2) + rev_match.group(1)

    floor_match = re.search(r'(\d+)(?:RD|TH|ST|ND)?FLOOR', room)
    if floor_match:
        floor = floor_match.group(1)
        base = re.sub(r'\d+(?:RD|TH|ST|ND)?FLOOR', '', room)
        return floor + base

    return room

def parse_time(time_str: str) -> Optional[time]:
    s = time_str.strip().upper().replace(" ", "")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M%p", "%I:%M %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    s = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def get_weekday_from_date(date_str: str) -> Optional[str]:
    dt = parse_date(date_str)
    if dt:
        return WEEKDAYS[dt.weekday()]
    return None

def time_overlaps(req_start: time, req_end: time, booked_start: time, booked_end: time) -> bool:
    return req_start < booked_end and req_end > booked_start

def load_timetable(csv_path: str) -> List[TimetableEntry]:
    entries = []
    seen = set()
    required_cols = {"course", "semester", "section", "subject", "day", "start_time", "end_time", "room_number"}

    path = Path(csv_path)
    if not path.exists():
        return entries

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return entries

        cols = {c.strip().lstrip('\ufeff').lower() for c in reader.fieldnames}
        missing = required_cols - cols
        if missing:
            return entries

        for row in reader:
            if not any(row.values()):
                continue

            row = {k.lstrip('\ufeff'): v for k, v in row.items()}

            try:
                course = row.get("course", "").strip()
                semester = row.get("semester", "").strip()
                section = row.get("section", "").strip()
                subject = row.get("subject", "").strip()
                day = row.get("day", "").strip()
                start_str = row.get("start_time", "").strip()
                end_str = row.get("end_time", "").strip()
                raw_room = row.get("room_number", "").strip()

                if not all([course, semester, section, subject, day, start_str, end_str, raw_room]):
                    continue

                start_time = parse_time(start_str)
                end_time = parse_time(end_str)
                if not start_time or not end_time:
                    continue
                if start_time >= end_time:
                    continue

                day_norm = day.strip().capitalize()
                if day_norm not in WEEKDAYS:
                    continue

                norm_room = normalize_room(raw_room)
                key = (course, semester, section, subject, day_norm, start_str, end_str, norm_room)
                if key in seen:
                    continue
                seen.add(key)

                entries.append(TimetableEntry(
                    course=course,
                    semester=semester,
                    section=section,
                    subject=subject,
                    day=day_norm,
                    start_time=start_time,
                    end_time=end_time,
                    room_number=norm_room,
                    raw_room=raw_room
                ))
            except Exception:
                continue

    entries.sort(key=lambda e: (e.day, e.start_time, e.room_number))
    return entries

def get_all_classrooms(entries: List[TimetableEntry]) -> List[str]:
    rooms = {}
    for e in entries:
        norm = e.room_number
        if norm not in rooms:
            rooms[norm] = e.raw_room
    return sorted(rooms.values(), key=lambda x: normalize_room(x))

def find_free_classrooms(entries: List[TimetableEntry], day: str, req_start: time, req_end: time) -> List[str]:
    day_entries = [e for e in entries if e.day == day]
    occupied_rooms = set()

    for e in day_entries:
        if time_overlaps(req_start, req_end, e.start_time, e.end_time):
            occupied_rooms.add(e.room_number)

    all_rooms = {e.room_number for e in entries}
    free_rooms = all_rooms - occupied_rooms

    room_display = {}
    for e in entries:
        if e.room_number in free_rooms and e.room_number not in room_display:
            room_display[e.room_number] = e.raw_room

    return sorted(room_display.values(), key=lambda x: normalize_room(x))

def merge_intervals(intervals: List[Tuple[time, time]]) -> List[Tuple[time, time]]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged

def get_classroom_free_periods(entries: List[TimetableEntry], room: str, day: str) -> List[Tuple[time, time, str]]:
    norm_room = normalize_room(room)
    room_entries = [e for e in entries if e.room_number == norm_room and e.day == day]
    if not room_entries:
        return []

    room_entries.sort(key=lambda e: e.start_time)

    occupied = [(e.start_time, e.end_time) for e in room_entries]
    occupied = merge_intervals(occupied)

    periods = []
    current = COLLEGE_START

    for start, end in occupied:
        if current < start:
            periods.append((current, start, "FREE"))
        periods.append((start, end, "OCCUPIED"))
        current = end

    if current < COLLEGE_END:
        periods.append((current, COLLEGE_END, "FREE"))

    return periods

def get_classroom_schedule(entries: List[TimetableEntry], room: str, day: str) -> List[ClassSchedule]:
    norm_room = normalize_room(room)
    room_entries = [e for e in entries if e.room_number == norm_room and e.day == day]
    room_entries.sort(key=lambda e: e.start_time)

    return [ClassSchedule(
        start_time=e.start_time,
        end_time=e.end_time,
        course=e.course,
        semester=e.semester,
        section=e.section,
        subject=e.subject
    ) for e in room_entries]

def format_time(t: time) -> str:
    return t.strftime("%I:%M %p").lstrip("0")

ENTRIES = load_timetable("all_courses_combined_timetable.csv")

@app.route("/")
def index():
    classrooms = get_all_classrooms(ENTRIES)
    return render_template("index.html", 
                           classrooms=classrooms, 
                           weekdays=WEEKDAYS)

@app.route("/api/free_rooms", methods=["POST"])
def api_free_rooms():
    data = request.json
    date_str = data.get("date")
    start_str = data.get("start_time")
    end_str = data.get("end_time")

    day = get_weekday_from_date(date_str)
    req_start = parse_time(start_str)
    req_end = parse_time(end_str)

    if not day or not req_start or not req_end or req_start >= req_end:
        return jsonify({"error": "Invalid input"}), 400

    free_rooms = find_free_classrooms(ENTRIES, day, req_start, req_end)
    return jsonify({"rooms": free_rooms, "day": day, "date": date_str})

@app.route("/api/room_periods", methods=["POST"])
def api_room_periods():
    data = request.json
    room = data.get("room")
    date_str = data.get("date")

    day = get_weekday_from_date(date_str)
    if not day:
        return jsonify({"error": "Invalid date"}), 400

    norm_room = normalize_room(room)
    all_rooms = {e.room_number for e in ENTRIES}
    if norm_room not in all_rooms:
        return jsonify({"error": "Room not found"}), 404

    periods = get_classroom_free_periods(ENTRIES, room, day)
    result = [{"start": format_time(s), "end": format_time(e), "status": st} for s, e, st in periods]
    return jsonify({"room": room, "day": day, "periods": result})

@app.route("/api/room_schedule", methods=["POST"])
def api_room_schedule():
    data = request.json
    room = data.get("room")
    date_str = data.get("date")

    day = get_weekday_from_date(date_str)
    if not day:
        return jsonify({"error": "Invalid date"}), 400

    norm_room = normalize_room(room)
    all_rooms = {e.room_number for e in ENTRIES}
    if norm_room not in all_rooms:
        return jsonify({"error": "Room not found"}), 404

    schedule = get_classroom_schedule(ENTRIES, room, day)
    result = [{
        "start": format_time(c.start_time),
        "end": format_time(c.end_time),
        "course": c.course,
        "semester": c.semester,
        "section": c.section,
        "subject": c.subject
    } for c in schedule]
    return jsonify({"room": room, "day": day, "schedule": result})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)