# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository supports a PhD thesis on **digital history teaching methodology** ("Методика навчання цифрової історії майбутніх фахівців") by Serhii Korniienko. It contains empirical materials from Ukrainian History NMT preparatory courses (October 2024 – April 2025) and academic paper fragments to be composed into a thesis.

## Repository Structure

- **`fragments/`** — Academic paper fragments and thesis template (LaTeX)
  - `thesis_template/` — Main thesis (`ssk_thes.tex`) with chapters, bibliography, and `kdpustyle.sty`
  - `04_927_TitovaKorniienkoZahorodkoMoiseienkoDonchev/` — Paper on gamification
  - `15_17_Kornieenko/` — Systematic review on digital history
  - `paper_els_17/` — Systematic review on gamification in history education
  - `1126_KorniienkoSemerikov/` — Supplementary paper
- **`Lecture material/`** — Presentations (.pptx), worksheets (.docx), PDFs, and textbook images for 38 lectures
- **`Video record_s/`** — Zoom recordings (.mp4) and audio (.m4a) tracked via Git LFS
- **`cite_structure/`** — HTML-based educational web site with interactive games (Christmas special)
- **`chat records.txt`** — Telegram group chat log (Ukrainian) from the preparatory course
- **`task`** — Working notes on thesis composition goals

## Build Commands (LaTeX papers)

Each paper in `fragments/*/source/` has a Makefile:

```bash
cd fragments/15_17_Kornieenko/source && make        # Build PDF with pdflatex + bibtex
cd fragments/paper_els_17/source && make             # Same pattern
make clean                                            # Remove build artifacts
```

The thesis template (`fragments/thesis_template/`) uses `extreport` class with `kdpustyle.sty`. Build with:
```bash
cd fragments/thesis_template
pdflatex ssk_thes.tex && bibtex ssk_thes && pdflatex ssk_thes.tex && pdflatex ssk_thes.tex
```

## Key Conventions

- **Language**: Content is primarily in Ukrainian; some papers are in English. The thesis must follow Ukrainian PhD formatting guidelines per [MoE regulation](https://zakon.rada.gov.ua/laws/show/z0155-17#Text).
- **Git LFS**: `.mp4` and `.m4a` files are tracked via Git LFS (see `.gitattributes`). Binary is at `/tmp/git-lfs-3.5.1/git-lfs` — add to PATH when needed.
- **Disk space**: The repository contains ~5GB of media files. When staging LFS files, each file is duplicated in `.git/lfs/objects/`. Clear cache with `rm -rf .git/lfs/objects/*` after pushing to free space.
- **Thesis goal**: Compose all fragments and empirical materials into a single thesis based on the template. Create a separate directory for the final thesis work.
- **Available MCPs**: Academic search, arXiv, PubMed, and Wiley Scholar Gateway MCP tools are available for literature research.
