# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PhD research project by Serhii Korniienko (КДПУ) validating a digital history teaching methodology for university preparation courses (НМТ prep, Oct 2024 – May 2025, ~90 students). Three interconnected components:

1. **`analysis/`** — Python pipeline analyzing course data (Google Forms, Telegram logs, attendance)
2. **`cite_structure/`** — HTML5/JS educational games platform (HistoryLikeGame)

## Running the Analysis Pipeline

```bash
# Run full pipeline (from project root)
cd analysis && python run_pipeline.py

# Run individual scripts
python analysis/parse_chat.py           # Extract events from Telegram log
python analysis/extract_assessments.py # Build assessment timeline
python analysis/analyze_responses.py   # Process Google Forms data
python analysis/track_attendance.py    # Attendance patterns
python analysis/catalog_gamification.py # Inventory game modules
python analysis/generate_figures.py    # Produce TikZ/pgfplots figures

# Bibliography validation
python analysis/verify_references.py   # Check DOIs (uses doi_cache.json)
python analysis/audit_bib_metadata.py  # Audit citation metadata quality
```

No `requirements.txt` exists — scripts use stdlib only (`pathlib`, `csv`, `json`, `subprocess`).


## Architecture & Data Flow

```
chat records.txt  ──► parse_chat.py ──► parsed_chat.csv
Google Forms data ──► analyze_responses.py ──► assessment_timeline.csv
                                           ──► individual_trajectories.csv
cite_structure/   ──► catalog_gamification.py ──► gamification_catalog.csv
All CSVs          ──► generate_figures.py ──► thesis/figures/*.tex (TikZ)
bibliography.bib  ──► verify_references.py ──► doi_cache.json (4.1MB cache)
```

The pipeline scripts write CSV/JSON outputs consumed by `generate_figures.py`, which produces `.tex` snippet files included by the thesis chapters via `\input{}`.

## Web Games (`cite_structure/`)

Static HTML5 files, no build step. Each game is a self-contained `.html` file. Technologies used across games:
- Vanilla JS + Canvas API (most games)
- Three.js (3D modules)
- A-Frame (AR modules)
- DOM drag-and-drop

The `game/` subdirectory contains quiz modules organized by historical period. `index.html` is the main site entry point. The platform grew from 23 modules (v1) to 62 modules (v2) across 9 historical periods and 13 game types.

## Key Data Files

| File | Description |
|------|-------------|
| `chat records.txt` | Raw Telegram export — source for teaching event extraction |
| `thesis/bibliography.bib` | Master bibliography — edit here, not in generated files |
| `analysis/doi_cache.json` | Cached DOI lookups — do not delete, expensive to regenerate |
| `analysis/full_metadata_cache.json` | Full citation metadata cache (~4.1MB) |

## Language

Thesis text and variable/comment naming in analysis scripts are in **Ukrainian**. Commit messages and code identifiers may mix Ukrainian and English.
