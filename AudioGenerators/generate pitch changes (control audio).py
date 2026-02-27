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
    # --- Rising ---
    # Slow (matches rise_rate=1.0): ~0.125 oct/s
    [110, 156, 8, 0.7],      # 110→156 Hz, 8s  (0.5 oct = 0.125 oct/s * 4s... narrow but audible)
    
    # Medium (matches rise_rate=1.5): ~0.1875 oct/s  
    [110, 220, 8, 0.7],      # 110→220 Hz, 8s  (1 full octave, very clean reference)
    
    # Fast (matches rise_rate=2.0): ~0.25 oct/s
    [110, 440, 8, 0.7],      # 110→440 Hz, 8s  (2 octaves, clearly audible climb)

    # --- Falling ---
    [220, 156, 8, 0.7],      # mirror of slow rise
    [440, 220, 8, 0.7],      # mirror of medium rise (1 octave down)
    [880, 220, 8, 0.7],      # mirror of fast rise (2 octaves down)

    # --- Constant (anchor/baseline) ---
    [220, 220, 8, 0.7],      # steady A3, dead center of the range
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
