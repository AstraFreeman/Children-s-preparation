#!/usr/bin/env python3
"""Catalog game modules from the HistoryLikeGame platform.

Scans three tiers of content:
  1. Quiz data files   (data/quiz/*.js)        — template-based quiz engine
  2. Falling data files (data/falling/*.js)     — template-based falling engine
  3. Unique game pages  (games/narrative/, ar/, data/games/ self-contained)

Outputs: thesis/analysis/gamification_catalog.csv
Columns: module_id, period, game_type, technology, file_path, code_size_kb
"""

import csv
import re
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parents[2] / "HistoryLikeGame"
OUTPUT_FILE = Path(__file__).resolve().parent / "gamification_catalog.csv"

# ── Period mapping for quiz data files ──────────────────────────────────
# Quiz filenames: crstm-s-{row}-{col}.js
# Row 1 = Period 1 (Стародавня історія), Row 2 = Period 2 (Русь-Україна), etc.
# Omega = α (Christmas meta-quiz)
QUIZ_ROW_TO_PERIOD = {
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "omega": "α",
}

# ── Period mapping for falling data files ───────────────────────────────
FALLING_PERIOD_MAP = {
    "period-2-kyiv-rus.js": "2",
    "period-3-lytva.js": "3",
    "period-4-kozaky.js": "4",
}

# ── Narrative game pages: (filename_or_path, game_type, technology, period) ──
# These are unique, hand-crafted games in games/narrative/
NARRATIVE_GAMES = [
    # Period 0 — Стародавня історія (intro / pre-period games)
    ("washhand-1.html",             "chronobiy-timeline",   "Three.js",          "0"),
    ("new-makako-2.html",           "block-buster",         "Canvas",            "0"),
    ("compas.html",                 "compass-navigation",   "DOM/Interactive",   "0"),
    ("los-elviros-1.html",         "solitaire-card",       "DOM/Drag-drop",     "0"),
    # Period 1 — Стародавня історія
    ("shiwafornia-2.html",          "path-builder",         "DOM/Interactive",   "1"),
    ("shivafornia-3.html",          "image-quiz",           "DOM/Interactive",   "1"),
    # Period 2 — Русь-Україна
    ("new-orlan-1.html",            "falling-answer",       "DOM/Falling",       "2"),
    ("masachuchi/masachuchi.html",  "apple-catcher",        "Canvas",            "2"),
    # Period 3 — Литовсько-польська доба
    ("taxes-1.html",                "falling-answer",       "DOM/Falling",       "3"),
    # Period 4 — Козацька доба
    ("solitaire-v2.html",           "historical-solitaire", "DOM/Drag-drop",     "4"),
    ("new-makako-1/index.html",     "falling-answer",       "DOM/JS",            "4"),
    # Period 5 — Імперський період
    ("bobble-shooter.html",         "bubble-shooter",       "Canvas",            "5"),
    ("tower-defense.html",          "tower-defense",        "Three.js",          "5"),
    # Period 6 — Українська революція
    ("viraska.html",                "wordwall-embed",       "Wordwall",          "6"),
    # Period 7 — Радянський період
    ("puzzle-phenikis.html",        "drag-drop-puzzle",     "DOM/Drag-drop",     "7"),
    # Period 8 — Незалежність
    ("kafe-simulator.html",         "cafe-simulator",       "DOM/Interactive",   "8"),
    # AR variant (narrative folder, but A-Frame-based)
    ("totoronto.html",              "ar-quiz",              "A-Frame",           "AR"),
]

