# import sounddevice as sd
# import numpy as np

# def test_device(device_id):
#     samplerate = 44100
#     duration = 1
#     frequency = 440
#     t = np.linspace(0, duration, int(samplerate * duration), False)
#     tone = 0.5 * np.sin(2 * np.pi * frequency * t)
#     print(f"Testing device {device_id}")
#     sd.play(tone, samplerate, device=device_id)
#     sd.wait()

# test_device(13)

import sounddevice as sd
import soundfile as sf
import threading

# Change these to your actual device IDs
DEVICE_SPEAKERS = 13
DEVICE_USB = 13

devices = sd.query_devices()

for i, device in enumerate(devices):
    print(f"{i}: {device['name']} - Output Channels: {device['max_output_channels']}")

def play_on_device(filename, device_id):
    data, samplerate = sf.read(filename)
    sd.play(data, samplerate, device=device_id)
    sd.wait()

# Use threads so they play simultaneously
t1 = threading.Thread(target=play_on_device, args=("audio1.wav", DEVICE_SPEAKERS))
t2 = threading.Thread(target=play_on_device, args=("audio2.wav", DEVICE_USB))

t1.start()
t2.start()

t1.join()
t2.join()

print("Done playing both audios")

# def find_device_by_name(name_fragment):
#     for i, device in enumerate(sd.query_devices()):
#         if name_fragment.lower() in device['name'].lower() and device['max_output_channels'] > 0:
#             return i
#     return None

# DEVICE_USB = find_device_by_name("KM-HIFI")
# DEVICE_SPEAKERS = find_device_by_name("Headphones")

# print("USB:", DEVICE_USB)
# print("Speakers:", DEVICE_SPEAKERS)