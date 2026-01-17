import os
import tkinter as tk
from tkinter import filedialog
import sounddevice as sd
import soundfile as sf
import threading

current_audio = None

def load_folder():
    folder = filedialog.askdirectory()
    if not folder:
        return
    listbox.delete(0, tk.END)
    for file in sorted(os.listdir(folder)):
        if file.endswith((".wav", ".mp3")):
            listbox.insert(tk.END, os.path.join(folder, file))

def play_audio():
    global current_audio
    selection = listbox.curselection()
    if not selection:
        return

    filepath = listbox.get(selection[0])
    stop_audio()

    def _play():
        global current_audio
        data, sr = sf.read(filepath, dtype='float32')
        current_audio = sd.play(data, sr)
        sd.wait()

    threading.Thread(target=_play, daemon=True).start()

def stop_audio():
    sd.stop()

# ---------------- GUI ----------------
root = tk.Tk()
root.title("Stimulus Player")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

load_btn = tk.Button(frame, text="Load Folder", command=load_folder)
load_btn.pack(fill=tk.X)

listbox = tk.Listbox(frame, width=60, height=15)
listbox.pack(pady=5)

play_btn = tk.Button(frame, text="Play", command=play_audio)
play_btn.pack(fill=tk.X)

stop_btn = tk.Button(frame, text="Stop", command=stop_audio)
stop_btn.pack(fill=tk.X)

root.mainloop()