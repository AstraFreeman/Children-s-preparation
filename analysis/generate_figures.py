#!/usr/bin/env python3
"""Generate TikZ/pgfplots figures from analysis outputs."""

import csv
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ANALYSIS_DIR = Path(__file__).resolve().parent
FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"


def read_csv(filename):
    """Read a CSV from the analysis directory."""
    filepath = ANALYSIS_DIR / filename
    if not filepath.exists():
        print(f"  Warning: {filename} not found, skipping")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_data_csv(filename, header, rows):
    """Write a data CSV to figures directory for pgfplotstableread."""
    filepath = FIGURES_DIR / filename
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for row in rows:
            f.write(row + "\n")


def fig_score_progression(stats):
    """Score progression across all seminars -- dual-axis line+bar."""
    if not stats:
        return

    header = "seminar mean_pct median_pct N"
    rows = []
    for s in stats:
        rows.append(f"{s['seminar']} {s['mean_pct']} {s['median_pct']} {s['N']}")
    write_data_csv("score_progression_data.csv", header, rows)

    tex = r"""\begin{tikzpicture}
\pgfplotstableread{figures/score_progression_data.csv}\datatable
\begin{axis}[
    width=0.95\textwidth,
    height=7cm,
    xlabel={Seminar number},
    ylabel={Score (\%)},
    ymin=0, ymax=110,
    xmin=0, xmax=41,
    axis y line*=left,
    grid=major,
    grid style={gray!30},
    legend style={at={(0.02,0.98)}, anchor=north west, font=\small},
    xtick={1,5,10,15,20,25,30,35,40},
]
% Vertical dashed line at gamification boundary
\draw[dashed, gray, thick] (axis cs:24.5,0) -- (axis cs:24.5,110)
    node[above, font=\scriptsize, text=gray] {Gamification introduced};

% Mean line
\addplot[blue, thick, mark=o, mark size=1.5pt] table[x=seminar, y=mean_pct] {\datatable};
\addlegendentry{Mean \%}

% Median line
\addplot[orange, thick, mark=square*, mark size=1.5pt, dashed] table[x=seminar, y=median_pct] {\datatable};
\addlegendentry{Median \%}
\end{axis}

\begin{axis}[
    width=0.95\textwidth,
    height=7cm,
    axis y line*=right,
    axis x line=none,
    ylabel={Number of respondents},
    ymin=0, ymax=30,
    xmin=0, xmax=41,
    legend style={at={(0.98,0.98)}, anchor=north east, font=\small},
]
% N bars
\addplot[ybar, fill=green!20, draw=green!50!black, bar width=0.5, opacity=0.5] table[x=seminar, y=N] {\datatable};
\addlegendentry{N respondents}
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "score_progression.tex").write_text(tex, encoding="utf-8")
    print("  Generated: score_progression.tex")


def fig_score_distribution(stats):
    """Mean scores with SD error bars for all seminars."""
    if not stats:
        return

    header = "seminar mean_pct sd_pct"
    rows = []
    for s in stats:
        sd = float(s['sd_score'])
        rows.append(f"{s['seminar']} {s['mean_pct']} {sd:.1f}")
    write_data_csv("score_distribution_data.csv", header, rows)

    tex = r"""\begin{tikzpicture}
\pgfplotstableread{figures/score_distribution_data.csv}\datatable
\begin{axis}[
    width=0.95\textwidth,
    height=7cm,
    xlabel={Seminar number},
    ylabel={Mean score (\%) $\pm$ SD},
    ymin=0, ymax=120,
    xmin=0, xmax=41,
    grid=major,
    grid style={gray!30},
    xtick={1,5,10,15,20,25,30,35,40},
]
\addplot[ybar, fill=blue!40, draw=blue!70!black, bar width=0.6,
    error bars/.cd, y dir=both, y explicit]
    table[x=seminar, y=mean_pct, y error=sd_pct] {\datatable};
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "score_distribution.tex").write_text(tex, encoding="utf-8")
    print("  Generated: score_distribution.tex")


