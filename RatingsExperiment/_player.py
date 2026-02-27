"""
_player.py — called as a subprocess to play one audio file on one device
Usage: python _player.py <device_id> <filepath>
"""
import sys
import sounddevice as sd
import soundfile as sf

device_id = int(sys.argv[1])
filepath  = sys.argv[2]

data, sr = sf.read(filepath, always_2d=True)
sd.play(data, sr, device=device_id)
sd.wait()