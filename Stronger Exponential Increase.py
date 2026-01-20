"""
TRUE Risset Rhythm Generator (Exponential, Event-Based)

- No linear tempo
- No speedup cheating
- No looping patterns
- Pure exponential timing
- Enhanced perceptual clarity for comparison with linear ramps
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# -----------------------------
# Perceptual control parameters
# -----------------------------
EXP_RANGE = 3.0     # Total exponential range in octaves (2.5–4 recommended)
HIT_DECAY = 45      # Faster decay = clearer rhythmic onsets

# -----------------------------
# Percussive hit (sharper impulse)
# -----------------------------
def make_hit(sample_rate, duration_ms=40, freq=120):
    length = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, length, endpoint=False)

    envelope = np.exp(-t * HIT_DECAY)
    signal = np.sin(2 * np.pi * freq * t)

    # Add short transient click for timing salience
    signal[:5] += 0.5

    return signal * envelope

# -----------------------------
# Generate one exponential layer
# -----------------------------
def generate_layer(
    duration,
    base_freq,
    layer_index,
    num_layers,
    accelerating,
    sample_rate
):
    samples = int(duration * sample_rate)
    layer = np.zeros(samples)

    # Octave-spaced starting frequencies
    freq_offset = 2 ** (layer_index / num_layers)

    t = 0.0
    while t < duration:
        progress = t / duration

        # TRUE exponential timing (no cheating)
        if accelerating:
            freq = base_freq * freq_offset * (2 ** (progress * EXP_RANGE))
            loudness = 0.6 + 0.4 * progress
        else:
            freq = base_freq * freq_offset * (2 ** (-progress * EXP_RANGE))
            loudness = 0.6 + 0.4 * (1 - progress)

        interval = 1.0 / freq

        # Shepard-style perceptual crossfade (less masking)
        fade = np.clip(progress * 1.3, 0, 1) * np.clip((1 - progress) * 1.3, 0, 1)

        hit = make_hit(sample_rate, freq=120 + layer_index * 40)
        start = int(t * sample_rate)
        end = min(start + len(hit), samples)

        layer[start:end] += hit[: end - start] * fade * loudness
        t += interval

    return layer

# -----------------------------
# Main generator
# -----------------------------
def generate_risset(
    duration=20,
    base_tempo=80,
    num_layers=3,
    accelerating=True,
    sample_rate=44100,
    output_dir="risset_stronger"
):
    os.makedirs(output_dir, exist_ok=True)

    base_freq = base_tempo / 60.0
    mix = np.zeros(int(duration * sample_rate))

    for i in range(num_layers):
        mix += generate_layer(
            duration,
            base_freq,
            i,
            num_layers,
            accelerating,
            sample_rate
        )

    # Normalize
    mix /= np.max(np.abs(mix) + 1e-9)

    direction = "up" if accelerating else "down"
    filename = f"risset_{direction}_{duration}s_{num_layers}layers_{base_tempo}BPM"

    wav_path = os.path.join(output_dir, filename + ".wav")
    mp3_path = os.path.join(output_dir, filename + ".mp3")

    sf.write(wav_path, mix, sample_rate)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="320k")
    os.remove(wav_path)

    print(f"✓ Created {mp3_path}")

# -----------------------------
# Generate comparison set
# -----------------------------
if __name__ == "__main__":
    # Accelerating (up)
    generate_risset(duration=8,  base_tempo=60,  num_layers=3, accelerating=True)
    generate_risset(duration=12, base_tempo=60,  num_layers=3, accelerating=True)
    generate_risset(duration=16, base_tempo=60,  num_layers=3, accelerating=True)

    # Decelerating (down)
    generate_risset(duration=8,  base_tempo=120, num_layers=3, accelerating=False)
    generate_risset(duration=12, base_tempo=120, num_layers=3, accelerating=False)
    generate_risset(duration=16, base_tempo=120, num_layers=3, accelerating=False)