def fig_enrollment_curve(enrollments):
    """Cumulative enrollment over time -- using month index as x-axis."""
    if not enrollments:
        return

    # Convert dates to day offset from course start
    course_start = datetime(2024, 10, 1)
    header = "day count"
    rows = []
    seen_days = set()
    for e in enrollments:
        try:
            dt = datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M")
            day = (dt - course_start).days
            if day not in seen_days:
                rows.append(f"{day} {e['cumulative_count']}")
                seen_days.add(day)
        except ValueError:
            continue

    if not rows:
        return
    write_data_csv("enrollment_curve_data.csv", header, rows)

    # Create month tick labels
    month_labels = []
    for m, label in [(0, "Oct"), (31, "Nov"), (61, "Dec"), (92, "Jan"),
                     (123, "Feb"), (151, "Mar"), (182, "Apr")]:
        month_labels.append(f"{m}")
    xtick_str = ",".join(month_labels)

    tex = r"""\begin{tikzpicture}
\pgfplotstableread{figures/enrollment_curve_data.csv}\datatable
\begin{axis}[
    width=0.95\textwidth,
    height=6cm,
    xlabel={Month (Oct 2024 -- Apr 2025)},
    ylabel={Cumulative enrollment},
    xticklabels={Oct, Nov, Dec, Jan, Feb, Mar, Apr},
    xtick={""" + xtick_str + r"""},
    grid=major,
    grid style={gray!30},
    ymin=0, ymax=25,
]
\addplot[const plot, thick, green!60!black, fill=green!10] table[x=day, y=count] {\datatable} \closedcycle;
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "enrollment_curve.tex").write_text(tex, encoding="utf-8")
    print("  Generated: enrollment_curve.tex")


def fig_absence_analysis(absences):
    """Absence frequency by reason -- horizontal bar chart."""
    if not absences:
        return

    reasons = defaultdict(int)
    for a in absences:
        reasons[a["reason"]] += 1

    label_map = {
        "internet": "Internet issues",
        "power_outage": "Power outage",
        "family": "Family reasons",
        "unspecified": "Unspecified",
        "health": "Health",
        "late": "Late arrival",
        "air_raid": "Air raid alert",
    }

    sorted_items = sorted(reasons.items(), key=lambda x: x[1], reverse=True)

    symbolic_coords = []
    for r, c in sorted_items:
        label = label_map.get(r, r)
        symbolic_coords.append(label)

    coords_str = ", ".join(f"{{{s}}}" for s in reversed(symbolic_coords))

    tex = r"""\begin{tikzpicture}
\begin{axis}[
    width=0.85\textwidth,
    height=6cm,
    xbar,
    xlabel={Frequency},
    symbolic y coords={""" + coords_str + r"""},
    ytick=data,
    nodes near coords,
    nodes near coords align={horizontal},
    bar width=12pt,
    xmin=0,
    enlarge y limits=0.15,
    grid=major,
    grid style={gray!30},
    xgrid=major,
    ygrid=none,
]
\addplot[fill=red!50, draw=red!70!black] coordinates {"""

    coord_lines = []
    for r, c in sorted_items:
        label = label_map.get(r, r)
        coord_lines.append(f"({c},{{{label}}})")
    tex += " ".join(reversed(coord_lines))

    tex += r"""};
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "absence_analysis.tex").write_text(tex, encoding="utf-8")
    print("  Generated: absence_analysis.tex")


