import tkinter as tk
from tkinter import filedialog
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import os
import time
import csv

# =========================
# GLOBAL SETTINGS
# =========================
sr = 44100
max_rate = 6.0  # BPM per second (slider extremes)
response_file = "responses.csv"

# =========================
# INITIALIZE RESPONSE FILE
# =========================
if not os.path.exists(response_file):
    with open(response_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "risset_file",
            "slider_value",
            "bpm_per_sec"
        ])

# =========================
# AUDIO STORAGE
# =========================
risset_audio = None
risset_sr = None
current_risset_name = "none"

stop_beep = False

# =========================
# LEFT SIDE: RISSET
# =========================
def load_risset():
    global risset_audio, risset_sr, current_risset_name
    path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav *.mp3")])
    if not path:
        return
    risset_audio, risset_sr = sf.read(path, dtype="float32")
    current_risset_name = os.path.basename(path)
    status_left.set(f"Loaded: {current_risset_name}")

def play_risset():
    if risset_audio is None:
        return
    sd.play(risset_audio, risset_sr)

# =========================
# RIGHT SIDE: BEEP TEMPO RAMP
# =========================
def play_beep():
    global stop_beep
    stop_beep = False

    bpm_start = 60
    duration = 12 #  how long the tempos are

    slider_val = slider.get()
    rate = slider_val * max_rate
    bpm_end = bpm_start + rate * duration

    def _run():
        global stop_beep
        n = int(sr * duration)
        t = np.linspace(0, duration, n)
        bpm = np.linspace(bpm_start, bpm_end, n)

        signal = np.zeros(n)
        phase = 0

        beep_freq = 1000 # beep frequency
        beep_dur = int(0.02 * sr) # beep duration in miliseconds
        t_beep = np.linspace(0, 0.02, beep_dur, endpoint=False)
        beep = np.sin(2 * np.pi * beep_freq * t_beep)
        beep *= np.hanning(beep_dur)

        for i in range(n):
            if stop_beep:
                return
            phase += bpm[i] / 60 / sr
            if phase >= 1:
                end = min(i + beep_dur, n)
                signal[i:end] += beep[:end - i]
                phase -= 1

        signal /= np.max(np.abs(signal))
        sd.play(signal, sr)
        sd.wait()

    threading.Thread(target=_run, daemon=True).start()

# =========================
# STOP ALL AUDIO
# =========================
def stop_all():
    global stop_beep
    stop_beep = True
    sd.stop()

# =========================
# SLIDER UPDATE
# =========================
def update_label(value):
    bpmps = float(value) * max_rate
    rate_label.set(f"{bpmps:+.2f} BPM/s")

# =========================
# SAVE RESPONSE
# =========================
def save_response():
    bpmps = slider.get() * max_rate
    with open(response_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(),
            current_risset_name,
            slider.get(),
            bpmps
        ])

# =========================
# GUI
# =========================
root = tk.Tk()
root.title("Risset vs Tempo Ramp Matching")

left = tk.Frame(root)
left.pack(side=tk.LEFT, padx=15, pady=15)

right = tk.Frame(root)
right.pack(side=tk.RIGHT, padx=15, pady=15)

# ---- LEFT ----
tk.Label(left, text="Risset Rhythm", font=("Arial", 12, "bold")).pack()
tk.Button(left, text="Load Audio", command=load_risset).pack(fill=tk.X)
tk.Button(left, text="Play", command=play_risset).pack(fill=tk.X)

status_left = tk.StringVar(value="No file loaded")
tk.Label(left, textvariable=status_left, wraplength=200).pack(pady=5)

# ---- RIGHT ----
tk.Label(right, text="Tempo Beep Match", font=("Arial", 12, "bold")).pack()

slider = tk.Scale(
    right,
    from_=-1.0,
    to=1.0,
    resolution=0.01,
    orient=tk.HORIZONTAL,
    length=300,
    command=update_label
)
slider.set(0.0)
slider.pack()

rate_label = tk.StringVar(value="0.00 BPM/s")
tk.Label(right, textvariable=rate_label).pack(pady=5)

tk.Button(right, text="Play Beep", command=play_beep).pack(fill=tk.X)
tk.Button(right, text="Save Response", command=save_response).pack(fill=tk.X, pady=5)

# ---- STOP ----
tk.Button(root, text="STOP ALL", command=stop_all).pack(pady=10)

root.mainloop()