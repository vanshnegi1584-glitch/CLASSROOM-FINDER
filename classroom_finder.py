#!/usr/bin/env python3
"""
Free Classroom Finder - Terminal Prototype
Reads timetable CSV files and finds free classrooms.
"""

import csv
import sys
from datetime import datetime, time
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


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


import re

def normalize_room(room: str) -> str:
    """Normalize room number to number-first format (e.g., 406CR, 124LT).
    For descriptive rooms like 'LOGIC LAB (3RD FLOOR)', keep a clean version."""
    if not room:
        return ""
    room = room.strip()
    room = room.replace(" ", "")
    room = room.replace("-", "")
    room = room.replace("(", "")
    room = room.replace(")", "")
    room = room.upper()

    # Check if it's a standard room pattern: number followed by LT/CR/LAB/AUDI etc.
    # Pattern: digits + letters (like 124LT, 406CR, 009LAB)
    std_match = re.match(r'^(\d+)([A-Z]+)$', room)
    if std_match:
        return std_match.group(1) + std_match.group(2)

    # Check if it's letters + digits (like CR406, LT124)
    rev_match = re.match(r'^([A-Z]+)(\d+)$', room)
    if rev_match:
        return rev_match.group(2) + rev_match.group(1)

    # For descriptive rooms (LOGICLAB3RDFLOOR), extract meaningful parts
    # Try to find a floor number
    floor_match = re.search(r'(\d+)(?:RD|TH|ST|ND)?FLOOR', room)
    if floor_match:
        floor = floor_match.group(1)
        # Get the base name (e.g., LOGICLAB)
        base = re.sub(r'\d+(?:RD|TH|ST|ND)?FLOOR', '', room)
        return floor + base

    # Fallback: return cleaned room
    return room


