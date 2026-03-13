"""
Data Cleaning Script -- ANOVA-Ready Output
------------------------------------------
Produces 4 tab-delimited .txt files for RStudio:

  1. risset_blocks.txt
       Long format: one row per Participant x Modality x Filename
       Score    = raw score
       Score_N  = normalised per Participant x Block (divide by abs max of that block)

  2. shepard_blocks.txt
       Same structure as above for shepard stimuli.

  3. risset_ranking_summary.txt
       Long format: one row per Participant x Modality x Filename
       Score    = mean across the 3 blocks
       Score_N  = normalised per Participant across all 3 runs (divide by abs max)

  4. shepard_ranking_summary.txt
       Same structure as above for shepard stimuli.

Normalisation method: divide by absolute max
  normalised = x / max(|x|)  within the normalisation window
  Zero stays zero (neutral anchor preserved). Most extreme score becomes +/-1.

Usage:
    python clean_data.py

    Edit INPUT_DIR and OUTPUT_DIR below to point at your folders.
    The input folder can contain subfolders per participant (p001/, p002/ ...)
    or all files flat in one directory. Flashcard files are automatically skipped.
"""

import os
import re
import glob
import argparse
import pandas as pd
import numpy as np

# -- SET YOUR FOLDERS HERE -----------------------------------------------------
INPUT_DIR  = "datasorted"    # folder containing participant CSVs
OUTPUT_DIR = "output"  # folder to write the 4 txt files + R code
# ------------------------------------------------------------------------------


# -- helpers -------------------------------------------------------------------

def find_participant_id(filepath: str) -> str:
    """Extract participant ID string (e.g. 'p006') from filename."""
    basename = os.path.basename(filepath)
    m = re.match(r"(p\d+)_", basename)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot parse participant ID from: {basename}")


def load_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    return df


def normalise_by_absmax(series: pd.Series) -> pd.Series:
    """
    Divide by the absolute maximum of the series.
    If all values are zero, return the series unchanged (avoids division by zero).
    """
    absmax = series.abs().max()
    if absmax == 0 or pd.isna(absmax):
        return series
    return series / absmax


# -- file-type detectors -------------------------------------------------------

def is_block_file(basename: str, stimulus: str) -> bool:
    pattern = rf"p\d+_block0[123]_{stimulus}_(both|haptic|audio)_\d+(_\d+)?\.csv"
    return bool(re.match(pattern, basename))


def is_ranking_summary(basename: str, stimulus: str) -> bool:
    pattern = rf"p\d+_{stimulus}_ranking_summary_\d+(_\d+)?\.csv"
    return bool(re.match(pattern, basename))


# -- file collection -----------------------------------------------------------

def collect_files(input_dir: str):
    risset_blocks, shepard_blocks, risset_ranking, shepard_ranking = [], [], [], []

    csv_files = sorted(glob.glob(os.path.join(input_dir, "**", "p*.csv"), recursive=True))
    if not csv_files:
        csv_files = sorted(glob.glob(os.path.join(input_dir, "p*.csv")))
    if not csv_files:
        print(f"WARNING: No CSV files found in {input_dir}")
        return risset_blocks, shepard_blocks, risset_ranking, shepard_ranking

    for fp in csv_files:
        base = os.path.basename(fp)
        if "flashcard" in base:
            continue
        if is_block_file(base, "risset"):
            risset_blocks.append(fp)
        elif is_block_file(base, "shepard"):
            shepard_blocks.append(fp)
        elif is_ranking_summary(base, "risset"):
            risset_ranking.append(fp)
        elif is_ranking_summary(base, "shepard"):
            shepard_ranking.append(fp)
        else:
            print(f"  [skipped] {base}")

    return risset_blocks, shepard_blocks, risset_ranking, shepard_ranking


# -- builders ------------------------------------------------------------------

