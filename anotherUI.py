import sounddevice as sd
import numpy as np

def play_test_tone(device_id, frequency=440, duration=1.5):
    device_info = sd.query_devices(device_id)
    samplerate = int(device_info['default_samplerate'])
    channels = min(device_info['max_output_channels'], 2)
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    tone = 0.4 * np.sin(2 * np.pi * frequency * t)
    if channels == 2:
        tone = np.column_stack([tone, tone])
    try:
        sd.play(tone, samplerate, device=device_id)
        sd.wait()
    except:
        pass

for i, device in enumerate(sd.query_devices()):
    if device['max_output_channels'] > 0:
        print(f"[{i}] {device['name']}")
        play_test_tone(i)


        print("idkidkidk")