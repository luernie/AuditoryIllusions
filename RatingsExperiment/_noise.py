"""
_noise.py — plays white noise on a device for a given duration (seconds)
Usage: python _noise.py <device_id> <duration>
"""
import sys
import time

device_id = int(sys.argv[1])
duration  = float(sys.argv[2])

try:
    import numpy as np
    import sounddevice as sd

    info = sd.query_devices(device_id)
    sr   = int(info['default_samplerate'])
    ch   = min(info['max_output_channels'], 2)

    # generate white noise at low volume in chunks to avoid memory issues
    chunk = int(sr * duration)
    noise = (np.random.uniform(-1, 1, chunk) * 0.08).astype(np.float32)
    if ch == 2:
        noise = np.column_stack([noise, noise])

    sd.play(noise, sr, device=device_id, blocking=True)

except Exception as e:
    # write error to a log file next to this script so we can debug
    import os
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_noise_error.log")
    with open(log, "a") as f:
        f.write(f"device={device_id} duration={duration} error={e}\n")
finally:
    try:
        sd.stop()
    except Exception:
        pass
    time.sleep(0.2)