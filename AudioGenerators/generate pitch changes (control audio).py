"""
Pitch Ramp Generator — Optimised for Headphones + LRA Haptic Motor
====================================================================
Anchor: 200 Hz

Why 200 Hz (not 1000 Hz):
  - LRA resonant frequency is 175–235 Hz (Precision Microdrives; NFPmotor.com)
    — outside this band the LRA produces little or no output
  - Pacinian corpuscle (skin vibration receptor) peak sensitivity: 200–300 Hz
    (PLOS ONE, Hopkins et al. 2016)
  - Audio-haptic perceptual integration is strongest when auditory and
    tactile frequencies match (Wilson et al., 2010, PMC2882664)
  - 200 Hz is clearly audible in headphones — just below peak auditory
    sensitivity (300–7000 Hz) but well within comfortable listening range

Range: ±0.5 oct (mild) and ±1.0 oct (strong)
  - Mild:   141 Hz ↔ 283 Hz  — stays within LRA resonance overlap zone
  - Strong: 100 Hz ↔ 400 Hz  — full extent of audio-haptic integration zone
  - Octave steps used because pitch perception is logarithmic
    (Attneave & Olson 1971; psychometric data confirm ratio-based perception)

Sweep: logarithmic (exponential frequency ramp)
  - Linear Hz sweep is perceptually non-uniform
  - Exponential sweep = constant perceived rate of change
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

sr         = 44100
output_dir = "pitch_ramps"
duration   = 8.0
amplitude  = 0.7
os.makedirs(output_dir, exist_ok=True)

ANCHOR = 200.0  # Hz — LRA resonance + peak Pacinian sensitivity

ramps = [
    # label               start_hz          end_hz
    ("constant",          ANCHOR,           ANCHOR),
    ("increase_mild",     ANCHOR,           ANCHOR * 2**0.5),   # +0.5 oct → 283 Hz
    ("decrease_mild",     ANCHOR,           ANCHOR / 2**0.5),   # -0.5 oct → 141 Hz
    ("increase_strong",   ANCHOR,           ANCHOR * 2**1.0),   # +1.0 oct → 400 Hz
    ("decrease_strong",   ANCHOR,           ANCHOR / 2**1.0),   # -1.0 oct → 100 Hz
]

for label, f0, f1 in ramps:
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Exponential (logarithmic) frequency sweep — perceptually uniform
    if f0 == f1:
        freqs = np.full(n, f0)
    else:
        freqs = f0 * (f1 / f0) ** (t / duration)

    # Integrate instantaneous frequency → phase
    phase  = 2 * np.pi * np.cumsum(freqs) / sr
    signal = amplitude * np.sin(phase)

    # 5ms fade in/out to prevent clicks
    fade = int(0.005 * sr)
    signal[:fade]  *= np.linspace(0, 1, fade)
    signal[-fade:] *= np.linspace(1, 0, fade)

    oct_change = np.log2(f1 / f0) if f0 != f1 else 0
    fname = f"pitch_{label}_{int(round(f0))}to{int(round(f1))}Hz"
    wav_path = os.path.join(output_dir, fname + ".wav")
    mp3_path = os.path.join(output_dir, fname + ".mp3")

    sf.write(wav_path, signal.astype(np.float32), sr)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="192k")
    os.remove(wav_path)

    print(f"✓ {fname}  ({oct_change:+.2f} oct)")

print(f"\nDone → {output_dir}/")
print(f"\nAnchor: {ANCHOR:.0f} Hz")
print(f"Mild:   ±0.5 oct → {ANCHOR/2**0.5:.0f}–{ANCHOR*2**0.5:.0f} Hz  (within LRA resonance overlap)")
print(f"Strong: ±1.0 oct → {ANCHOR/2**1.0:.0f}–{ANCHOR*2**1.0:.0f} Hz  (full audio-haptic integration zone)")