# ── AR games in ar/ directory ───────────────────────────────────────────
AR_GAMES = [
    ("kvebek.html",                         "ar-scene",   "A-Frame"),
    ("kvebek-2.html",                       "ar-scene",   "A-Frame+AR.js"),
    ("totoronto-2.html",                    "ar-poster",  "A-Frame+AR.js"),
    ("usin/usin-1.html",                    "ar-scene",   "A-Frame+AR.js"),
    ("usin/usin-test.html",                 "ar-test",    "A-Frame+AR.js"),
    ("usin-blue/usin-blue-1.html",          "ar-scene",   "A-Frame+AR.js"),
    ("usin-blue/usin-test.html",            "ar-test",    "A-Frame+AR.js"),
    ("usin-green/usin-green-1.html",        "ar-scene",   "A-Frame+AR.js"),
    ("usin-green/usin-test.html",           "ar-test",    "A-Frame+AR.js"),
    ("usin-indg/usin-indg-1.html",          "ar-scene",   "A-Frame+AR.js"),
    ("usin-indg/usin-test.html",            "ar-test",    "A-Frame+AR.js"),
    ("usin-prsk/usin-prsk-1.html",          "ar-scene",   "A-Frame+AR.js"),
    ("usin-prsk/usin-test.html",            "ar-test",    "A-Frame+AR.js"),
]

# ── Self-contained games in data/games/ ─────────────────────────────────
DATA_GAMES = [
    ("Yove_3/index.html",          "tower-defense-v2",  "Three.js+Canvas", "5"),
    ("pheniks_2/pheniks_2.html",    "drag-drop-puzzle",  "DOM/Drag-drop",   "7"),
]

# ── Game-specific data files in data/games/ ─────────────────────────────
GAME_DATA_FILES = {
    "bobble-imperial.js":       ("bobble-data",      "5"),
    "kafe-independence.js":     ("kafe-data",        "8"),
    "puzzle-soviet.js":         ("puzzle-data",      "7"),
    "solitaire-v2-cossack.js":  ("solitaire-data",   "4"),
}


def _file_size_kb(path: Path) -> float:
    """Return file size in KB, rounded to 1 decimal."""
    try:
        return round(path.stat().st_size / 1024, 1)
    except OSError:
        return 0.0


def _code_size_kb(path: Path) -> float:
    """Return total code size for a module.

    For single files, returns the file size.
    For directories containing the file, sums all .html/.js/.css in that dir.
    """
    if path.is_file():
        parent = path.parent
        # If the parent has other code siblings (self-contained module), sum them
        siblings = list(parent.glob("*.html")) + list(parent.glob("*.js")) + list(parent.glob("*.css"))
        # Only count as multi-file module if there are at least 2 code files
        # AND the parent is not a shared directory (narrative/, ar/, etc.)
        parent_name = parent.name
        multi_file_dirs = {"masachuchi", "new-makako-1", "Yove_3", "pheniks_2"}
        if parent_name in multi_file_dirs and len(siblings) > 1:
            total = sum(f.stat().st_size for f in siblings)
            return round(total / 1024, 1)
    return _file_size_kb(path)


