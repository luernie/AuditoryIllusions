"""
Linear Tempo Ramp Generator (Event-Based Beeps)

- Linear tempo changes
- Fixed-duration beeps
- Configurable start/end BPM
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# -----------------------------
# Settings
# -----------------------------
sr = 44100
output_dir = "tempo_ramps_simple"
os.makedirs(output_dir, exist_ok=True)

# -----------------------------
# Define ramps
# Format: [start_BPM, end_BPM, duration_s, beep_freq_Hz, beep_duration_s]
# -----------------------------
ramps = [
    [60, 100, 8, 800, 0.1],   # Fast acceleration (up)
    [60, 100, 12, 800, 0.1],  # Medium acceleration (up)
    [60, 100, 16, 800, 0.1],  # Slow acceleration (up)
    [100, 60, 8, 800, 0.1],   # Fast acceleration (down)
    [100, 60, 12, 800, 0.1],  # Medium acceleration (down)
    [100, 60, 16, 800, 0.1],  # Slow acceleration (down)
]

# -----------------------------
# Generate one ramp file
# -----------------------------
def generate_ramp(bpm_start, bpm_end, duration, beep_freq, beep_duration, sample_rate, output_dir):
    # Generate beep sound
    beep_samples = int(beep_duration * sample_rate)
    t_beep = np.linspace(0, beep_duration, beep_samples, endpoint=False)
    beep = np.sin(2 * np.pi * beep_freq * t_beep)
    beep *= np.hanning(beep_samples)

    # Time vector and linear BPM ramp
    t = np.linspace(0, duration, int(sample_rate * duration))
    bpm = np.linspace(bpm_start, bpm_end, len(t))

    # Generate signal
    signal = np.zeros(len(t))
    phase = 0
    for i in range(len(t)):
        phase += bpm[i] / 60 / sample_rate
        if phase >= 1:
            end = min(i + beep_samples, len(signal))
            signal[i:end] += beep[:end - i]
            phase -= 1

    # Normalize
    signal /= np.max(np.abs(signal) + 1e-9)

    # File naming
    fname_base = f"ramp_{bpm_start}to{bpm_end}BPM_{duration}s_{int(beep_freq)}Hz"
    wav_path = os.path.join(output_dir, fname_base + ".wav")
    mp3_path = os.path.join(output_dir, fname_base + ".mp3")

    # Save files
    sf.write(wav_path, signal, sample_rate)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="192k")
    os.remove(wav_path)

    print(f"✓ Created {mp3_path}")

# -----------------------------
# Generate all ramps
# -----------------------------
if __name__ == "__main__":
    for ramp in ramps:
        bpm0, bpm1, duration, beep_freq, beep_duration = ramp
        generate_ramp(bpm0, bpm1, duration, beep_freq, beep_duration, sr, output_dir)