def fig_course_timeline(assessments):
    """Simplified timeline showing weekly assessment counts by type."""
    if not assessments:
        return

    # Aggregate by week and type
    course_start = datetime(2024, 10, 1)
    type_labels = {
        "seminar": "Seminar",
        "modular_control": "Modular",
        "intro_test": "Intro",
        "lecture_quiz": "Lecture",
        "other": "Other",
    }

    # Compute unique dates per type
    type_dates = defaultdict(set)
    for a in assessments:
        try:
            dt = datetime.strptime(a["timestamp"], "%Y-%m-%d %H:%M")
            day = (dt - course_start).days
            type_dates[a["type"]].add(day)
        except ValueError:
            continue

    # Build per-type coordinate sets (unique dates only, mapped to numeric y)
    y_map = {"seminar": 4, "modular_control": 3, "intro_test": 2, "lecture_quiz": 1, "other": 0}
    type_colors = {"seminar": "blue", "modular_control": "red",
                   "intro_test": "green!60!black", "lecture_quiz": "orange", "other": "gray"}
    type_marks = {"seminar": "o", "modular_control": "square*",
                  "intro_test": "triangle*", "lecture_quiz": "diamond*", "other": "x"}

    tex = r"""\begin{tikzpicture}
\begin{axis}[
    width=\textwidth,
    height=5cm,
    xlabel={Month (Oct 2024 -- Apr 2025)},
    xticklabels={Oct, Nov, Dec, Jan, Feb, Mar, Apr},
    xtick={0,31,61,92,123,151,182},
    yticklabels={Other, Lecture, Intro, Modular, Seminar},
    ytick={0,1,2,3,4},
    grid=major,
    grid style={gray!30},
    legend style={at={(0.02,0.98)}, anchor=north west, font=\scriptsize, legend columns=3},
    ymin=-0.5, ymax=4.8,
    xmin=-5, xmax=200,
]
"""
    for atype in ["seminar", "modular_control", "intro_test", "lecture_quiz", "other"]:
        if atype not in type_dates:
            continue
        days = sorted(type_dates[atype])
        y = y_map[atype]
        color = type_colors[atype]
        mark = type_marks[atype]
        label = type_labels[atype]
        # Limit to unique dates to avoid overcrowding
        coords = " ".join(f"({d},{y})" for d in days)
        tex += f"\\addplot[only marks, mark={mark}, mark size=2pt, {color}] coordinates {{{coords}}};\n"
        tex += f"\\addlegendentry{{{label} ({len(days)})}}\n"

    # Key dates as vertical lines
    gam_day = (datetime(2024, 12, 1) - course_start).days
    start_day = (datetime(2024, 10, 12) - course_start).days
    tex += f"\\draw[dashed, gray] (axis cs:{start_day},-0.5) -- (axis cs:{start_day},4.8) node[above, font=\\tiny, text=gray] {{Start}};\n"
    tex += f"\\draw[dashed, gray] (axis cs:{gam_day},-0.5) -- (axis cs:{gam_day},4.8) node[above, font=\\tiny, text=gray] {{Gamification}};\n"

    tex += r"""\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "course_timeline.tex").write_text(tex, encoding="utf-8")
    print("  Generated: course_timeline.tex")


def fig_full_course_comparison(stats):
    """Full course mean% with shaded pre/post regions."""
    if not stats:
        return

    header = "seminar mean_pct"
    rows = []
    for s in stats:
        rows.append(f"{s['seminar']} {s['mean_pct']}")
    write_data_csv("full_course_comparison_data.csv", header, rows)

    tex = r"""\begin{tikzpicture}
\pgfplotstableread{figures/full_course_comparison_data.csv}\datatable
\begin{axis}[
    width=0.95\textwidth,
    height=7cm,
    xlabel={Seminar number},
    ylabel={Mean score (\%)},
    ymin=0, ymax=110,
    xmin=0, xmax=41,
    grid=major,
    grid style={gray!30},
    xtick={1,5,10,15,20,25,30,35,40},
    legend style={at={(0.02,0.98)}, anchor=north west, font=\small},
]
% Shaded regions
\fill[blue!8] (axis cs:0,0) rectangle (axis cs:24.5,110);
\fill[green!8] (axis cs:24.5,0) rectangle (axis cs:41,110);
\node[font=\scriptsize, text=blue!60!black] at (axis cs:12,105) {Pre-gamification};
\node[font=\scriptsize, text=green!60!black] at (axis cs:33,105) {Post-gamification};
\draw[dashed, gray, thick] (axis cs:24.5,0) -- (axis cs:24.5,110);

% Mean line
\addplot[blue!70!black, thick, mark=*, mark size=1.5pt] table[x=seminar, y=mean_pct] {\datatable};
\addlegendentry{Mean \%}
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "full_course_comparison.tex").write_text(tex, encoding="utf-8")
    print("  Generated: full_course_comparison.tex")