def build_blocks(file_list: list) -> pd.DataFrame:
    """
    One row per Participant x Modality x Filename.
    Score_N = normalised per Participant x Block (each block normalised independently).
    Rationale: each block is a self-contained ranking session so the score range
    is meaningful only within that block. Normalising per block preserves the
    relative ordering within each condition without letting one block's absolute
    range distort another's.
    """
    frames = []
    for fp in file_list:
        try:
            df = load_csv(fp)
            df["ParticipantID"] = find_participant_id(fp)
            frames.append(df)
        except Exception as e:
            print(f"  ERROR loading {fp}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Normalise per Participant x Block window
    combined["Score_N"] = (
        combined
        .groupby(["ParticipantID", "Block"])["Score"]
        .transform(normalise_by_absmax)
    )

    col_order = ["ParticipantID", "Participant", "Block", "Modality", "Filename", "Rank", "Score", "Score_N"]
    col_order = [c for c in col_order if c in combined.columns]
    combined = combined[col_order]

    combined.sort_values(["ParticipantID", "Block", "Modality", "Filename"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined


def build_ranking_summary(file_list: list) -> pd.DataFrame:
    """
    One row per Participant x Modality x Filename
    Score   = mean across the 3 blocks (raw)
    Score_N = normalised across ALL 3 runs per Participant before averaging,
              then the normalised scores are averaged.
    Rationale: the 3 flashcard runs are a single pool of ratings for that
    participant. Normalising across all runs together keeps the averaged
    Score_N on a consistent [-1, 1] scale and avoids compressing the mean
    by averaging already-independently-normalised values.
    """
    frames = []
    for fp in file_list:
        try:
            df = load_csv(fp)
            df["ParticipantID"] = find_participant_id(fp)
            frames.append(df)
        except Exception as e:
            print(f"  ERROR loading {fp}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Normalise per Participant across ALL blocks/runs before averaging
    combined["Score_N"] = (
        combined
        .groupby("ParticipantID")["Score"]
        .transform(normalise_by_absmax)
    )

    # Average both raw and normalised scores across blocks
    averaged = (
        combined
        .groupby(
            ["ParticipantID", "Participant", "Stimulus", "Modality", "Filename"],
            as_index=False
        )
        .agg(
            Score=("Score", "mean"),
            Score_N=("Score_N", "mean"),
            N_blocks=("Block", "count")
        )
    )

    averaged.sort_values(["ParticipantID", "Modality", "Filename"], inplace=True)
    averaged.reset_index(drop=True, inplace=True)
    return averaged


def save_txt(df: pd.DataFrame, output_path: str):
    df.to_csv(output_path, sep="\t", index=False)
    print(f"  Saved {len(df)} rows -> {output_path}")


# -- R code hints --------------------------------------------------------------

R_CODE = """\
# -- ANOVA-ready R code ----------------------------------------------------------
# Use Score for raw analysis, Score_N for normalised analysis.
# install.packages("ez")  # run once if not installed
library(ez)

# -- 1. Risset blocks: one-way RM-ANOVA on Stimulus (Score_N) -----------------
risset_blocks <- read.table("risset_blocks.txt", header=TRUE, sep="\\t")
risset_blocks$ParticipantID <- factor(risset_blocks$ParticipantID)
risset_blocks$Modality      <- factor(risset_blocks$Modality)
risset_blocks$Filename      <- factor(risset_blocks$Filename)

# Collapse across modality first (modality order was fixed, not randomised)
risset_blocks_collapsed <- risset_blocks %>%
  group_by(ParticipantID, Filename) %>%
  summarise(Score_N = mean(Score_N), Score = mean(Score), .groups="drop")

ezANOVA(data=risset_blocks_collapsed, dv=Score_N, wid=ParticipantID, within=Filename)

# -- 2. Shepard blocks: one-way RM-ANOVA on Stimulus (Score_N) ----------------
shepard_blocks <- read.table("shepard_blocks.txt", header=TRUE, sep="\\t")
shepard_blocks$ParticipantID <- factor(shepard_blocks$ParticipantID)
shepard_blocks$Modality      <- factor(shepard_blocks$Modality)
shepard_blocks$Filename      <- factor(shepard_blocks$Filename)

shepard_blocks_collapsed <- shepard_blocks %>%
  group_by(ParticipantID, Filename) %>%
  summarise(Score_N = mean(Score_N), Score = mean(Score), .groups="drop")

ezANOVA(data=shepard_blocks_collapsed, dv=Score_N, wid=ParticipantID, within=Filename)

# -- 3. Risset ranking summary: two-way RM-ANOVA (Modality x Stimulus) --------
risset_ranking <- read.table("risset_ranking_summary.txt", header=TRUE, sep="\\t")
risset_ranking$ParticipantID <- factor(risset_ranking$ParticipantID)
risset_ranking$Modality      <- factor(risset_ranking$Modality)
risset_ranking$Filename      <- factor(risset_ranking$Filename)

ezANOVA(data=risset_ranking, dv=Score_N, wid=ParticipantID, within=.(Modality, Filename))

# -- 4. Shepard ranking summary: two-way RM-ANOVA (Modality x Stimulus) -------
shepard_ranking <- read.table("shepard_ranking_summary.txt", header=TRUE, sep="\\t")
shepard_ranking$ParticipantID <- factor(shepard_ranking$ParticipantID)
shepard_ranking$Modality      <- factor(shepard_ranking$Modality)
shepard_ranking$Filename      <- factor(shepard_ranking$Filename)

ezANOVA(data=shepard_ranking, dv=Score_N, wid=ParticipantID, within=.(Modality, Filename))
"""


# -- entry point ---------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Clean participant CSVs into ANOVA-ready txt files.")
    parser.add_argument("--input_dir",  default=INPUT_DIR,  help="Folder containing participant CSVs")
    parser.add_argument("--output_dir", default=OUTPUT_DIR, help="Folder to write output txt files")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\nScanning: {args.input_dir}")
    risset_blocks, shepard_blocks, risset_ranking, shepard_ranking = collect_files(args.input_dir)

    print(f"\nFound:")
    print(f"  Risset block files     : {len(risset_blocks)}")
    print(f"  Shepard block files    : {len(shepard_blocks)}")
    print(f"  Risset ranking files   : {len(risset_ranking)}")
    print(f"  Shepard ranking files  : {len(shepard_ranking)}")

    outputs = [
        ("risset_blocks.txt",           build_blocks,          risset_blocks),
        ("shepard_blocks.txt",          build_blocks,          shepard_blocks),
        ("risset_ranking_summary.txt",  build_ranking_summary, risset_ranking),
        ("shepard_ranking_summary.txt", build_ranking_summary, shepard_ranking),
    ]

    print(f"\nBuilding output files in: {args.output_dir}")
    for filename, builder, file_list in outputs:
        df = builder(file_list)
        if df.empty:
            print(f"  WARNING: No data for {filename}, skipping.")
            continue
        out_path = os.path.join(args.output_dir, filename)
        save_txt(df, out_path)

    hints_path = os.path.join(args.output_dir, "r_anova_code.R")
    with open(hints_path, "w", encoding="utf-8") as f:
        f.write(R_CODE)
    print(f"  Saved R code        -> {hints_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()