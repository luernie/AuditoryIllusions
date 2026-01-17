import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

sr = 44100
output_dir = "tempo_ramps_simple"
os.makedirs(output_dir, exist_ok=True)

# =========================
# DEFINE RAMPS HERE
# Format: [start_BPM, end_BPM, duration_s, beep_freq_Hz, beep_duration_s]
# =========================
ramps = [
    [40, 150, 8, 800, 0.1],   # 60->120 BPM over 10s, 1 kHz, 20ms beep
    [40, 150, 10, 800, 0.1],     # 90->150 BPM over 5s, 800 Hz, 30ms beep
    [40, 150, 12, 800, 0.1]     # 40->80 BPM over 12s, 1.2 kHz, 10ms beep
]

# =========================
# GENERATE FILES
# =========================
for ramp in ramps:
    bpm0, bpm1, duration, beep_freq, beep_duration = ramp

    beep_samples = int(beep_duration * sr)
    t_beep = np.linspace(0, beep_duration, beep_samples, endpoint=False)
    beep = np.sin(2 * np.pi * beep_freq * t_beep)
    beep *= np.hanning(beep_samples)

    t = np.linspace(0, duration, int(sr * duration))
    bpm = np.linspace(bpm0, bpm1, len(t))

    signal = np.zeros(len(t))
    phase = 0

    for i in range(len(t)):
        phase += bpm[i] / 60 / sr
        if phase >= 1:
            end = min(i + beep_samples, len(signal))
            signal[i:end] += beep[:end - i]
            phase -= 1

    signal /= np.max(np.abs(signal))

    fname = f"tempo_{bpm0}to{bpm1}_{duration}s_{int(beep_freq)}Hz_{int(beep_duration*1000)}ms"
    wav_path = f"{output_dir}/{fname}.wav"
    mp3_path = f"{output_dir}/{fname}.mp3"

    sf.write(wav_path, signal, sr)
    AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="192k")
    os.remove(wav_path)

    print(f"Created: {mp3_path}")