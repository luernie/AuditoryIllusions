"""
flashcard_ui.py — flashcard rating phase
3 separate runs of n×3 randomized audio/modality cards, with breaks between.
"""

import tkinter as tk
from tkinter import messagebox
import os
import sys
import subprocess
import random

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')

MODALITY_LABEL = {
    "audio":  "Audio only",
    "haptic": "Haptic only",
    "both":   "Audio + Haptic",
}

HERE          = os.path.dirname(os.path.abspath(__file__))
PLAYER_SCRIPT = os.path.join(HERE, "_player.py")

NUM_RUNS = 3


def show_break_screen(root, message, button_text, on_continue):
    for w in root.winfo_children():
        w.destroy()
    root.configure(bg="#f5f5f5")
    root.geometry("480x280")
    root.resizable(False, False)
    outer = tk.Frame(root, bg="#f5f5f5")
    outer.place(relx=0.5, rely=0.5, anchor="center")
    tk.Label(outer, text=message, bg="#f5f5f5", fg="#333",
             font=("Arial", 14), justify="center").pack(pady=(0, 32))
    tk.Button(outer, text=button_text,
              font=("Arial", 11, "bold"), bg="#333", fg="white",
              relief=tk.FLAT, padx=24, pady=10,
              activebackground="#555", cursor="hand2",
              command=on_continue).pack()


