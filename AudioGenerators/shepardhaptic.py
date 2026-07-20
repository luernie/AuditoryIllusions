"""
Haptic + Audio Shepard Tone Generator
=====================================
Generates rising and falling Shepard tones in TWO matched versions:
  - HAPTIC : in the actuator's usable band (150-400 Hz), equalized to
             the measured RMS_g(f) response.
  - AUDIO  : the SAME illusion shifted up for clear audibility, matched
             to the haptic version by BAND RATIO and SWEEP RATE (not by
             carrier -- a Shepard tone has no fixed carrier to swap).

Why "matched by ratio and rate, not carrier":
  A Shepard tone's percept lives in its sweeping frequency content, so
  there is no single carrier to reassign. The correct cross-modal match
  keeps the log-frequency span (ratio), the number of layers, the
  envelope, and the sweep rate identical, and only shifts the absolute
  register. The audio band is the haptic band multiplied by
  2^AUDIO_SHIFT_OCTAVES, which preserves the ratio exactly and (because
  both share TARGET_DURATION_S and N_SWEEPS) preserves the sweep rate
  exactly by construction.

Loop: phase-continuous synthesis + integer-cycle phase snap => seamless
loop at any duration. Output: 44100 Hz, 16-bit, mono WAV, 0.8 FS.
"""

import os
import numpy as np
from scipy.io import wavfile

# =====================================================================
# PARAMETERS -- edit these
# =====================================================================
OUTPUT_FOLDER   = "shepard_wavs"
SAMPLE_RATE     = 44100
PEAK_AMPLITUDE  = 0.8

TARGET_DURATION_S = 12.0        # every file is exactly this long
N_SWEEPS          = 2           # integer full sweeps in the file
                                #   sweep rate = N_SWEEPS / TARGET_DURATION_S
                                #   = 0.167 spans/s  (shared by both versions)

HAPTIC_F_LOW    = 150.0         # actuator's flat band, low edge
HAPTIC_F_HIGH   = 400.0         # actuator's flat band, high edge
N_LAYERS        = 4             # simultaneous voices (shared)

AUDIO_SHIFT_OCTAVES = 1.0       # audio band = haptic band * 2^this
                                #   1.0 -> 300-800 Hz (ratio preserved)

EQUALIZE_HAPTIC = True          # invert measured RMS_g(f) for the haptic band
                                #   (audio is never equalized -- goes to a speaker)
EQ_GAIN_LIMITS  = (0.5, 2.0)

DIRECTIONS      = {"rising": +1, "falling": -1}

# ---------------------------------------------------------------------
# Measured actuator response (commanded_hz, rms_g), 130-450 Hz.
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
EQ_REF_G = float(np.median(EQ_RMSG))

# =====================================================================
# GENERATOR
# =====================================================================

def eq_gain(freq, equalize):
    if not equalize:
        return np.ones_like(freq)
    rms = np.interp(freq, EQ_FREQ, EQ_RMSG)
    return np.clip(EQ_REF_G / rms, *EQ_GAIN_LIMITS)


def generate_shepard(direction, f_low, f_high, equalize):
    """
    direction: +1 rising, -1 falling.
    Returns (signal, info). Duration is exactly TARGET_DURATION_S.
    """
    sweep_s  = TARGET_DURATION_S / N_SWEEPS
    n        = int(round(TARGET_DURATION_S * SAMPLE_RATE))
    R        = f_high / f_low
    i        = np.arange(n)

    out = np.zeros(n)
    for k in range(N_LAYERS):
        # position on [0,1) defined on the sample index -> perfectly periodic
        p = (k / N_LAYERS + direction * N_SWEEPS * i / n) % 1.0
        freq = f_low * R ** p
        env  = 0.5 * (1.0 - np.cos(2.0 * np.pi * p))          # Hann in position
        phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        # snap accrued phase to integer cycles -> seamless loop
        target = 2.0 * np.pi * np.round(phase[-1] / (2.0 * np.pi))
        phase += (target - phase[-1]) * (i + 1) / n
        out += np.sin(phase) * env * eq_gain(freq, equalize)

    out *= PEAK_AMPLITUDE / np.max(np.abs(out))
    info = dict(sweep_s=sweep_s, ratio=R, f_low=f_low, f_high=f_high,
                sweep_rate=N_SWEEPS / TARGET_DURATION_S)
    return out, info


def write_wav(signal, path):
    wavfile.write(path, SAMPLE_RATE, np.int16(np.round(signal * 32767)))


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    shift = 2.0 ** AUDIO_SHIFT_OCTAVES
    a_low, a_high = HAPTIC_F_LOW * shift, HAPTIC_F_HIGH * shift

    print("=" * 62)
    print("HAPTIC + AUDIO SHEPARD TONE GENERATOR")
    print("=" * 62)
    print(f"Duration        : {TARGET_DURATION_S:.1f} s  ({N_SWEEPS} sweeps, "
          f"rate {N_SWEEPS/TARGET_DURATION_S:.3f} spans/s)")
    print(f"Haptic band     : {HAPTIC_F_LOW:.0f}-{HAPTIC_F_HIGH:.0f} Hz  (equalized={EQUALIZE_HAPTIC})")
    print(f"Audio band      : {a_low:.0f}-{a_high:.0f} Hz  (+{AUDIO_SHIFT_OCTAVES} oct)")
    print(f"Ratio (both)    : {HAPTIC_F_HIGH/HAPTIC_F_LOW:.4f}   Layers: {N_LAYERS}")

    versions = [
        ("haptic", HAPTIC_F_LOW, HAPTIC_F_HIGH, EQUALIZE_HAPTIC),
        ("audio",  a_low,        a_high,        False),
    ]
    for vname, lo, hi, eq in versions:
        for dname, sign in DIRECTIONS.items():
            sig, info = generate_shepard(sign, lo, hi, eq)
            path = os.path.join(OUTPUT_FOLDER, f"shepard_{dname}_{vname}.wav")
            write_wav(sig, path)
            print(f"  {vname:6s} {dname:8s} -> {os.path.basename(path)}  "
                  f"[{info['f_low']:.0f}-{info['f_high']:.0f} Hz, "
                  f"r={info['ratio']:.3f}, {info['sweep_rate']:.3f} spans/s]")
    print("\nHaptic -> wrist actuator. Audio -> speaker. Same illusion, shifted register.")
    print("Done.")