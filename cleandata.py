"""
clean_data.py — ANOVA-Ready Output
------------------------------------
Reads ranking summary and flashcard averages CSVs from INPUT_DIR and
produces 4 tab-delimited .txt files for RStudio:

    risset_ranking.txt
    shepard_ranking.txt
    risset_flashcards.txt
    shepard_flashcards.txt

Each file has columns:
    Participant  Modality  Filename  Score  Score_N

Normalisation: two-sided, per participant across all stimuli/modalities
    Score_N =  Score / max( positive scores)   for Score > 0
    Score_N =  Score / abs(min(negative scores)) for Score < 0  [result is negative]
    Score_N =  0                                for Score == 0
    → positive side anchors at +1, negative side anchors at -1 independently.

Usage:
    python clean_data.py
    python clean_data.py --input_dir datasorted --output_dir output
"""

import os
import re
import glob
import argparse
import pandas as pd
import numpy as np


# -- SET YOUR FOLDERS HERE -----------------------------------------------------
INPUT_DIR  = "datasorted"
OUTPUT_DIR = "output"
# ------------------------------------------------------------------------------


# -- helpers -------------------------------------------------------------------

def find_participant_id(filepath: str) -> int:
    """Extract numeric participant ID from filename (e.g. 'p006' → 6)."""
    basename = os.path.basename(filepath)
    m = re.match(r"p(\d+)_", basename)
    if m:
        return int(m.group(1))
    raise ValueError(f"Cannot parse participant ID from: {basename}")


def load_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    return df


def normalise_two_sided(series: pd.Series) -> pd.Series:
    """
    Two-sided normalisation per participant:
      positive scores: divide by max of positive scores  → range (0, +1]
      negative scores: divide by abs(min of negative scores) → range [-1, 0)
      zeros stay zero.
    If there are no positive or no negative scores, that side stays as-is
    (avoids division by zero on a flat participant).
    """
    result = series.copy().astype(float)

    pos_mask = series > 0
    neg_mask = series < 0

    if pos_mask.any():
        pos_max = series[pos_mask].max()
        result[pos_mask] = series[pos_mask] / pos_max

    if neg_mask.any():
        neg_min = series[neg_mask].min()   # most negative value
        result[neg_mask] = series[neg_mask] / abs(neg_min)

    return result


# -- file-type detectors -------------------------------------------------------

def is_ranking_summary(basename: str, stimulus: str) -> bool:
    pattern = rf"p\d+_{stimulus}_ranking_summary_\d+(_\d+)?\.csv"
    return bool(re.match(pattern, basename))


def is_flashcard_averages(basename: str, stimulus: str) -> bool:
    pattern = rf"p\d+_{stimulus}_flashcards_averages_\d+(_\d+)?\.csv"
    return bool(re.match(pattern, basename))


# -- file collection -----------------------------------------------------------

def collect_files(input_dir: str):
    risset_ranking    = []
    shepard_ranking   = []
    risset_flashcards = []
    shepard_flashcards = []

    csv_files = sorted(glob.glob(os.path.join(input_dir, "**", "p*.csv"), recursive=True))
    if not csv_files:
        csv_files = sorted(glob.glob(os.path.join(input_dir, "p*.csv")))
    if not csv_files:
        print(f"WARNING: No CSV files found in {input_dir}")
        return risset_ranking, shepard_ranking, risset_flashcards, shepard_flashcards

    for fp in csv_files:
        base = os.path.basename(fp)
        if is_ranking_summary(base, "risset"):
            risset_ranking.append(fp)
        elif is_ranking_summary(base, "shepard"):
            shepard_ranking.append(fp)
        elif is_flashcard_averages(base, "risset"):
            risset_flashcards.append(fp)
        elif is_flashcard_averages(base, "shepard"):
            shepard_flashcards.append(fp)
        else:
            print(f"  [skipped] {base}")

    return risset_ranking, shepard_ranking, risset_flashcards, shepard_flashcards


# -- builders ------------------------------------------------------------------

