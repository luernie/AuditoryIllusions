"""
config.py — shared settings

MODE: set to "trial" for participants, "dev" to see all debug info
"""

MODE = "trial"   # <-- change to "trial" when running with participants

# ── FOLDERS ───────────────────────────────────────────────────────────────────
RISSET_FOLDER  = "AudioRatingRR"
SHEPARD_FOLDER = "AudioRatingST"
OUTPUT_FOLDER  = "data"

# ── EXPERIMENT DEFINITIONS ────────────────────────────────────────────────────
# Each experiment has a "dev" and "trial" version of display strings

EXPERIMENTS = {
    "risset": {
        "folder":      RISSET_FOLDER,
        "label":       "Risset Rhythm",
        "ui_title": {
            "dev":   "Risset Rhythm — Tempo Perception",
            "trial": "Tempo Perception",
        },
        "show_condition": {
            "dev":   True,
            "trial": False,
        },
        "show_progress": {
            "dev":   True,
            "trial": False,
        },
        "instructions": (
            "Listen to each audio sample and rate how you perceive the tempo using the slider:\n"
            "  -10 = strongly slowing down          +10 = strongly speeding up\n"
            "     0 = no clear change in tempo\n\n"
            "You can replay a sample as many times as you like before rating it.\n"
            "When you have rated all samples, press Save & Continue."
        ),
    },
    "shepard": {
        "folder":      SHEPARD_FOLDER,
        "label":       "Shepard Tone",
        "ui_title": {
            "dev":   "Shepard Tone — Pitch Perception",
            "trial": "Pitch Perception",
        },
        "show_condition": {
            "dev":   True,
            "trial": False,
        },
        "show_progress": {
            "dev":   True,
            "trial": False,
        },
        "instructions": (
            "Listen to each audio sample and rate how you perceive the pitch using the slider:\n"
            "  -10 = strongly decreasing pitch       +10 = strongly increasing pitch\n"
            "     0 = no clear change in pitch\n\n"
            "You can replay a sample as many times as you like before rating it.\n"
            "When you have rated all samples, press Save & Continue."
        ),
    },
}

def get_exp_config(exp_key):
    """Return a flat config dict resolved for the current MODE."""
    raw = EXPERIMENTS[exp_key]
    return {
        "folder":         raw["folder"],
        "label":          raw["label"],
        "ui_title":       raw["ui_title"][MODE],
        "show_condition": raw["show_condition"][MODE],
        "show_progress":  raw["show_progress"][MODE],
        "instructions":   raw["instructions"],
    }

# ── LATIN SQUARE ──────────────────────────────────────────────────────────────
LATIN_SQUARE = [
    ["audio",  "haptic", "both"],
    ["audio",  "both",   "haptic"],
    ["haptic", "audio",  "both"],
    ["haptic", "both",   "audio"],
    ["both",   "audio",  "haptic"],
    ["both",   "haptic", "audio"],
]

def get_block_order(participant_number):
    row = (participant_number - 1) % 6
    return LATIN_SQUARE[row]