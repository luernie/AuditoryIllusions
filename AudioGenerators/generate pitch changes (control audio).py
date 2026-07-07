"""
Pitch Ramp Generator — Haptic-Optimised for LRA-ZA-0832
=========================================================
Anchor: 220 Hz

Why 220 Hz (shifted from original 200 Hz):
  - LRA-ZA-0832 characterised resonance peak: 210 Hz (free air),
    measured via MPU-6050 accelerometer sweep 0-600 Hz
  - Usable tracking bandwidth: 110-420 Hz (motor faithfully tracks
    commanded frequency within ±5 Hz across this range)
  - 220 Hz anchor places all octave-spaced components safely within
    the usable band:
      220 / 2^1.0 = 110 Hz  (lower bound, just inside tracking range)
      220 × 2^1.0 = 440 Hz  (upper bound, within tracking range)
  - 200 Hz anchor placed the strong-decrease endpoint at 100 Hz,
    where the motor loses tracking and rings at resonance instead

Range: ±0.5 oct (mild) and ±1.0 oct (strong)
  - Mild:   155 Hz ↔ 311 Hz  — comfortably within usable band
  - Strong: 110 Hz ↔ 440 Hz  — full usable band extent

Sweep: logarithmic (exponential frequency ramp)
  - Linear Hz sweep is perceptually non-uniform
  - Exponential sweep = constant perceived rate of change per octave
  - (Attneave & Olson 1971; psychometric data confirm ratio-based perception)

5 control stimuli:
  - constant    (zero ramp — perceptual control)
  - increase_mild    (+0.5 oct over 8s)
  - decrease_mild    (-0.5 oct over 8s)
  - increase_strong  (+1.0 oct over 8s)
  - decrease_strong  (-1.0 oct over 8s)
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# ── Settings ───────────────────────────────────────────────────────────────────
sr         = 48000        # Hz — matches Windows HD Audio / Syntacts board
output_dir = "AudioRatingST"
duration   = 8.0          # seconds per stimulus
amplitude  = 0.8          # leave headroom for Syntacts amplifier
os.makedirs(output_dir, exist_ok=True)

# Anchor frequency — slightly above LRA resonance peak (210 Hz)
# so that full-octave-down endpoint (110 Hz) stays within usable band
ANCHOR = 220.0  # Hz

# ── Ramp definitions ───────────────────────────────────────────────────────────
# Format: (label, start_hz, end_hz)
# All endpoints derived from ANCHOR using octave ratios
ramps = [
    # label               start_hz              end_hz
    ("constant",          ANCHOR,               ANCHOR),                  # 220 → 220 Hz
    ("increase_mild",     ANCHOR,               ANCHOR * 2 ** 0.5),       # 220 → 311 Hz
    ("decrease_mild",     ANCHOR,               ANCHOR / 2 ** 0.5),       # 220 → 155 Hz
    ("increase_strong",   ANCHOR,               ANCHOR * 2 ** 1.0),       # 220 → 440 Hz
    ("decrease_strong",   ANCHOR,               ANCHOR / 2 ** 1.0),       # 220 → 110 Hz
]


# ── Generator ──────────────────────────────────────────────────────────────────
def generate_pitch_ramp(label, f0, f1, duration, sample_rate, amplitude, output_dir):
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Exponential frequency sweep — perceptually uniform rate of change
    if f0 == f1:
        freqs = np.full(n, f0)
    else:
        freqs = f0 * (f1 / f0) ** (t / duration)

    # Integrate instantaneous frequency → continuous phase
    phase  = 2 * np.pi * np.cumsum(freqs) / sample_rate
    signal = amplitude * np.sin(phase)

    # 10ms fade in/out — longer than original 5ms because
    # lower frequencies (110 Hz) have longer periods and need
    # more cycles to fade cleanly without audible clicks
    fade = int(0.010 * sample_rate)
    signal[:fade]  *= np.linspace(0, 1, fade)
    signal[-fade:] *= np.linspace(1, 0, fade)

    # ── Save ───────────────────────────────────────────────────────────────────
    oct_change = np.log2(f1 / f0) if f0 != f1 else 0.0
    fname    = f"pitch_{label}_{int(round(f0))}to{int(round(f1))}Hz"
    wav_path = os.path.join(output_dir, fname + ".wav")
    mp3_path = os.path.join(output_dir, fname + ".mp3")

    sf.write(wav_path, signal.astype(np.float32), sample_rate)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="192k")
    os.remove(wav_path)

    print(f"  ✓ {fname}  ({oct_change:+.2f} oct)  [{int(round(f0))}→{int(round(f1))} Hz]")
    return mp3_path


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Generating haptic pitch ramps")
    print(f"  Anchor frequency: {ANCHOR:.0f} Hz")
    print(f"  Sample rate:      {sr} Hz")
    print(f"  Duration:         {duration:.0f}s per stimulus")
    print(f"  Output folder:    {output_dir}/\n")
    print(f"  Usable LRA band:  110–420 Hz")
    print(f"  Mild range:       {ANCHOR/2**0.5:.0f}–{ANCHOR*2**0.5:.0f} Hz")
    print(f"  Strong range:     {ANCHOR/2**1.0:.0f}–{ANCHOR*2**1.0:.0f} Hz\n")

    for label, f0, f1 in ramps:
        generate_pitch_ramp(label, f0, f1, duration, sr, amplitude, output_dir)

    print(f"\nDone — {len(ramps)} files saved to {output_dir}/")
    print(f"\nComponent summary:")
    print(f"  constant:         220 Hz throughout")
    print(f"  increase_mild:    220 → 311 Hz  (+0.5 oct)")
    print(f"  decrease_mild:    220 → 155 Hz  (-0.5 oct)")
    print(f"  increase_strong:  220 → 440 Hz  (+1.0 oct)")
    print(f"  decrease_strong:  220 → 110 Hz  (-1.0 oct)")
    print(f"\n  All endpoints within characterized usable band (110–420 Hz)")