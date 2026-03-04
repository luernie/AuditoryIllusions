"""
_player.py — plays one audio file on one device then exits cleanly
Usage: python _player.py <device_id> <filepath>
"""
import sys
import time
import sounddevice as sd
import soundfile as sf

device_id = int(sys.argv[1])
filepath  = sys.argv[2]

try:
    data, sr = sf.read(filepath, always_2d=True)
    sd.play(data, sr, device=device_id)
    sd.wait()
finally:
    sd.stop()
    time.sleep(0.2)  # let the driver fully release before process exits