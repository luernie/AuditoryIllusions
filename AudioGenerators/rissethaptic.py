"""
Haptic Risset Rhythm Generator
===============================
Generates accelerating and decelerating tactile Risset rhythms for a
wideband wrist-worn actuator, using a fixed 250 Hz carrier (peak
Pacinian sensitivity, center of the actuator's flat band).

Key design decisions (see stimulus-design doc):
  - All rhythmic information lives in the amplitude envelope; the
    carrier never changes.
  - Pulse duration is CONSTANT across all tempi (the classic failure
    mode is time-scaling the pulse with tempo, which turns fast layers
    into a buzz). Only the inter-onset interval changes.
  - 3 layers at an exact 2:1 tempo ratio, Hann envelope in normalized
    log-tempo so layers are exactly silent when they wrap.
  - Mild -3 dB per tempo doubling tilt (faster pulse trains feel more
    intense at equal amplitude).
  - Doubling period is derived from an INTEGER beat count per doubling,
    so every layer lands an onset exactly at the loop point -> the file
    loops seamlessly. Pulses that overhang the file end are wrapped
    around to the beginning (modulo overlap-add).

Output: 44100 Hz, 16-bit, mono WAV, normalized to 0.8 FS.
"""

import os
import numpy as np
from scipy.io import wavfile

# =====================================================================
# PARAMETERS -- edit these
# =====================================================================
OUTPUT_FOLDER   = "risset_wavs"    # where WAVs are written
SAMPLE_RATE     = 44100            # Hz
PEAK_AMPLITUDE  = 0.8              # fraction of full scale (amp headroom)

CARRIER_HZ      = 250.0            # fixed vibration frequency inside each pulse
N_LAYERS        = 3                # simultaneous tempo voices
TEMPO_LO_HZ     = 1.0              # slowest layer's starting pulse rate (1 Hz = 60 BPM)
                                   # layers span TEMPO_LO_HZ .. TEMPO_LO_HZ * 2^N_LAYERS

BEATS_PER_DBL   = 17               # integer beats per doubling period (sets the
                                   #   doubling time: D = BEATS_PER_DBL*ln2/TEMPO_LO_HZ
                                   #   ~= 11.78 s for 17 beats @ 1 Hz).
                                   #   MUST be an integer for a seamless loop.
N_DOUBLINGS     = 3                # file length = N_DOUBLINGS doubling periods

PULSE_MS        = 40.0             # burst length -- CONSTANT for all tempi
RAMP_MS         = 5.0              # raised-cosine attack/release on each burst
TILT_DB_PER_DBL = -3.0             # attenuation per tempo doubling (fast = quieter)

DIRECTIONS      = {"accelerating": +1, "decelerating": -1}   # both generated

# =====================================================================
# GENERATOR
# =====================================================================

def make_pulse():
    """Fixed-length 250 Hz burst with raised-cosine ramps, flat sustain."""
    n_pulse = int(round(PULSE_MS / 1000.0 * SAMPLE_RATE))
    n_ramp  = int(round(RAMP_MS  / 1000.0 * SAMPLE_RATE))
    t = np.arange(n_pulse) / SAMPLE_RATE

    env = np.ones(n_pulse)
    ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_ramp) / n_ramp))
    env[:n_ramp]  = ramp
    env[-n_ramp:] = ramp[::-1]

    return np.sin(2.0 * np.pi * CARRIER_HZ * t) * env


def generate_risset(direction):
    """
    direction: +1 accelerating, -1 decelerating.
    Returns float array in [-1, 1].
    """
    D        = BEATS_PER_DBL * np.log(2.0) / TEMPO_LO_HZ   # doubling period, s
    duration = N_DOUBLINGS * D
    n        = int(round(duration * SAMPLE_RATE))
    t        = np.arange(n) / SAMPLE_RATE

    pulse   = make_pulse()
    n_pulse = len(pulse)
    out     = np.zeros(n)

    for k in range(N_LAYERS):
        # normalized log-tempo position in [0, 1), wraps seamlessly
        p = (k / N_LAYERS + direction * t / (N_LAYERS * D)) % 1.0

        # instantaneous pulse rate (Hz): exponential over N_LAYERS doublings
        tempo = TEMPO_LO_HZ * 2.0 ** (p * N_LAYERS)

        # Hann envelope in position: exactly zero at tempo-band edges
        env = 0.5 * (1.0 - np.cos(2.0 * np.pi * p))

        # -3 dB per doubling tilt (position 0 = slowest, 1 = fastest)
        tilt = 10.0 ** (TILT_DB_PER_DBL * (p * N_LAYERS) / 20.0)

        # beat phase: onsets wherever it crosses an integer
        beat_phase = np.cumsum(tempo) / SAMPLE_RATE
        onsets = np.flatnonzero(np.diff(np.floor(beat_phase)) > 0) + 1
        onsets = np.concatenate(([0], onsets))   # onset at t = 0 as well

        for i in onsets:
            amp = env[i] * tilt[i]
            if amp < 1e-4:
                continue
            idx = (i + np.arange(n_pulse)) % n    # wrap overhang to file start
            out[idx] += pulse * amp

    out *= PEAK_AMPLITUDE / np.max(np.abs(out))
    return out, D, duration


def write_wav(signal, path):
    wavfile.write(path, SAMPLE_RATE, np.int16(np.round(signal * 32767)))


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("=" * 60)
    print("HAPTIC RISSET RHYTHM GENERATOR")
    print("=" * 60)
    print(f"Carrier         : {CARRIER_HZ:.0f} Hz (fixed)")
    print(f"Layers          : {N_LAYERS} at exact 2:1 tempo ratio")
    print(f"Tempo span      : {TEMPO_LO_HZ:.2f} - "
          f"{TEMPO_LO_HZ * 2**N_LAYERS:.2f} pulses/s")
    print(f"Pulse           : {PULSE_MS:.0f} ms, {RAMP_MS:.0f} ms ramps (constant)")

    for name, sign in DIRECTIONS.items():
        sig, D, dur = generate_risset(sign)
        path = os.path.join(OUTPUT_FOLDER, f"risset_{name}.wav")
        write_wav(sig, path)
        print(f"\n  {name:12s} -> {path}")
        print(f"    doubling period: {D:.4f} s ({BEATS_PER_DBL} beats, exact)")
        print(f"    file duration  : {dur:.4f} s "
              f"({N_DOUBLINGS} doublings, seamless loop)")
    print("\nDone.")