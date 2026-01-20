"""
TRUE Risset Rhythm Generator (Exponential, Event-Based)

- No linear tempo
- No speedup cheating
- No looping patterns
- Pure exponential timing
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# -----------------------------
# Percussive hit (neutral impulse)
# -----------------------------

def make_hit(sample_rate, duration_ms=60, freq=100):
    length = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, length, endpoint=False)

    envelope = np.exp(-t * 30)
    signal = np.sin(2 * np.pi * freq * t) * envelope

    return signal


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

    # Octave-spaced starting frequency
    freq_offset = 2 ** (layer_index / num_layers)

    t = 0.0
    while t < duration:
        progress = t / duration

        if accelerating:
            freq = base_freq * freq_offset * (2 ** progress)
        else:
            freq = base_freq * freq_offset * (2 ** -progress)

        interval = 1.0 / freq

        # Fade envelope (Shepard-style)
        fade = np.sin(np.pi * progress)

        hit = make_hit(sample_rate, freq=80 + layer_index * 30)
        start = int(t * sample_rate)
        end = min(start + len(hit), samples)

        layer[start:end] += hit[: end - start] * fade
        t += interval

    return layer


# -----------------------------
# Main generator
# -----------------------------

def generate_risset(
    filename,
    duration=20,
    base_tempo=80,
    num_layers=3,
    accelerating=True,
    sample_rate=44100,
    output_dir="risset_fixed"
):
    os.makedirs(output_dir, exist_ok=True)

    base_freq = base_tempo / 60.0
    mix = np.zeros(int(duration * sample_rate))

    for i in range(num_layers):
        layer = generate_layer(
            duration,
            base_freq,
            i,
            num_layers,
            accelerating,
            sample_rate
        )
        mix += layer

    # Normalize
    mix /= np.max(np.abs(mix) + 1e-9)

    wav_path = os.path.join(output_dir, filename.replace(".mp3", ".wav"))
    mp3_path = os.path.join(output_dir, filename)

    sf.write(wav_path, mix, sample_rate)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="320k")
    os.remove(wav_path)

    print(f"✓ Created {mp3_path}")


# -----------------------------
# Example usage
# -----------------------------

if __name__ == "__main__":
    generate_risset(
        filename="risset_exponential_increase.mp3",
        duration=20,
        base_tempo=80,
        num_layers=3,
        accelerating=True
    )

    generate_risset(
        filename="risset_exponential_decrease.mp3",
        duration=20,
        base_tempo=80,
        num_layers=3,
        accelerating=False
    )