def parse_time(time_str: str) -> Optional[time]:
    """Parse time string with multiple format support."""
    s = time_str.strip().upper().replace(" ", "")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M%p", "%I:%M %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string with multiple format support."""
    s = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def get_weekday_from_date(date_str: str) -> Optional[str]:
    """Get weekday name from date string."""
    dt = parse_date(date_str)
    if dt:
        return WEEKDAYS[dt.weekday()]
    return None


def time_overlaps(req_start: time, req_end: time, booked_start: time, booked_end: time) -> bool:
    """Check if two time intervals overlap."""
    return req_start < booked_end and req_end > booked_start


def load_timetable(csv_paths: List[str]) -> List[TimetableEntry]:
    """Load and combine timetable data from multiple CSV files."""
    entries = []
    seen = set()
    required_cols = {"course", "semester", "section", "subject", "day", "start_time", "end_time", "room_number"}

    for csv_path in csv_paths:
        path = Path(csv_path)
        if not path.exists():
            print(f"Warning: File not found: {csv_path}")
            continue

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print(f"Warning: Empty CSV: {csv_path}")
                continue

            cols = {c.strip().lstrip('\ufeff').lower() for c in reader.fieldnames}
            missing = required_cols - cols
            if missing:
                print(f"Warning: Missing columns in {csv_path}: {missing}")
                continue

            for row_num, row in enumerate(reader, start=2):
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
    """Get sorted unique classroom names (original format)."""
    rooms = {}
    for e in entries:
        norm = e.room_number
        if norm not in rooms:
            rooms[norm] = e.raw_room
    return sorted(rooms.values(), key=lambda x: normalize_room(x))


def get_entries_for_day(entries: List[TimetableEntry], day: str) -> List[TimetableEntry]:
    """Filter entries for a specific day."""
    return [e for e in entries if e.day == day]


def get_entries_for_room_day(entries: List[TimetableEntry], room: str, day: str) -> List[TimetableEntry]:
    """Filter entries for a specific room and day."""
    norm_room = normalize_room(room)
    return [e for e in entries if e.room_number == norm_room and e.day == day]


def find_free_classrooms(entries: List[TimetableEntry], day: str, req_start: time, req_end: time) -> List[str]:
    """Find classrooms completely free during the requested interval."""
    day_entries = get_entries_for_day(entries, day)
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
    """Merge overlapping or adjacent time intervals."""
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
    """Get free/occupied periods for a classroom on a given day."""
    room_entries = get_entries_for_room_day(entries, room, day)
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
    """Get scheduled classes for a classroom on a given day."""
    room_entries = get_entries_for_room_day(entries, room, day)
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


def print_menu():
    print("\n====================================")
    print("       FREE CLASSROOM FINDER")
    print("====================================")
    print("1. Find free classrooms")
    print("2. Check when a classroom is free")
    print("3. View classroom schedule")
    print("4. View all classrooms")
    print("5. Exit")
    print()


def option_find_free(entries: List[TimetableEntry]):
    print("\n--- Find Free Classrooms ---")
    date_str = input("Enter date (DD-MM-YYYY): ").strip()
    day = get_weekday_from_date(date_str)
    if not day:
        print("Invalid date format. Use DD-MM-YYYY.")
        return

    start_str = input("Enter start time (e.g., 1:00 PM or 13:00): ").strip()
    end_str = input("Enter end time (e.g., 2:00 PM or 14:00): ").strip()

    req_start = parse_time(start_str)
    req_end = parse_time(end_str)

    if not req_start or not req_end:
        print("Invalid time format. Use formats like 1:00 PM, 01:00 PM, 13:00, or 13:00:00")
        return
    if req_start >= req_end:
        print("End time must be after start time.")
        return

    free_rooms = find_free_classrooms(entries, day, req_start, req_end)

    print(f"\nAvailable classrooms on {day} ({date_str})")
    print(f"{format_time(req_start)} - {format_time(req_end)}")
    print()

    if free_rooms:
        for i, room in enumerate(free_rooms, 1):
            print(f"{i}. {room}")
        print(f"\nTotal available: {len(free_rooms)}")
    else:
        print("No classrooms available.")


def option_check_free(entries: List[TimetableEntry]):
    print("\n--- Check When Classroom Is Free ---")
    room = input("Enter classroom: ").strip()
    date_str = input("Enter date (DD-MM-YYYY): ").strip()

    day = get_weekday_from_date(date_str)
    if not day:
        print("Invalid date format. Use DD-MM-YYYY.")
        return

    norm_room = normalize_room(room)
    all_rooms = {e.room_number for e in entries}
    if norm_room not in all_rooms:
        print(f"Classroom '{room}' not found in timetable.")
        return

    periods = get_classroom_free_periods(entries, room, day)

    print(f"\n{room} \u2014 {day} ({date_str})")
    print()

    for start, end, status in periods:
        print(f"{format_time(start)} - {format_time(end)}   {status}")


def option_view_schedule(entries: List[TimetableEntry]):
    print("\n--- View Classroom Schedule ---")
    room = input("Classroom: ").strip()
    date_str = input("Date: ").strip()

    day = get_weekday_from_date(date_str)
    if not day:
        print("Invalid date format. Use DD-MM-YYYY.")
        return

    norm_room = normalize_room(room)
    all_rooms = {e.room_number for e in entries}
    if norm_room not in all_rooms:
        print(f"Classroom '{room}' not found in timetable.")
        return

    schedule = get_classroom_schedule(entries, room, day)

    print(f"\n{room} \u2014 {day} ({date_str})")
    print()

    if not schedule:
        print("No classes scheduled.")
        return

    for cls in schedule:
        print(f"{format_time(cls.start_time)} - {format_time(cls.end_time)}")
        print(f"Course: {cls.course}")
        print(f"Semester: {cls.semester}")
        print(f"Section: {cls.section}")
        print(f"Subject: {cls.subject}")
        print()


def option_view_all(entries: List[TimetableEntry]):
    print("\n--- All Classrooms ---")
    rooms = get_all_classrooms(entries)
    for i, room in enumerate(rooms, 1):
        print(f"{i}. {room}")
    print(f"\nTotal classrooms: {len(rooms)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python classroom_finder.py <csv_file1> [csv_file2 ...]")
        print("Example: python classroom_finder.py timetable.csv")
        sys.exit(1)

    csv_files = sys.argv[1:]
    print("Loading timetable data...")
    entries = load_timetable(csv_files)

    if not entries:
        print("No valid timetable data loaded. Exiting.")
        sys.exit(1)

    print(f"Loaded {len(entries)} timetable entries.")
    print(f"Found {len(get_all_classrooms(entries))} unique classrooms.")

    while True:
        print_menu()
        choice = input("Enter choice: ").strip()

        if choice == "1":
            option_find_free(entries)
        elif choice == "2":
            option_check_free(entries)
        elif choice == "3":
            option_view_schedule(entries)
        elif choice == "4":
            option_view_all(entries)
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    main()