def fig_modular_control_progression(mc_stats):
    """Bar+line for modular controls: N per MC + mean% line."""
    if not mc_stats:
        return

    header = "mc N mean_pct sd_pct"
    rows = []
    for s in mc_stats:
        rows.append(f"{s['module']} {s['N']} {s['mean_pct']} {s['sd_pct']}")
    write_data_csv("modular_control_data.csv", header, rows)

    tex = r"""\begin{tikzpicture}
\pgfplotstableread{figures/modular_control_data.csv}\datatable
\begin{axis}[
    width=0.85\textwidth,
    height=6cm,
    xlabel={Modular control},
    ylabel={Mean score (\%)},
    ymin=0, ymax=110,
    axis y line*=left,
    grid=major,
    grid style={gray!30},
    xtick={1,2,3,4,5,6,7},
    legend style={at={(0.02,0.98)}, anchor=north west, font=\small},
]
% Mean line with error bars
\addplot[blue, thick, mark=o, mark size=2pt,
    error bars/.cd, y dir=both, y explicit]
    table[x=mc, y=mean_pct, y error=sd_pct] {\datatable};
\addlegendentry{Mean \% $\pm$ SD}
\end{axis}

\begin{axis}[
    width=0.85\textwidth,
    height=6cm,
    axis y line*=right,
    axis x line=none,
    ylabel={Number of respondents},
    ymin=0, ymax=30,
    xtick={1,2,3,4,5,6,7},
    legend style={at={(0.98,0.98)}, anchor=north east, font=\small},
]
\addplot[ybar, fill=green!20, draw=green!50!black, bar width=8pt, opacity=0.6] table[x=mc, y=N] {\datatable};
\addlegendentry{N respondents}
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "modular_control_progression.tex").write_text(tex, encoding="utf-8")
    print("  Generated: modular_control_progression.tex")


def fig_pre_post_comparison(stats):
    """Grouped bar: pre-gamification vs post-gamification summary stats."""
    if not stats:
        return

    pre = [s for s in stats if int(s["seminar"]) <= 24]
    post = [s for s in stats if int(s["seminar"]) >= 25]

    if not pre or not post:
        print("  Skipping pre_post_comparison: insufficient data")
        return

    import statistics as st

    pre_means = [float(s["mean_pct"]) for s in pre]
    post_means = [float(s["mean_pct"]) for s in post]
    pre_ns = [int(s["N"]) for s in pre]
    post_ns = [int(s["N"]) for s in post]

    data = {
        "pre_mean": round(st.mean(pre_means), 1),
        "post_mean": round(st.mean(post_means), 1),
        "pre_median": round(st.median(pre_means), 1),
        "post_median": round(st.median(post_means), 1),
        "pre_n_avg": round(st.mean(pre_ns), 1),
        "post_n_avg": round(st.mean(post_ns), 1),
        "pre_count": len(pre),
        "post_count": len(post),
    }

    tex = r"""\begin{tikzpicture}
\begin{axis}[
    width=0.75\textwidth,
    height=6cm,
    ybar,
    bar width=18pt,
    ylabel={Value},
    symbolic x coords={Mean \%, Median \%, Avg N, Seminars},
    xtick=data,
    ymin=0, ymax=100,
    legend style={at={(0.98,0.98)}, anchor=north east, font=\small},
    nodes near coords,
    nodes near coords style={font=\scriptsize},
    enlarge x limits=0.2,
    grid=major,
    grid style={gray!30},
    ygrid=major,
    xgrid=none,
]
\addplot[fill=blue!40, draw=blue!70!black] coordinates {
    ({Mean \%},""" + str(data["pre_mean"]) + r""")
    ({Median \%},""" + str(data["pre_median"]) + r""")
    ({Avg N},""" + str(data["pre_n_avg"]) + r""")
    ({Seminars},""" + str(data["pre_count"]) + r""")
};
\addlegendentry{Pre-gamification (Sem.\ 1--24)}

\addplot[fill=green!40, draw=green!70!black] coordinates {
    ({Mean \%},""" + str(data["post_mean"]) + r""")
    ({Median \%},""" + str(data["post_median"]) + r""")
    ({Avg N},""" + str(data["post_n_avg"]) + r""")
    ({Seminars},""" + str(data["post_count"]) + r""")
};
\addlegendentry{Post-gamification (Sem.\ 25--39)}
\end{axis}
\end{tikzpicture}"""

    (FIGURES_DIR / "pre_post_comparison.tex").write_text(tex, encoding="utf-8")
    print("  Generated: pre_post_comparison.tex")


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating TikZ/pgfplots figures...")

    stats = read_csv("response_stats.csv")
    enrollments = read_csv("enrollment_timeline.csv")
    absences = read_csv("attendance_log.csv")
    assessments = read_csv("assessment_timeline.csv")
    mc_stats = read_csv("modular_control_stats.csv")

    # 5 existing figures (rewritten as TikZ)
    fig_score_progression(stats)
    fig_score_distribution(stats)
    fig_enrollment_curve(enrollments)
    fig_absence_analysis(absences)
    fig_course_timeline(assessments)

    # 3 new figures
    fig_full_course_comparison(stats)
    fig_modular_control_progression(mc_stats)
    fig_pre_post_comparison(stats)

    print(f"\nAll figures saved to: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
