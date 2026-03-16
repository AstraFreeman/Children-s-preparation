#!/usr/bin/env python3
"""Track attendance and enrollment from parsed chat data."""

import csv
from pathlib import Path
from collections import defaultdict

PARSED_CHAT = Path(__file__).resolve().parent / "parsed_chat.csv"
OUTPUT_ATTENDANCE = Path(__file__).resolve().parent / "attendance_log.csv"
OUTPUT_ENROLLMENT = Path(__file__).resolve().parent / "enrollment_timeline.csv"


def main():
    if not PARSED_CHAT.exists():
        print("Error: Run parse_chat.py first")
        return

    with open(PARSED_CHAT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    # Enrollment timeline
    enrollments = []
    known_users = set()
    for r in records:
        if r["message_type"] == "join" and r["joined_user"]:
            user = r["joined_user"]
            if user not in known_users and user != "Невідомо":
                known_users.add(user)
                enrollments.append({
                    "timestamp": r["timestamp"],
                    "user": user,
                    "cumulative_count": len(known_users),
                })

    with open(OUTPUT_ENROLLMENT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "user", "cumulative_count"])
        writer.writeheader()
        writer.writerows(enrollments)

    # Absence tracking
    absences = []
    for r in records:
        if r["message_type"] == "absence":
            absences.append({
                "timestamp": r["timestamp"],
                "sender": r["sender"],
                "reason": r["absence_reason"],
                "text": r["text"][:200],
            })

    with open(OUTPUT_ATTENDANCE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "sender", "reason", "text"])
        writer.writeheader()
        writer.writerows(absences)

    # Summary
    reasons = defaultdict(int)
    for a in absences:
        reasons[a["reason"]] += 1

    absence_by_person = defaultdict(int)
    for a in absences:
        absence_by_person[a["sender"]] += 1

    print(f"Enrollment timeline: {len(enrollments)} unique joins")
    print(f"Final enrollment: {len(known_users)} participants")
    print(f"Total absence reports: {len(absences)}")
    print(f"Absence reasons: {dict(sorted(reasons.items(), key=lambda x: -x[1]))}")
    print(f"Top absentees: {dict(sorted(absence_by_person.items(), key=lambda x: -x[1])[:5])}")
    print(f"-> {OUTPUT_ENROLLMENT}")
    print(f"-> {OUTPUT_ATTENDANCE}")


if __name__ == "__main__":
    main()
