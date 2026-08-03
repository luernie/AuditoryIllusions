"""
aggregate.py — builds summary files from raw experiment CSVs
=============================================================
Point it at your results folder and it produces two files per
participant/experiment combination:

  YYYYMMDD_HHMMSS_p001_risset_ranking_summary.csv
  YYYYMMDD_HHMMSS_p001_risset_flashcard_summary.csv

Usage:
  python aggregate.py                      # uses ./results by default
  python aggregate.py path/to/results      # custom folder

It reads:
  - {date}_p001_block*_risset_*.csv                  (individual ranking blocks)
  - TEMP_{date}_p001_risset_flashcard_run*.csv        (per-run flashcard temp files)

It does NOT modify or delete any source files.
"""

import os
import sys
import csv
import glob
import re
from collections import defaultdict
from datetime import datetime

RESULTS_FOLDER = sys.argv[1] if len(sys.argv) > 1 else "./results"
OUTPUT_FOLDER  = RESULTS_FOLDER

NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

# Matches: [DEV_]YYYYMMDD_HHMMSS_p###_block##_<exp>_<modality>.csv
BLOCK_RE = re.compile(
    r"^(?:DEV_)?\d{8}_\d{6}_p(\d+)_block\d+_([a-zA-Z]+)_[a-zA-Z]+\.csv$"
)

# Matches: TEMP_YYYYMMDD_HHMMSS_p###_<exp>_flashcard_run#.csv
FLASHCARD_RE = re.compile(
    r"^TEMP_\d{8}_\d{6}_p(\d+)_([a-zA-Z]+)_flashcard_run(\d+)\.csv$"
)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved: {path}")


def find_files():
    return sorted(os.listdir(RESULTS_FOLDER))


def participant_exp_pairs(all_files):
    pairs = set()
    for fname in all_files:
        m = BLOCK_RE.match(fname)
        if m:
            pairs.add((int(m.group(1)), m.group(2)))
    return sorted(pairs)


# ── RANKING SUMMARY ───────────────────────────────────────────────────────────

def build_ranking_summary(pid, exp, all_files):
    matches = [f for f in all_files if BLOCK_RE.match(f)
               and BLOCK_RE.match(f).group(1) == str(pid)
               and BLOCK_RE.match(f).group(2) == exp]

    if not matches:
        print(f"  No ranking block files found for p{pid:03d} {exp}")
        return

    all_rows = []
    for fname in matches:
        rows = read_csv(os.path.join(RESULTS_FOLDER, fname))
        all_rows.extend(rows)

    if not all_rows:
        return

    out_path = os.path.join(OUTPUT_FOLDER,
                            f"{NOW}_p{pid:03d}_{exp}_ranking_summary.csv")
    fieldnames = ["Participant", "Block", "Stimulus", "Modality",
                  "Rank", "Filename", "Score"]
    write_csv(out_path, fieldnames,
              [{k: r.get(k, "") for k in fieldnames} for r in all_rows])


# ── FLASHCARD SUMMARY ─────────────────────────────────────────────────────────

def build_flashcard_summary(pid, exp, all_files):
    matches = [f for f in all_files if FLASHCARD_RE.match(f)
               and FLASHCARD_RE.match(f).group(1) == str(pid)
               and FLASHCARD_RE.match(f).group(2) == exp]

    if not matches:
        print(f"  No flashcard temp files found for p{pid:03d} {exp}")
        return

    grouped = defaultdict(dict)
    all_trials = []

    for fname in matches:
        rows = read_csv(os.path.join(RESULTS_FOLDER, fname))
        for r in rows:
            try:
                run   = int(r["Run"])
                fn    = r["Filename"]
                mod   = r["Modality"]
                score = float(r["Score"])
                grouped[(fn, mod)][run] = score
                all_trials.append(r)
            except (KeyError, ValueError):
                pass

    if not grouped:
        return

    # Raw trials file
    trials_path = os.path.join(OUTPUT_FOLDER,
                               f"{NOW}_p{pid:03d}_{exp}_flashcard_trials.csv")
    write_csv(trials_path,
              ["Participant", "Experiment", "Run", "Filename", "Modality", "Score"],
              [{k: r.get(k, "") for k in
                ["Participant", "Experiment", "Run", "Filename", "Modality", "Score"]}
               for r in all_trials])

    # Summary file (averages)
    avg_rows = []
    for (fname, mod), runs in sorted(grouped.items()):
        s1  = runs.get(1, "")
        s2  = runs.get(2, "")
        s3  = runs.get(3, "")
        scores = [s for s in [s1, s2, s3] if s != ""]
        avg = round(sum(scores) / len(scores), 4) if scores else ""
        avg_rows.append({
            "Participant": pid,
            "Experiment":  exp,
            "Filename":    fname,
            "Modality":    mod,
            "Score_Run1":  s1,
            "Score_Run2":  s2,
            "Score_Run3":  s3,
            "Average":     avg,
        })

    summary_path = os.path.join(OUTPUT_FOLDER,
                                f"{NOW}_p{pid:03d}_{exp}_flashcard_summary.csv")
    write_csv(summary_path,
              ["Participant", "Experiment", "Filename", "Modality",
               "Score_Run1", "Score_Run2", "Score_Run3", "Average"],
              avg_rows)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.isdir(RESULTS_FOLDER):
        print(f"Folder not found: {RESULTS_FOLDER}")
        sys.exit(1)

    all_files = find_files()
    pairs = participant_exp_pairs(all_files)
    if not pairs:
        print(f"No block files found in: {RESULTS_FOLDER}")
        sys.exit(1)

    print(f"Found {len(pairs)} participant/experiment combination(s):\n")
    for pid, exp in pairs:
        print(f"  p{pid:03d} — {exp}")
        build_ranking_summary(pid, exp, all_files)
        build_flashcard_summary(pid, exp, all_files)
        print()

    print("Done.")


if __name__ == "__main__":
    main()