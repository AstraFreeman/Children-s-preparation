#!/usr/bin/env python3
"""Parse Viber/Telegram chat records into structured data."""

import re
import csv
import sys
from pathlib import Path

CHAT_FILE = Path(__file__).resolve().parent.parent.parent / "chat records.txt"
OUTPUT_FILE = Path(__file__).resolve().parent / "parsed_chat.csv"

# Ukrainian month names -> month numbers
MONTH_MAP = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}

MONTH_PATTERN = "|".join(MONTH_MAP.keys())

# Timestamp pattern: [ DD month YYYY р. HH:MM ]
TIMESTAMP_RE = re.compile(
    rf"\[\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})\s+р\.\s+(\d{{1,2}}):(\d{{2}})\s*\]"
)

GOOGLE_FORMS_RE = re.compile(r"https://forms\.gle/\S+")
GOOGLE_DRIVE_RE = re.compile(r"https://drive\.google\.com/\S+")
ZOOM_RE = re.compile(r"https://us\d+web\.zoom\.us/\S+")
WORDWALL_RE = re.compile(r"https://wordwall\.net/\S+")
HISTORY_GAME_RE = re.compile(r"https://astrafreeman\.github\.io/HistoryLikeGame/")
ZNO_RE = re.compile(r"https://zno\.osvita\.ua/\S+")

# Event patterns
JOIN_RE = re.compile(r"Приєднався користувач ⁨(.+?)⁩")
LEAVE_RE = re.compile(r"⁨(.+?)⁩ залишає чат")
REMOVED_RE = re.compile(r"Користувач ⁨(.+?)⁩ видалив ⁨(.+?)⁩")
ADDED_RE = re.compile(r"Користувач ⁨(.+?)⁩ додав вас")
DELETED_MSG_RE = re.compile(r"Повідомлення видалено")

# Content patterns
SEMINAR_RE = re.compile(r"[Сс]емінар\s*(\d+)", re.IGNORECASE)
MODULAR_RE = re.compile(r"[Мм]одульний\s+контроль\s*(\d+)", re.IGNORECASE)
LECTURE_RE = re.compile(r"[Лл]екці[яю]\s*(\d+)", re.IGNORECASE)
FILE_MSG_RE = re.compile(r"Файлове повідомлення\s*%?\s*(.+?)\s*%?$")
VIDEO_MSG_RE = re.compile(r"Відеоповідомлення")
PHOTO_MSG_RE = re.compile(r"Фотоповідомлення")
ABSENCE_RE = re.compile(
    r"(буду відсутн|буде відсутн|не буде|не зможу бути|запізн|"
    r"вимкнули світло|немає світла|зникло світло|"
    r"проблеми з інтернетом|поганий інтернет|інтернету немає|"
    r"сімейними обставинами|захворі|стан здоров)",
    re.IGNORECASE
)

ABSENCE_REASONS = {
    "power_outage": re.compile(r"(вимкнули світло|немає світла|зникло світло)", re.IGNORECASE),
    "internet": re.compile(r"(проблеми з інтернетом|поганий інтернет|інтернету немає)", re.IGNORECASE),
    "family": re.compile(r"сімейними обставинами", re.IGNORECASE),
    "health": re.compile(r"(захворі|стан здоров)", re.IGNORECASE),
    "late": re.compile(r"запізн", re.IGNORECASE),
    "air_raid": re.compile(r"(тривог|повітрян)", re.IGNORECASE),
}


def classify_absence_reason(text):
    for reason, pattern in ABSENCE_REASONS.items():
        if pattern.search(text):
            return reason
    return "unspecified"


def classify_message(sender, text):
    """Classify message type."""
    if JOIN_RE.search(text):
        return "join"
    if LEAVE_RE.search(text):
        return "leave"
    if REMOVED_RE.search(text):
        return "removed"
    if DELETED_MSG_RE.search(text):
        return "deleted"
    if ADDED_RE.search(text):
        return "added_to_group"
    if VIDEO_MSG_RE.search(text):
        return "video"
    if PHOTO_MSG_RE.search(text):
        return "photo"
    if FILE_MSG_RE.search(text):
        return "file"
    if MODULAR_RE.search(text):
        return "modular_control"
    if GOOGLE_FORMS_RE.search(text) and SEMINAR_RE.search(text):
        return "seminar_quiz"
    if GOOGLE_FORMS_RE.search(text):
        return "google_form"
    if HISTORY_GAME_RE.search(text):
        return "gamification"
    if WORDWALL_RE.search(text):
        return "gamification"
    if ZNO_RE.search(text):
        return "external_resource"
    if ABSENCE_RE.search(text):
        return "absence"
    return "message"


def parse_chat(filepath):
    """Parse the chat file into structured records."""
    records = []
    current_record = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            ts_match = TIMESTAMP_RE.match(line)
            if ts_match:
                # Save previous record
                if current_record:
                    records.append(finalize_record(current_record))

                day, month_name, year, hour, minute = ts_match.groups()
                month = MONTH_MAP[month_name]
                timestamp = f"{year}-{month:02d}-{int(day):02d} {int(hour):02d}:{int(minute):02d}"

                rest = line[ts_match.end():].strip()

                # Extract sender
                sender_match = re.match(r"⁨(.+?)⁩:\s*(.*)", rest)
                if sender_match:
                    sender = sender_match.group(1)
                    text = sender_match.group(2)
                else:
                    sender = "system"
                    text = rest

                current_record = {
                    "timestamp": timestamp,
                    "sender": sender,
                    "text": text,
                }
            elif current_record:
                # Continuation of previous message
                current_record["text"] += "\n" + line

    if current_record:
        records.append(finalize_record(current_record))

    return records


def finalize_record(record):
    """Add derived fields to a record."""
    text = record["text"]
    sender = record["sender"]

    record["message_type"] = classify_message(sender, text)

    # Extract links
    forms = GOOGLE_FORMS_RE.findall(text)
    record["google_forms_links"] = "; ".join(forms) if forms else ""
    record["google_forms_count"] = len(forms)

    # Seminar number
    sem_match = SEMINAR_RE.search(text)
    record["seminar_number"] = sem_match.group(1) if sem_match else ""

    # Modular control number
    mod_match = MODULAR_RE.search(text)
    record["modular_control_number"] = mod_match.group(1) if mod_match else ""

    # Lecture number
    lec_match = LECTURE_RE.search(text)
    record["lecture_number"] = lec_match.group(1) if lec_match else ""

    # Join event
    join_match = JOIN_RE.search(text)
    record["joined_user"] = join_match.group(1) if join_match else ""

    # Absence reason
    if record["message_type"] == "absence":
        record["absence_reason"] = classify_absence_reason(text)
    else:
        record["absence_reason"] = ""

    return record


def main():
    if not CHAT_FILE.exists():
        print(f"Error: Chat file not found at {CHAT_FILE}")
        sys.exit(1)

    records = parse_chat(CHAT_FILE)

    fieldnames = [
        "timestamp", "sender", "message_type", "text",
        "google_forms_links", "google_forms_count",
        "seminar_number", "modular_control_number", "lecture_number",
        "joined_user", "absence_reason",
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    # Summary
    types = {}
    for r in records:
        t = r["message_type"]
        types[t] = types.get(t, 0) + 1

    total_forms = sum(r["google_forms_count"] for r in records)
    print(f"Parsed {len(records)} messages -> {OUTPUT_FILE}")
    print(f"Total Google Forms links: {total_forms}")
    print(f"Message types: {dict(sorted(types.items(), key=lambda x: -x[1]))}")
    return records


if __name__ == "__main__":
    main()
