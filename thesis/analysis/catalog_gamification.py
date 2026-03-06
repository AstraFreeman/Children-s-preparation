#!/usr/bin/env python3
"""Catalog HTML game modules from cite_structure/game/."""

import csv
import re
from pathlib import Path
from html.parser import HTMLParser

GAME_DIR = Path(__file__).resolve().parent.parent.parent / "cite_structure" / "game"
OUTPUT_FILE = Path(__file__).resolve().parent / "gamification_catalog.csv"


class GameHTMLParser(HTMLParser):
    """Extract structured info from game HTML files."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.questions = []
        self.current_question = ""
        self.in_question = False
        self.question_count = 0
        self.text_content = []
        self.in_body = False
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag)
        if tag == "title":
            self.in_title = True
        if tag == "body":
            self.in_body = True
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        if "question" in cls.lower():
            self.in_question = True
            self.question_count += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_body:
            self.text_content.append(data.strip())


def parse_game_file(filepath):
    """Parse a single game HTML file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = filepath.read_text(encoding="cp1251")
        except:
            return None

    parser = GameHTMLParser()
    try:
        parser.feed(content)
    except:
        pass

    # Count questions by looking for common patterns
    q_patterns = [
        re.findall(r'class="question', content, re.IGNORECASE),
        re.findall(r'<div[^>]*question[^>]*>', content, re.IGNORECASE),
        re.findall(r'питання|запитання|question', content, re.IGNORECASE),
    ]

    # Extract topic from filename
    # Format: Crstm_S_X_Y.html where X = section, Y = question set
    name = filepath.stem
    parts = name.split("_")

    section = ""
    subsection = ""
    if len(parts) >= 3:
        section = parts[2] if len(parts) > 2 else ""
        subsection = parts[3] if len(parts) > 3 else ""

    # Count interactive elements
    input_count = len(re.findall(r"<input", content, re.IGNORECASE))
    button_count = len(re.findall(r"<button", content, re.IGNORECASE))
    select_count = len(re.findall(r"<select", content, re.IGNORECASE))

    # Try to extract question type
    question_types = set()
    if re.search(r"radio|checkbox", content, re.IGNORECASE):
        question_types.add("multiple_choice")
    if re.search(r"text.*input|input.*text", content, re.IGNORECASE):
        question_types.add("text_input")
    if re.search(r"drag|drop|sortable", content, re.IGNORECASE):
        question_types.add("drag_and_drop")
    if re.search(r"match|відповідність", content, re.IGNORECASE):
        question_types.add("matching")

    # Full text for content analysis
    full_text = " ".join(parser.text_content)

    return {
        "filename": filepath.name,
        "section": section,
        "subsection": subsection,
        "title": parser.title.strip() or name,
        "input_elements": input_count,
        "buttons": button_count,
        "question_types": "; ".join(question_types) if question_types else "unknown",
        "file_size_kb": round(filepath.stat().st_size / 1024, 1),
        "text_length": len(full_text),
    }


def main():
    if not GAME_DIR.exists():
        print(f"Error: Game directory not found: {GAME_DIR}")
        return

    html_files = sorted(GAME_DIR.glob("*.html"))
    if not html_files:
        print("No HTML files found")
        return

    catalog = []
    for f in html_files:
        info = parse_game_file(f)
        if info:
            catalog.append(info)
            print(f"  {info['filename']}: section={info['section']}, "
                  f"inputs={info['input_elements']}, types={info['question_types']}")

    fieldnames = [
        "filename", "section", "subsection", "title",
        "input_elements", "buttons", "question_types",
        "file_size_kb", "text_length",
    ]
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalog)

    sections = set(c["section"] for c in catalog)
    print(f"\nTotal game modules: {len(catalog)}")
    print(f"Sections: {sorted(sections)}")
    print(f"Gamification platform introduced: 2024-12-01")
    print(f"-> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
