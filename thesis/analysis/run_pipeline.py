#!/usr/bin/env python3
"""Master pipeline runner for the thesis data analysis."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    ("parse_chat.py", "Parsing chat records"),
    ("extract_assessments.py", "Extracting assessment timeline"),
    ("analyze_responses.py", "Analyzing Google Forms responses"),
    ("track_attendance.py", "Tracking attendance and enrollment"),
    ("catalog_gamification.py", "Cataloging gamification modules"),
    ("generate_figures.py", "Generating publication figures"),
]

SCRIPT_DIR = Path(__file__).resolve().parent


def run_script(name, description):
    """Run a single analysis script."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"  Running: {name}")
    print(f"{'='*60}")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / name)],
        capture_output=True, text=True, cwd=str(SCRIPT_DIR),
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}", file=sys.stderr)

    if result.returncode != 0:
        print(f"  WARNING: {name} exited with code {result.returncode}")
        return False
    return True


def generate_report():
    """Generate a summary report."""
    report_path = SCRIPT_DIR / "ANALYSIS_REPORT.md"
    lines = [
        "# Data Analysis Pipeline Report",
        "",
        "## Generated Output Files",
        "",
    ]

    for f in sorted(SCRIPT_DIR.glob("*.csv")):
        size = f.stat().st_size
        lines.append(f"- `{f.name}` ({size:,} bytes)")

    figures_dir = SCRIPT_DIR.parent / "figures"
    if figures_dir.exists():
        lines.append("")
        lines.append("## Generated Figures")
        lines.append("")
        for f in sorted(figures_dir.glob("*")):
            lines.append(f"- `{f.name}` ({f.stat().st_size:,} bytes)")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report_path}")


def main():
    print("=" * 60)
    print("  PhD Thesis Data Analysis Pipeline")
    print("  Korniienko S.S. - Digital History Teaching Methodology")
    print("=" * 60)

    success = 0
    total = len(SCRIPTS)

    for name, desc in SCRIPTS:
        if run_script(name, desc):
            success += 1

    print(f"\n{'='*60}")
    print(f"  Pipeline complete: {success}/{total} scripts succeeded")
    print(f"{'='*60}")

    generate_report()

    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
