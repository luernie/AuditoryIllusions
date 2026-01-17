import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

sr = 44100
duration = 12  # seconds
output_dir = "tempo_ramps_beep"
os.makedirs(output_dir, exist_ok=True)

# Tempo ramps to generate
tempo_ranges = [
    (0, 100),
    (60, 120),
    (90, 180)
]

# Beep parameters
beep_freq = 1000       # Hz
beep_duration = 0.02   # seconds (20 ms)
beep_samples = int(beep_duration * sr)

# Create beep with envelope
t_beep = np.linspace(0, beep_duration, beep_samples, endpoint=False)
beep = np.sin(2 * np.pi * beep_freq * t_beep)

# Hann envelope to avoid clicks
envelope = np.hanning(beep_samples)
beep *= envelope

for bpm0, bpm1 in tempo_ranges:
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

    wav_name = f"{output_dir}/tempo_{bpm0}_to_{bpm1}_BPM_{duration}s.wav"
    mp3_name = wav_name.replace(".wav", ".mp3")

    sf.write(wav_name, signal, sr)

    audio = AudioSegment.from_wav(wav_name)
    audio.export(mp3_name, format="mp3", bitrate="192k")

    os.remove(wav_name)