class FlashcardWindow:
    def __init__(self, root, exp_config, audio_device, haptic_device, on_complete):
        self.root          = root
        self.exp_config    = exp_config
        self.folder        = exp_config["folder"]
        self.audio_device  = audio_device
        self.haptic_device = haptic_device
        self.on_complete   = on_complete

        self.root.title("Rating Task")
        self.root.configure(bg="#f5f5f5")

        self.results            = []
        self._procs             = []
        self._current_run       = 0
        self._current_run_cards = []
        self._card_idx          = 0
        self._score             = 0.0

        self._files = sorted([
            os.path.join(os.path.abspath(self.folder), f)
            for f in os.listdir(os.path.abspath(self.folder))
            if f.lower().endswith(AUDIO_EXTENSIONS)
        ])

        show_break_screen(
            self.root,
            "You are about to begin the rating task.\n\nTake a moment to get ready.",
            "Begin →",
            self._start_next_run
        )

    def _start_next_run(self):
        if self._current_run >= NUM_RUNS:
            self.root.destroy()
            self.on_complete(self.results)
            return
        run_num = self._current_run + 1
        cards = [
            (run_num, os.path.basename(fp), fp, mod)
            for fp in self._files
            for mod in ["audio", "haptic", "both"]
        ]
        random.shuffle(cards)
        self._current_run_cards = cards
        self._card_idx = 0
        self._build_card_ui()
        self._show_card()

    def _on_run_complete(self):
        self._current_run += 1
        self._stop_all()
        if self._current_run >= NUM_RUNS:
            self.root.destroy()
            self.on_complete(self.results)
        else:
            show_break_screen(
                self.root,
                "Time to take a short break.\n\nRelax for a moment before continuing.",
                "Continue →",
                self._start_next_run
            )

    def _build_card_ui(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("560x460")
        self.root.resizable(False, False)

        banner = tk.Frame(self.root, bg="#f0f0f0",
                          highlightbackground="#ddd", highlightthickness=1)
        banner.pack(fill=tk.X, padx=20, pady=(16, 0))
        bi = tk.Frame(banner, bg="#f0f0f0")
        bi.pack(fill=tk.X, padx=16, pady=10)
        tk.Label(bi, text="Rating Task",
                 bg="#f0f0f0", font=("Arial", 13, "bold")).pack(anchor="w")
        tk.Label(bi,
                 text=self.exp_config["instructions"],
                 bg="#f0f0f0", fg="#333", font=("Arial", 9),
                 justify="left").pack(anchor="w", pady=(4, 0))

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=12)

        card = tk.Frame(self.root, bg="white",
                        highlightbackground="#ddd", highlightthickness=1)
        card.pack(fill=tk.X, padx=20)
        ci = tk.Frame(card, bg="white")
        ci.pack(fill=tk.X, padx=20, pady=20)

        self.modality_lbl = tk.Label(ci, text="", bg="white", fg="#555",
                                     font=("Arial", 10))
        self.modality_lbl.pack(anchor="w", pady=(0, 14))

        self.play_btn = tk.Button(ci, text="▶  Play", bg="#e8e8e8", fg="#333",
                                  font=("Arial", 11), relief=tk.FLAT, padx=16, pady=6,
                                  activebackground="#ddd", cursor="hand2",
                                  command=self._play)
        self.play_btn.pack(anchor="w", pady=(0, 16))

        slider_row = tk.Frame(ci, bg="white")
        slider_row.pack(fill=tk.X)
        tk.Label(slider_row, text="-10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)
        self.slider = tk.Scale(slider_row, from_=-10.0, to=10.0, resolution=0.1,
                               orient=tk.HORIZONTAL, showvalue=0, bg="white",
                               troughcolor="#e0e0e0", highlightthickness=0, bd=0,
                               command=self._on_slide)
        self.slider.set(0.0)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Label(slider_row, text="+10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)

        self.score_lbl = tk.Label(ci, text="0.0", bg="white", fg="#aaa",
                                   font=("Arial", 12, "bold"))
        self.score_lbl.pack(anchor="e", pady=(6, 0))

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=(12, 0))
        footer = tk.Frame(self.root, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=20, pady=10)

        self.progress_lbl = tk.Label(footer, text="", bg="#f5f5f5",
                                     fg="#aaa", font=("Arial", 9))
        self.progress_lbl.pack(side=tk.LEFT)

        self.next_btn = tk.Button(footer, text="Next →",
                                  font=("Arial", 11, "bold"), bg="#333", fg="white",
                                  relief=tk.FLAT, padx=18, pady=7,
                                  activebackground="#555", cursor="hand2",
                                  command=self._next)
        self.next_btn.pack(side=tk.RIGHT)

    def _show_card(self):
        self._stop_all()
        self._score = 0.0
        self.slider.set(0.0)
        self.score_lbl.config(text="0.0", fg="#aaa")
        self.play_btn.config(text="▶  Play", fg="#333")
        run, filename, filepath, modality = self._current_run_cards[self._card_idx]
        self._current_filepath = filepath
        self._current_modality = modality
        if self.exp_config.get("show_condition", True):
            self.modality_lbl.config(text=f"Condition: {MODALITY_LABEL[modality]}")
        else:
            self.modality_lbl.config(text="")
        if self.exp_config.get("show_progress", True):
            self.progress_lbl.config(text=f"{self._card_idx + 1} / {len(self._current_run_cards)}")
        else:
            self.progress_lbl.config(text="")

    def _next(self):
        self._stop_all()
        run, filename, filepath, modality = self._current_run_cards[self._card_idx]
        self.results.append({
            "run": run, "filename": filename,
            "modality": modality, "score": self._score,
        })
        self._card_idx += 1
        if self._card_idx >= len(self._current_run_cards):
            self._on_run_complete()
        else:
            self._show_card()

    def _on_slide(self, val):
        self._score = round(float(val), 1)
        v = self._score
        color = "#c0392b" if v < 0 else "#27ae60" if v > 0 else "#aaa"
        self.score_lbl.config(text=f"{v:+.1f}" if v != 0 else "0.0", fg=color)

    def _play(self):
        self._stop_all()
        try:
            if self._current_modality == "audio":
                self._launch(self.audio_device,  self._current_filepath)
            elif self._current_modality == "haptic":
                self._launch(self.haptic_device, self._current_filepath)
            elif self._current_modality == "both":
                self._launch(self.audio_device,  self._current_filepath)
                self._launch(self.haptic_device, self._current_filepath)
            self.play_btn.config(text="■  Playing", fg="#555")
            self.root.after(200, self._check_end)
        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _launch(self, device_id, filepath):
        proc = subprocess.Popen(
            [sys.executable, PLAYER_SCRIPT, str(device_id), filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._procs.append(proc)

    def _stop_all(self):
        for proc in self._procs:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        self._procs.clear()

    def _check_end(self):
        self._procs = [p for p in self._procs if p.poll() is None]
        if not self._procs:
            try:
                self.play_btn.config(text="▶  Play", fg="#333")
            except Exception:
                pass
        else:
            self.root.after(200, self._check_end)