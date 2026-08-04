"""
test_ports.py — audio device tester
Uses subprocess + sounddevice for safe per-device tone playback on Windows.
"""

import tkinter as tk
from tkinter import messagebox
import sys
import os
import subprocess

HERE        = os.path.dirname(os.path.abspath(__file__))
TONE_SCRIPT = os.path.join(HERE, "_tone.py")


class TestPortsWindow:
    def __init__(self, root, on_done):
        self.root    = root
        self.on_done = on_done
        self.root.title("Step 1 — Test Audio Ports")
        self.root.geometry("700x560")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")
        self._build()

    def _build(self):
        tk.Label(self.root, text="Step 1: Test Audio Ports",
                 bg="#f5f5f5", font=("Arial", 16, "bold")).pack(pady=(20, 4), padx=24, anchor="w")
        tk.Label(self.root,
                 text="Play a tone on each device to identify your headphone and haptic outputs.\n"
                      "Then enter the two device IDs at the bottom and click Confirm.",
                 bg="#f5f5f5", fg="#555", font=("Arial", 10),
                 justify="left").pack(padx=24, anchor="w")

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=24, pady=12)

        wrap = tk.Frame(self.root, bg="#f5f5f5")
        wrap.pack(fill=tk.BOTH, expand=True, padx=24)

        canvas = tk.Canvas(wrap, bg="#f5f5f5", highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#f5f5f5")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cwin, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            -1 if (e.delta > 0 or e.num == 4) else 1, "units"))
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        try:
            import sounddevice as sd
            devices = [(i, d) for i, d in enumerate(sd.query_devices())
                       if d['max_output_channels'] > 0]
        except Exception:
            devices = []

        for dev_id, dev in devices:
            row = tk.Frame(inner, bg="white",
                           highlightbackground="#ddd", highlightthickness=1)
            row.pack(fill=tk.X, pady=3)
            ri = tk.Frame(row, bg="white")
            ri.pack(fill=tk.X, padx=12, pady=8)

            tk.Label(ri, text=f"[{dev_id}]", bg="white", fg="#888",
                     font=("Courier", 10), width=5, anchor="w").pack(side=tk.LEFT)
            tk.Label(ri, text=dev['name'], bg="white", fg="#222",
                     font=("Arial", 10), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

            status = tk.Label(ri, text="", bg="white", fg="#27ae60", font=("Arial", 9))
            status.pack(side=tk.LEFT, padx=(8, 0))

            tk.Button(ri, text="Play Tone", font=("Arial", 9),
                      bg="#e0e0e0", relief=tk.FLAT, padx=10, pady=4,
                      cursor="hand2",
                      command=lambda d=dev_id, s=status: self._play(d, s)
                      ).pack(side=tk.RIGHT)

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=24, pady=(12, 0))

        entry_frame = tk.Frame(self.root, bg="#f5f5f5")
        entry_frame.pack(fill=tk.X, padx=24, pady=14)

        tk.Label(entry_frame, text="Headphone device ID:", bg="#f5f5f5",
                 font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.audio_entry = tk.Entry(entry_frame, font=("Courier", 11), width=6,
                                    relief=tk.SOLID, bd=1)
        self.audio_entry.grid(row=0, column=1, sticky="w", padx=(10, 40))

        tk.Label(entry_frame, text="Haptic device ID:", bg="#f5f5f5",
                 font=("Arial", 10)).grid(row=0, column=2, sticky="w", pady=4)
        self.haptic_entry = tk.Entry(entry_frame, font=("Courier", 11), width=6,
                                     relief=tk.SOLID, bd=1)
        self.haptic_entry.grid(row=0, column=3, sticky="w", padx=(10, 0))

        tk.Button(self.root, text="Confirm & Continue →",
                  font=("Arial", 11, "bold"), bg="#333", fg="white",
                  relief=tk.FLAT, padx=20, pady=8, cursor="hand2",
                  activebackground="#555",
                  command=self._confirm).pack(pady=(0, 20))

    def _play(self, device_id, status_label):
        status_label.config(text="playing...")
        self.root.update()
        subprocess.Popen(
            [sys.executable, TONE_SCRIPT, str(device_id)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.root.after(2000, lambda: status_label.config(text="done"))

    def _confirm(self):
        try:
            audio_id  = int(self.audio_entry.get().strip())
            haptic_id = int(self.haptic_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter valid integer device IDs.")
            return
        self.root.destroy()
        self.on_done(audio_id, haptic_id)