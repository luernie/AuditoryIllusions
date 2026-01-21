"""
TRUE Risset Rhythm Generator (Cyclic, Loopable, Customizable)

- Log-periodic exponential timing
- Perceptually stationary
- Seamlessly loopable
- Event-based (no interpolation)
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# -----------------------------
# Percussive hit
# -----------------------------
def make_hit(sample_rate, duration_ms=35, freq=120, decay=45):
    length = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, length, endpoint=False)
    envelope = np.exp(-t * decay)
    signal = np.sin(2 * np.pi * freq * t)
    signal[:5] += 0.5  # timing transient
    return signal * envelope

# -----------------------------
# Generate one Risset layer
# -----------------------------
def generate_layer(
    total_duration,
    base_freq,
    layer_index,
    num_layers,
    cycle_duration,
    accelerating,
    sample_rate
):
    samples = int(total_duration * sample_rate)
    layer = np.zeros(samples)

    # Direction of motion in log-time
    direction = 1 if accelerating else -1

    # Layer offset (Shepard spacing)
    phase_offset = layer_index / num_layers

    t = 0.0
    while t < total_duration:
        # Cyclic log-phase (0–1)
        phase = ((direction * t / cycle_duration) + phase_offset) % 1.0

        # Exponential but bounded event rate
        freq = base_freq * (2 ** phase)
        interval = 1.0 / freq

        # Shepard amplitude envelope
        fade = np.sin(np.pi * phase)

        hit = make_hit(sample_rate, freq=120 + layer_index * 30)
        start = int(t * sample_rate)
        end = min(start + len(hit), samples)

        layer[start:end] += hit[: end - start] * fade
        t += interval

    return layer

# -----------------------------
# Main generator
# -----------------------------
def generate_risset(
    duration=30,
    base_tempo=90,
    num_layers=6,
    accelerating=True,
    cycle_duration=6.0,
    sample_rate=44100,
    output_dir="risset_loopable"
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
            cycle_duration,
            accelerating,
            sample_rate
        )

    # Normalize
    mix /= np.max(np.abs(mix) + 1e-9)

    direction = "up" if accelerating else "down"
    filename = f"risset_{direction}_{duration}s_{base_tempo}BPM_{num_layers}layers"

    wav_path = os.path.join(output_dir, filename + ".wav")
    mp3_path = os.path.join(output_dir, filename + ".mp3")

    sf.write(wav_path, mix, sample_rate)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="320k")
    os.remove(wav_path)

    print(f"✓ Created {mp3_path}")

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    # Accelerating illusion
    generate_risset(duration=20, base_tempo=80, num_layers=3, accelerating=True)
    generate_risset(duration=40, base_tempo=80, num_layers=3, accelerating=True)

    # Decelerating illusion
    generate_risset(duration=20, base_tempo=80, num_layers=3, accelerating=False)
    generate_risset(duration=40, base_tempo=80, num_layers=3, accelerating=False)
