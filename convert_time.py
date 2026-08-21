import csv
from datetime import datetime

def convert_to_12hr(time_str):
    """Convert 24-hour time to 12-hour format with AM/PM"""
    try:
        dt = datetime.strptime(time_str, "%H:%M")
        return dt.strftime("%I:%M %p").lstrip("0")
    except:
        return time_str

input_file = "D:\\classroom-finder\\all_courses_combined_timetable.csv"
output_file = "D:\\classroom-finder\\all_courses_combined_timetable.csv"

rows = []
with open(input_file, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    rows.append(header)
    for row in reader:
        row[5] = convert_to_12hr(row[5])
        row[6] = convert_to_12hr(row[6])
        rows.append(row)

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("Converted all times to 12-hour format with AM/PM")