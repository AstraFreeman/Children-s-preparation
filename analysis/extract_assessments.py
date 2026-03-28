#!/usr/bin/env python3
"""Extract assessment timeline from parsed chat data."""

import csv
import re
from pathlib import Path

PARSED_CHAT = Path(__file__).resolve().parent / "parsed_chat.csv"
OUTPUT_FILE = Path(__file__).resolve().parent / "assessment_timeline.csv"


def main():
    if not PARSED_CHAT.exists():
        print("Error: Run parse_chat.py first")
        return

    with open(PARSED_CHAT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    assessments = []
    form_counter = 0

    for r in records:
        if not r["google_forms_links"]:
            continue

        links = r["google_forms_links"].split("; ")
        timestamp = r["timestamp"]
        sender = r["sender"]
        text = r["text"]

        # Determine assessment type
        if r["modular_control_number"]:
            atype = "modular_control"
            number = r["modular_control_number"]
        elif r["seminar_number"]:
            atype = "seminar"
            number = r["seminar_number"]
        elif "вступний тест" in text.lower() or "introductory" in text.lower():
            atype = "intro_test"
            number = "0"
        elif r["lecture_number"]:
            atype = "lecture_quiz"
            number = r["lecture_number"]
        else:
            atype = "other"
            number = ""

        for link in links:
            form_counter += 1
            # Try to extract block name from text
            block_name = ""
            block_patterns = [
                r'Блок\s*["\u201c]?([^"\u201d\n]+)["\u201d]?',
                r'(Частина\s+\S+)',
                r'(Chapter\s+\d+)',
                r'(Part\s+\d+)',
                r'(Блок\s+\S+)',
                r'(Тест\s+\d+)',
            ]
            for pat in block_patterns:
                m = re.search(pat, text)
                if m:
                    block_name = m.group(1).strip()
                    break

            assessments.append({
                "form_id": form_counter,
                "timestamp": timestamp,
                "type": atype,
                "number": number,
                "block_name": block_name,
                "link": link,
                "sender": sender,
            })

    fieldnames = ["form_id", "timestamp", "type", "number", "block_name", "link", "sender"]
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(assessments)

    # Summary
    types = {}
    for a in assessments:
        t = a["type"]
        types[t] = types.get(t, 0) + 1

    seminars = sorted(set(int(a["number"]) for a in assessments if a["type"] == "seminar" and a["number"]))
    modular = sorted(set(int(a["number"]) for a in assessments if a["type"] == "modular_control" and a["number"]))

    print(f"Total assessment forms: {len(assessments)}")
    print(f"Types: {types}")
    print(f"Seminar numbers: {seminars}")
    print(f"Modular controls: {modular}")
    print(f"Date range: {assessments[0]['timestamp']} to {assessments[-1]['timestamp']}")
    print(f"-> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