def _detect_technology(filepath: Path) -> str:
    """Auto-detect technology from file content as a verification/fallback."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unknown"

    if "aframe" in content.lower() or "a-scene" in content.lower():
        if "ar.js" in content.lower() or "aframe-ar" in content.lower():
            return "A-Frame+AR.js"
        return "A-Frame"
    if "three.min.js" in content or "THREE." in content:
        if "getContext" in content or "<canvas" in content:
            return "Three.js+Canvas"
        return "Three.js"
    if "wordwall.net" in content:
        return "Wordwall"
    if "getContext('2d')" in content or 'getContext("2d")' in content:
        return "Canvas"
    if "<canvas" in content:
        return "Canvas"
    return "DOM/Interactive"


def catalog_quiz_modules() -> list[dict]:
    """Catalog quiz data files (Tier 1)."""
    quiz_dir = GAME_DIR / "data" / "quiz"
    rows = []
    for js_file in sorted(quiz_dir.glob("crstm-s-*.js")):
        stem = js_file.stem  # e.g. "crstm-s-1-1" or "crstm-s-omega"
        parts = stem.split("-")  # ["crstm", "s", "1", "1"] or ["crstm", "s", "omega"]
        if len(parts) >= 3 and parts[2] == "omega":
            module_id = "quiz-omega"
            period = "α"
        elif len(parts) >= 4:
            row = parts[2]
            col = parts[3]
            extra = f"-{parts[4]}" if len(parts) > 4 else ""
            module_id = f"quiz-{row}-{col}{extra}"
            period = QUIZ_ROW_TO_PERIOD.get(row, row)
        else:
            module_id = f"quiz-{stem}"
            period = "?"

        rel_path = js_file.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": period,
            "game_type": "quiz",
            "technology": "Template-based",
            "file_path": str(rel_path),
            "code_size_kb": _file_size_kb(js_file),
        })
    return rows


def catalog_falling_modules() -> list[dict]:
    """Catalog falling-answer data files (Tier 2)."""
    falling_dir = GAME_DIR / "data" / "falling"
    rows = []
    for js_file in sorted(falling_dir.glob("*.js")):
        period = FALLING_PERIOD_MAP.get(js_file.name, "?")
        stem = js_file.stem  # e.g. "period-2-kyiv-rus"
        module_id = f"falling-{stem}"
        rel_path = js_file.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": period,
            "game_type": "falling-answer",
            "technology": "Template-based",
            "file_path": str(rel_path),
            "code_size_kb": _file_size_kb(js_file),
        })
    return rows


def catalog_narrative_games() -> list[dict]:
    """Catalog unique narrative/arcade game pages (Tier 3a)."""
    narrative_dir = GAME_DIR / "games" / "narrative"
    rows = []
    for rel_name, game_type, tech_expected, period in NARRATIVE_GAMES:
        filepath = narrative_dir / rel_name
        if not filepath.exists():
            print(f"  WARNING: narrative game not found: {filepath}")
            continue

        # Auto-detect technology as verification
        tech_detected = _detect_technology(filepath)
        # Prefer the manually curated technology label
        technology = tech_expected

        module_id = filepath.stem
        if "/" in rel_name:
            # Sub-directory game: use directory name
            module_id = rel_name.split("/")[0]

        rel_path = filepath.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": period,
            "game_type": game_type,
            "technology": technology,
            "file_path": str(rel_path),
            "code_size_kb": _code_size_kb(filepath),
        })
    return rows


def catalog_ar_games() -> list[dict]:
    """Catalog AR game pages (Tier 3b)."""
    ar_dir = GAME_DIR / "ar"
    rows = []
    for rel_name, game_type, tech_expected in AR_GAMES:
        filepath = ar_dir / rel_name
        if not filepath.exists():
            print(f"  WARNING: AR game not found: {filepath}")
            continue

        module_id = filepath.stem
        rel_path = filepath.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": "AR",
            "game_type": game_type,
            "technology": tech_expected,
            "file_path": str(rel_path),
            "code_size_kb": _file_size_kb(filepath),
        })
    return rows


def catalog_data_games() -> list[dict]:
    """Catalog self-contained games in data/games/ (Tier 3c)."""
    games_data_dir = GAME_DIR / "data" / "games"
    rows = []

    # Self-contained HTML games
    for rel_name, game_type, tech_expected, period in DATA_GAMES:
        filepath = games_data_dir / rel_name
        if not filepath.exists():
            print(f"  WARNING: data game not found: {filepath}")
            continue

        module_id = rel_name.split("/")[0]
        rel_path = filepath.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": period,
            "game_type": game_type,
            "technology": tech_expected,
            "file_path": str(rel_path),
            "code_size_kb": _code_size_kb(filepath),
        })

    # Game-specific data files (JS data consumed by narrative games)
    for js_name, (game_type, period) in sorted(GAME_DATA_FILES.items()):
        filepath = games_data_dir / js_name
        if not filepath.exists():
            print(f"  WARNING: game data file not found: {filepath}")
            continue

        module_id = filepath.stem
        rel_path = filepath.relative_to(GAME_DIR)
        rows.append({
            "module_id": module_id,
            "period": period,
            "game_type": game_type,
            "technology": "JS-data",
            "file_path": str(rel_path),
            "code_size_kb": _file_size_kb(filepath),
        })

    return rows


def print_summary(catalog: list[dict]) -> None:
    """Print summary statistics."""
    print(f"\n{'=' * 60}")
    print(f"  HistoryLikeGame Platform — Gamification Catalog")
    print(f"{'=' * 60}")
    print(f"  Total modules cataloged: {len(catalog)}")

    # Breakdown by tier
    quiz_count = sum(1 for r in catalog if r["game_type"] == "quiz")
    falling_count = sum(1 for r in catalog if r["game_type"] == "falling-answer"
                        and r["technology"] == "Template-based")
    data_file_count = sum(1 for r in catalog if r["technology"] == "JS-data")
    ar_count = sum(1 for r in catalog if r["period"] == "AR")
    narrative_count = len(catalog) - quiz_count - falling_count - data_file_count - ar_count
    # Adjust: self-contained data games (Yove_3, pheniks_2) are not in AR
    self_contained = sum(1 for r in catalog
                         if r["file_path"].startswith("data/games/")
                         and r["technology"] != "JS-data")

    print(f"\n  Tier 1 — Quiz modules:            {quiz_count}")
    print(f"  Tier 2 — Falling-answer modules:   {falling_count}")
    print(f"  Tier 3 — Unique game pages:        {narrative_count - self_contained}")
    print(f"           Self-contained (data/):   {self_contained}")
    print(f"           AR experiences:            {ar_count}")
    print(f"           Game data files:           {data_file_count}")

    # Breakdown by period
    periods = {}
    for r in catalog:
        p = r["period"]
        periods.setdefault(p, []).append(r)
    print(f"\n  By historical period:")
    for p in sorted(periods.keys(), key=lambda x: (x not in "012345678", x)):
        names = [r["module_id"] for r in periods[p]]
        print(f"    Period {p:>3s}: {len(names):2d} modules")

    # Breakdown by technology
    techs = {}
    for r in catalog:
        t = r["technology"]
        techs.setdefault(t, 0)
        techs[t] += 1
    print(f"\n  By technology:")
    for t in sorted(techs.keys()):
        print(f"    {t:<20s}: {techs[t]:2d}")

    # Total code size
    total_kb = sum(r["code_size_kb"] for r in catalog)
    print(f"\n  Total code size: {total_kb:.1f} KB ({total_kb / 1024:.1f} MB)")

    print(f"\n  Platform introduced: 2024-12-01 (HistoryLikeGame)")
    print(f"  -> {OUTPUT_FILE}")
    print(f"{'=' * 60}")


def main():
    if not GAME_DIR.exists():
        print(f"Error: Game directory not found: {GAME_DIR}")
        return

    catalog = []

    print("Scanning Tier 1: Quiz data files...")
    quiz_rows = catalog_quiz_modules()
    for r in quiz_rows:
        print(f"  {r['module_id']:25s}  period={r['period']}  {r['code_size_kb']:6.1f} KB")
    catalog.extend(quiz_rows)

    print("\nScanning Tier 2: Falling-answer data files...")
    falling_rows = catalog_falling_modules()
    for r in falling_rows:
        print(f"  {r['module_id']:25s}  period={r['period']}  {r['code_size_kb']:6.1f} KB")
    catalog.extend(falling_rows)

    print("\nScanning Tier 3a: Narrative/arcade games...")
    narrative_rows = catalog_narrative_games()
    for r in narrative_rows:
        print(f"  {r['module_id']:25s}  period={r['period']}  tech={r['technology']:<20s}  "
              f"{r['code_size_kb']:6.1f} KB")
    catalog.extend(narrative_rows)

    print("\nScanning Tier 3b: AR games...")
    ar_rows = catalog_ar_games()
    for r in ar_rows:
        print(f"  {r['module_id']:25s}  period={r['period']}  tech={r['technology']:<20s}  "
              f"{r['code_size_kb']:6.1f} KB")
    catalog.extend(ar_rows)

    print("\nScanning Tier 3c: Self-contained data games + game data files...")
    data_rows = catalog_data_games()
    for r in data_rows:
        print(f"  {r['module_id']:25s}  period={r['period']}  tech={r['technology']:<20s}  "
              f"{r['code_size_kb']:6.1f} KB")
    catalog.extend(data_rows)

    if not catalog:
        print("No modules found.")
        return

    # Write CSV
    fieldnames = ["module_id", "period", "game_type", "technology",
                  "file_path", "code_size_kb"]
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalog)

    print_summary(catalog)


if __name__ == "__main__":
    main()
