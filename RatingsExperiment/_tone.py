"""
_tone.py — called as a subprocess to play a test tone on one device
Usage: python _tone.py <device_id>
"""
import sys
import numpy as np
import sounddevice as sd

device_id = int(sys.argv[1])

info = sd.query_devices(device_id)
sr   = int(info['default_samplerate'])
ch   = min(info['max_output_channels'], 2)

t    = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
tone = (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

if ch == 2:
    tone = np.column_stack([tone, tone])

sd.play(tone, sr, device=device_id)
sd.wait()