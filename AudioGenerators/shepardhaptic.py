"""
Haptic Shepard Tone Generator
==============================
Generates rising and falling tactile Shepard tones for a wideband
wrist-worn actuator (usable band ~150-400 Hz, flat RMS plateau).

Key design decisions (see stimulus-design doc):
  - Layer ratio is DERIVED from band + layer count so layers tile the
    band exactly and the wraparound is seamless:
        r = (F_HIGH/F_LOW)^(1/N_LAYERS)  ->  ~1.28 for 150-400 Hz, 4 layers
  - Hann (raised-cosine) envelope in normalized log-frequency: layers
    are EXACTLY zero at band edges, so the wrap is silent.
  - Phase-continuous synthesis: phase = 2*pi*cumsum(f)/fs (no clicks).
  - Sweep duration is auto-adjusted so every layer accrues an INTEGER
    number of carrier cycles per sweep -> the file loops seamlessly.
  - Per-sample amplitude equalization against the measured RMS_g(f)
    curve of the actuator (embedded below), so output acceleration is
    flat across the sweep, not just commanded voltage.

Output: 44100 Hz, 16-bit, mono WAV, normalized to 0.8 FS.
"""

import os
import numpy as np
from scipy.io import wavfile

# =====================================================================
# PARAMETERS -- edit these
# =====================================================================
OUTPUT_FOLDER   = "shepard_wavs"   # where WAVs are written
SAMPLE_RATE     = 44100            # Hz
PEAK_AMPLITUDE  = 0.8              # fraction of full scale (amp headroom)

F_LOW           = 150.0            # Hz, bottom of actuator's flat band
F_HIGH          = 400.0            # Hz, top of actuator's flat band
N_LAYERS        = 4                # simultaneous voices
                                   # layer ratio is derived: (F_HIGH/F_LOW)^(1/N_LAYERS)

FULL_SWEEP_S    = 12.0             # nominal seconds for one layer to traverse
                                   #   the full band (auto-adjusted slightly
                                   #   for a seamless loop). Slower = more convincing.
N_SWEEPS        = 3                # file length = N_SWEEPS full sweeps (integer!)

EQUALIZE        = True             # invert measured RMS_g(f) so output accel is flat
EQ_GAIN_LIMITS  = (0.5, 2.0)       # safety clamp on equalization gain

DIRECTIONS      = {"rising": +1, "falling": -1}   # both files generated

# ---------------------------------------------------------------------
# Measured actuator response (commanded_hz, rms_g), trustworthy region.
# From your frequency sweep CSV, 130-450 Hz.
# ---------------------------------------------------------------------
EQ_FREQ = np.array([130, 140, 150, 160, 170, 180, 190, 200, 210, 220,
                    230, 240, 250, 260, 270, 280, 290, 300, 310, 320,
                    330, 340, 350, 360, 370, 380, 390, 400, 410, 420,
                    430, 440, 450], dtype=float)
EQ_RMSG = np.array([1.654, 1.798, 1.835, 1.860, 1.891, 1.913, 1.943,
                    1.957, 1.954, 1.899, 1.884, 1.878, 1.900, 1.866,
                    1.843, 1.856, 1.860, 1.823, 1.833, 1.820, 1.814,
                    1.807, 1.795, 1.784, 1.791, 1.775, 1.777, 1.761,
                    1.728, 1.713, 1.694, 1.637, 1.629], dtype=float)
EQ_REF_G = float(np.median(EQ_RMSG))   # gain = EQ_REF_G / RMS_g(f)

# =====================================================================
# GENERATOR
# =====================================================================

def adjusted_sweep_time():
    """
    Adjust FULL_SWEEP_S so each layer accrues an integer number of
    carrier cycles per full sweep -> file loops with zero phase jump.

    Cycles per sweep = S * F_LOW * (R - 1) / ln(R),  R = F_HIGH/F_LOW
    (integral of an exponential frequency sweep).
    """
    R = F_HIGH / F_LOW
    k = F_LOW * (R - 1.0) / np.log(R)          # cycles per second of sweep
    n_cycles = round(FULL_SWEEP_S * k)          # snap to integer
    return n_cycles / k


def eq_gain(freq):
    """Per-sample equalization gain from the measured response."""
    if not EQUALIZE:
        return np.ones_like(freq)
    rms = np.interp(freq, EQ_FREQ, EQ_RMSG)
    return np.clip(EQ_REF_G / rms, *EQ_GAIN_LIMITS)


def generate_shepard(direction):
    """
    direction: +1 rising, -1 falling.
    Returns float array in [-1, 1].
    """
    sweep_s  = adjusted_sweep_time()
    duration = N_SWEEPS * sweep_s
    n        = int(round(duration * SAMPLE_RATE))
    R        = F_HIGH / F_LOW

    out = np.zeros(n)
    for k in range(N_LAYERS):
        # normalized log-frequency position in [0, 1), defined on the
        # sample index so that p at sample n exactly equals p at sample 0
        # -> envelope and frequency trajectory are perfectly periodic
        i = np.arange(n)
        p = (k / N_LAYERS + direction * N_SWEEPS * i / n) % 1.0

        # instantaneous frequency (exponential sweep across the band)
        freq = F_LOW * R ** p

        # Hann envelope in position: exactly zero at both band edges
        env = 0.5 * (1.0 - np.cos(2.0 * np.pi * p))

        # phase-continuous carrier
        phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE

        # snap total accrued phase to an exact integer number of cycles
        # (spreads a sub-milliHz correction across the file so the loop
        #  point has zero phase discontinuity: with cumsum convention,
        #  looping requires phase[-1] to be an exact multiple of 2*pi)
        target = 2.0 * np.pi * np.round(phase[-1] / (2.0 * np.pi))
        phase += (target - phase[-1]) * (i + 1) / n

        out += np.sin(phase) * env * eq_gain(freq)

    out *= PEAK_AMPLITUDE / np.max(np.abs(out))
    return out, sweep_s, duration


def write_wav(signal, path):
    wavfile.write(path, SAMPLE_RATE, np.int16(np.round(signal * 32767)))


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    r_derived = (F_HIGH / F_LOW) ** (1.0 / N_LAYERS)

    print("=" * 60)
    print("HAPTIC SHEPARD TONE GENERATOR")
    print("=" * 60)
    print(f"Band            : {F_LOW:.0f} - {F_HIGH:.0f} Hz")
    print(f"Layers          : {N_LAYERS}  (derived ratio r = {r_derived:.4f})")
    print(f"Equalization    : {EQUALIZE} (ref {EQ_REF_G:.3f} g)")

    for name, sign in DIRECTIONS.items():
        sig, sweep_s, dur = generate_shepard(sign)
        path = os.path.join(OUTPUT_FOLDER, f"shepard_{name}.wav")
        write_wav(sig, path)
        print(f"\n  {name:8s} -> {path}")
        print(f"    sweep time (loop-adjusted): {sweep_s:.4f} s")
        print(f"    file duration             : {dur:.4f} s "
              f"({N_SWEEPS} full sweeps, seamless loop)")
    print("\nDone.")