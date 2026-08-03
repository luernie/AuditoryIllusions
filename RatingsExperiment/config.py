"""
config.py — shared settings

MODE: set to "trial" for participants, "dev" to see all debug info
"""

MODE = "trial"   # <-- "trial" for participants, "dev" for debugging

# ── FOLDERS ───────────────────────────────────────────────────────────────────
RISSET_FOLDER  = "AudioRatingRR"
SHEPARD_FOLDER = "AudioRatingST"
OUTPUT_FOLDER  = "data"

# ── EXPERIMENT DEFINITIONS ────────────────────────────────────────────────────
EXPERIMENTS = {
    "risset": {
        "folder":      RISSET_FOLDER,
        "label":       "Risset Rhythm",
        "ui_title": {
            "dev":   "Risset Rhythm — Tempo Perception",
            "trial": "Tempo Perception",
        },
        "show_condition": {"dev": True, "trial": False},
        "show_progress":  {"dev": True, "trial": False},
        # (heading, text) pairs shown at the top of every screen
        "definitions": [
            ("Tempo",
             "How fast or slow a rhythm feels — how quickly the beats seem to repeat."),
            ("Haptic tempo",
             "How fast or slow a series of vibrations feels — how quickly the pulses seem to repeat."),
        ],
        "rating_bullets": [
            "-10 = strongly slowing down",
            "0 = no change",
            "+10 = strongly speeding up",
            "You can replay a sample as many times as you like before rating it.",
        ],
    },
    "shepard": {
        "folder":      SHEPARD_FOLDER,
        "label":       "Shepard Tone",
        "ui_title": {
            "dev":   "Shepard Tone — Pitch Perception",
            "trial": "Pitch Perception",
        },
        "show_condition": {"dev": True, "trial": False},
        "show_progress":  {"dev": True, "trial": False},
        "definitions": [
            ("Pitch",
             "How high or low a sound feels."),
            ("Haptic pitch",
             "How high or low a vibration feels — sharper, buzzier vibrations feel higher; "
             "deeper, thuddier vibrations feel low."),
        ],
        "rating_bullets": [
            "-10 = strongly decreasing",
            "0 = no change",
            "+10 = strongly increasing",
            "You can replay a sample as many times as you like before rating it.",
        ],
    },
}

def get_exp_config(exp_key):
    """Return a flat config dict resolved for the current MODE."""
    raw = EXPERIMENTS[exp_key]
    return {
        "folder":          raw["folder"],
        "label":           raw["label"],
        "ui_title":        raw["ui_title"][MODE],
        "show_condition":  raw["show_condition"][MODE],
        "show_progress":   raw["show_progress"][MODE],
        "definitions":     raw["definitions"],
        "rating_bullets":  raw["rating_bullets"],
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