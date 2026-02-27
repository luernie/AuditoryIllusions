"""
config.py — shared settings for the experiment
"""

# ── FOLDERS ───────────────────────────────────────────────────────────────────
RISSET_FOLDER  = "./audio/risset"   # folder of risset rhythm audio files
OUTPUT_FOLDER  = "./results"        # where CSV exports are saved

# ── LATIN SQUARE ──────────────────────────────────────────────────────────────
# 6 orderings of the 3 modalities (all permutations)
LATIN_SQUARE = [
    ["audio",  "haptic", "both"],
    ["audio",  "both",   "haptic"],
    ["haptic", "audio",  "both"],
    ["haptic", "both",   "audio"],
    ["both",   "audio",  "haptic"],
    ["both",   "haptic", "audio"],
]

def get_block_order(participant_number: int):
    """Return list of modality strings for this participant."""
    row = (participant_number - 1) % 6
    return LATIN_SQUARE[row]