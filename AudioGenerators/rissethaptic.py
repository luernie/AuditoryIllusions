"""
Haptic + Audio Risset Rhythm Generator
======================================
Generates accelerating and decelerating Risset rhythms in TWO versions
that are GUARANTEED IDENTICAL IN RHYTHM and differ only in carrier
frequency:
  - HAPTIC : 250 Hz carrier (peak Pacinian sensitivity, center of the
             actuator's flat band) -> wrist actuator.
  - AUDIO  : 500 Hz carrier (clearly audible) -> speaker.

How the guarantee works:
  All rhythmic information lives in the amplitude ENVELOPE (the pulse
  onset pattern). We synthesize that envelope EXACTLY ONCE, then multiply
  it by each carrier. Because both versions share the same envelope
  array -- same onset samples, same tempo trajectory, same layer
  weighting -- they are provably identical in rhythm. Only the carrier
  differs. (This is why we do NOT re-run the generator per carrier:
  two separate runs could drift by floating-point paths; one shared
  envelope cannot.)

Duration is fixed at TARGET_DURATION_S. The doubling period is forced to
tile it an integer number of times, and BEATS_PER_DBL is an integer, so
onsets land exactly on the loop point. TEMPO_LO is DERIVED (it is the one
quantity we let float -- the absolute starting tempo, which no observer
can judge in isolation). Both integer-Hz carriers complete a whole number
of cycles in TARGET_DURATION_S, so the carrier loops seamlessly too.

Output: 44100 Hz, 16-bit, mono WAV, 0.8 FS.
"""

import os
import numpy as np
from scipy.io import wavfile

# =====================================================================
# PARAMETERS -- edit these
# =====================================================================
OUTPUT_FOLDER   = "risset_wavs"
SAMPLE_RATE     = 44100
PEAK_AMPLITUDE  = 0.8

TARGET_DURATION_S = 12.0        # every file is exactly this long
N_DOUBLINGS       = 2           # integer tempo doublings in the file
BEATS_PER_DBL     = 9           # integer beats per doubling (accel feel)
                                #   -> per-doubling period D = TARGET/N_DOUBLINGS = 6 s
                                #   -> TEMPO_LO is DERIVED (see below), ~1.04 Hz
                                #   (raise for a faster base tempo, lower for slower)

N_LAYERS        = 3             # simultaneous tempo voices
PULSE_MS        = 40.0          # burst length -- CONSTANT across tempi
RAMP_MS         = 5.0           # raised-cosine attack/release per burst
TILT_DB_PER_DBL = -3.0          # faster layers attenuated (feel louder)

HAPTIC_CARRIER  = 210.0         # -> wrist
AUDIO_CARRIER   = 500.0         # -> speaker
CARRIERS        = {"haptic": HAPTIC_CARRIER, "audio": AUDIO_CARRIER}

DIRECTIONS      = {"accelerating": +1, "decelerating": -1}

# TEMPO_LO derived so an integer number of beats/doublings tiles the file:
#   D = TARGET / N_DOUBLINGS ;  beats/dbl = TEMPO_LO * D / ln2  = BEATS_PER_DBL
TEMPO_LO_HZ = BEATS_PER_DBL * np.log(2.0) * N_DOUBLINGS / TARGET_DURATION_S

# =====================================================================
# GENERATOR
# =====================================================================

def make_pulse_window():
    """Carrier-FREE raised-cosine burst window (values in [0,1])."""
    n_pulse = int(round(PULSE_MS / 1000.0 * SAMPLE_RATE))
    n_ramp  = int(round(RAMP_MS  / 1000.0 * SAMPLE_RATE))
    w = np.ones(n_pulse)
    ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_ramp) / n_ramp))
    w[:n_ramp]  = ramp
    w[-n_ramp:] = ramp[::-1]
    return w


def generate_envelope(direction):
    """
    Build the amplitude envelope carrying ALL rhythm information.
    Carrier-free -> shared by every carrier version.
    direction: +1 accelerating, -1 decelerating.
    """
    D   = TARGET_DURATION_S / N_DOUBLINGS
    n   = int(round(TARGET_DURATION_S * SAMPLE_RATE))
    win = make_pulse_window()
    n_p = len(win)
    env = np.zeros(n)

    for k in range(N_LAYERS):
        i = np.arange(n)
        p = (k / N_LAYERS + direction * i / (N_LAYERS * D * SAMPLE_RATE)) % 1.0
        tempo = TEMPO_LO_HZ * 2.0 ** (p * N_LAYERS)
        wenv  = 0.5 * (1.0 - np.cos(2.0 * np.pi * p))               # layer weight
        tilt  = 10.0 ** (TILT_DB_PER_DBL * (p * N_LAYERS) / 20.0)

        beat_phase = np.cumsum(tempo) / SAMPLE_RATE
        onsets = np.flatnonzero(np.diff(np.floor(beat_phase)) > 0) + 1
        onsets = np.concatenate(([0], onsets))

        for oi in onsets:
            amp = wenv[oi] * tilt[oi]
            if amp < 1e-4:
                continue
            idx = (oi + np.arange(n_p)) % n     # wrap overhang -> seamless loop
            env[idx] += win * amp

    return env, dict(D=D, tempo_lo=TEMPO_LO_HZ,
                     tempo_hi=TEMPO_LO_HZ * 2.0 ** N_LAYERS)


def render_carrier(envelope, carrier_hz):
    """Multiply the shared envelope by a continuous carrier, normalize."""
    n = len(envelope)
    t = np.arange(n) / SAMPLE_RATE
    sig = envelope * np.sin(2.0 * np.pi * carrier_hz * t)
    sig *= PEAK_AMPLITUDE / np.max(np.abs(sig))
    return sig


def write_wav(signal, path):
    wavfile.write(path, SAMPLE_RATE, np.int16(np.round(signal * 32767)))


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("=" * 62)
    print("HAPTIC + AUDIO RISSET RHYTHM GENERATOR")
    print("=" * 62)
    print(f"Duration        : {TARGET_DURATION_S:.1f} s  "
          f"({N_DOUBLINGS} doublings, {BEATS_PER_DBL} beats/dbl)")
    print(f"Doubling period : {TARGET_DURATION_S/N_DOUBLINGS:.2f} s")
    print(f"Tempo (derived) : {TEMPO_LO_HZ:.3f} -> "
          f"{TEMPO_LO_HZ*2**N_LAYERS:.3f} Hz  ({TEMPO_LO_HZ*60:.1f} BPM start)")
    print(f"Carriers        : haptic {HAPTIC_CARRIER:.0f} Hz | audio {AUDIO_CARRIER:.0f} Hz")
    print(f"Pulse           : {PULSE_MS:.0f} ms, {RAMP_MS:.0f} ms ramps (constant)")

    for dname, sign in DIRECTIONS.items():
        env, info = generate_envelope(sign)          # ONE envelope per direction
        for vname, carrier in CARRIERS.items():
            sig = render_carrier(env, carrier)        # shared envelope, two carriers
            path = os.path.join(OUTPUT_FOLDER, f"risset_{dname}_{vname}.wav")
            write_wav(sig, path)
            print(f"  {vname:6s} {dname:12s} -> {os.path.basename(path)}  "
                  f"[carrier {carrier:.0f} Hz]")
    print("\nHaptic + audio of each direction share ONE envelope -> identical rhythm.")
    print("Done.")