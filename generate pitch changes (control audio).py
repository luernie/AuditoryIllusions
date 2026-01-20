import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

sr = 44100
output_dir = "pitch_ramps_simple"
os.makedirs(output_dir, exist_ok=True)

# =========================
# DEFINE RAMP LINES HERE
# Format: [start_Hz, end_Hz, duration_s, amplitude (0-1)]
# =========================
ramps = [
    [200, 400, 5, 0.8],    # 200->400 Hz over 5s
    [300, 800, 10, 0.8],   # 300->800 Hz over 10s
    [500, 2000, 12, 0.8]   # 500->2000 Hz over 12s
]

# =========================
# GENERATE FILES
# =========================
for ramp in ramps:
    f0, f1, duration, amp = ramp

    t = np.linspace(0, duration, int(sr * duration))
    freqs = np.linspace(f0, f1, len(t))
    
    # integrate frequency to get phase
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    signal = amp * np.sin(phase)

    fname = f"pitch_{f0}to{f1}_{duration}s"
    wav_path = f"{output_dir}/{fname}.wav"
    mp3_path = f"{output_dir}/{fname}.mp3"

    sf.write(wav_path, signal, sr)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="192k")
    os.remove(wav_path)

    print(f"Created: {mp3_path}")