def build_ranking(file_list: list) -> pd.DataFrame:
    """
    Reads ranking summary CSVs (one per participant).
    Score   = raw score from the ranking task
    Score_N = two-sided normalisation per participant across all rows
    """
    frames = []
    for fp in file_list:
        try:
            df = load_csv(fp)
            df["Participant"] = find_participant_id(fp)
            frames.append(df)
        except Exception as e:
            print(f"  ERROR loading {fp}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Rename Score column if needed (ranking summary uses 'Score')
    if "Score" not in combined.columns:
        raise KeyError(f"Expected 'Score' column, found: {list(combined.columns)}")

    # Two-sided normalisation per participant
    combined["Score_N"] = (
        combined
        .groupby("Participant")["Score"]
        .transform(normalise_two_sided)
    )

    # Round numeric columns to 3 decimal places
    combined["Score"]   = combined["Score"].round(3)
    combined["Score_N"] = combined["Score_N"].round(3)

    # Keep only the columns we want, in order (Filename last)
    combined = combined[["Participant", "Modality", "Score", "Score_N", "Filename"]]

    # Sort: participant → modality (audio, both, haptic) → filename
    modality_order = {"audio": 0, "both": 1, "haptic": 2}
    combined["_mod_sort"] = combined["Modality"].map(modality_order).fillna(99)
    combined.sort_values(["Participant", "_mod_sort", "Filename"], inplace=True)
    combined.drop(columns=["_mod_sort"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    return combined


def build_flashcards(file_list: list) -> pd.DataFrame:
    """
    Reads flashcard averages CSVs (one per participant).
    Score   = the Average column from the flashcard averages file
    Score_N = two-sided normalisation per participant across all rows
    """
    frames = []
    for fp in file_list:
        try:
            df = load_csv(fp)
            df["Participant"] = find_participant_id(fp)
            frames.append(df)
        except Exception as e:
            print(f"  ERROR loading {fp}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Flashcard averages file uses 'Average' as the score column
    if "Average" not in combined.columns:
        raise KeyError(f"Expected 'Average' column, found: {list(combined.columns)}")

    combined = combined.rename(columns={"Average": "Score"})

    # Two-sided normalisation per participant
    combined["Score_N"] = (
        combined
        .groupby("Participant")["Score"]
        .transform(normalise_two_sided)
    )

    # Round numeric columns to 3 decimal places
    combined["Score"]   = combined["Score"].round(3)
    combined["Score_N"] = combined["Score_N"].round(3)

    # Keep only the columns we want, in order (Filename last)
    combined = combined[["Participant", "Modality", "Score", "Score_N", "Filename"]]

    # Sort: participant → modality (audio, both, haptic) → filename
    modality_order = {"audio": 0, "both": 1, "haptic": 2}
    combined["_mod_sort"] = combined["Modality"].map(modality_order).fillna(99)
    combined.sort_values(["Participant", "_mod_sort", "Filename"], inplace=True)
    combined.drop(columns=["_mod_sort"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    return combined


def save_txt(df: pd.DataFrame, output_path: str):
    df.to_csv(output_path, sep="\t", index=False)
    print(f"  Saved {len(df)} rows → {output_path}")


# -- sanity checks -------------------------------------------------------------

def sanity_check(df: pd.DataFrame, label: str):
    """Print warnings if Score_N is out of expected range."""
    out_of_range = df[(df["Score_N"] > 1.0 + 1e-9) | (df["Score_N"] < -1.0 - 1e-9)]
    if not out_of_range.empty:
        print(f"  WARNING [{label}]: {len(out_of_range)} Score_N values outside [-1, 1]:")
        print(out_of_range.to_string(index=False))
    else:
        print(f"  OK [{label}]: all Score_N values within [-1, 1]")

    # Check each participant has at least one +1 or -1
    for p, grp in df.groupby("Participant"):
        has_pos_anchor = (grp["Score_N"] >= 1.0 - 1e-9).any()
        has_neg_anchor = (grp["Score_N"] <= -1.0 + 1e-9).any()
        if not has_pos_anchor and grp["Score"].max() > 0:
            print(f"  WARNING [{label}] Participant {p}: no Score_N == +1.0")
        if not has_neg_anchor and grp["Score"].min() < 0:
            print(f"  WARNING [{label}] Participant {p}: no Score_N == -1.0")


# -- entry point ---------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Clean participant CSVs into ANOVA-ready txt files.")
    parser.add_argument("--input_dir",  default=INPUT_DIR)
    parser.add_argument("--output_dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\nScanning: {args.input_dir}")
    risset_ranking, shepard_ranking, risset_flashcards, shepard_flashcards = \
        collect_files(args.input_dir)

    print(f"\nFound:")
    print(f"  Risset ranking files    : {len(risset_ranking)}")
    print(f"  Shepard ranking files   : {len(shepard_ranking)}")
    print(f"  Risset flashcard files  : {len(risset_flashcards)}")
    print(f"  Shepard flashcard files : {len(shepard_flashcards)}")

    outputs = [
        ("risset_ranking.txt",    build_ranking,    risset_ranking),
        ("shepard_ranking.txt",   build_ranking,    shepard_ranking),
        ("risset_flashcards.txt", build_flashcards, risset_flashcards),
        ("shepard_flashcards.txt",build_flashcards, shepard_flashcards),
    ]

    print(f"\nBuilding output files in: {args.output_dir}")
    for filename, builder, file_list in outputs:
        if not file_list:
            print(f"  WARNING: No input files for {filename}, skipping.")
            continue
        df = builder(file_list)
        if df.empty:
            print(f"  WARNING: Empty dataframe for {filename}, skipping.")
            continue
        out_path = os.path.join(args.output_dir, filename)
        save_txt(df, out_path)
        sanity_check(df, filename)

    print("\nDone.")


if __name__ == "__main__":
    main()