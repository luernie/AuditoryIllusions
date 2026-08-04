"""
rating_ui.py — ranking screen for one block
"""

import tkinter as tk
from tkinter import messagebox
import os
import sys
import subprocess
import random
import time

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')

MODALITY_LABEL = {
    "audio":  "Audio only",
    "haptic": "Haptic only",
    "both":   "Audio + Haptic",
}

HERE          = os.path.dirname(os.path.abspath(__file__))
PLAYER_SCRIPT = os.path.join(HERE, "_player.py")
NOISE_SCRIPT  = os.path.join(HERE, "_noise.py")


class RatingWindow:
    def __init__(self, root, exp_config, modality, audio_device, haptic_device, on_complete,
                 block_number=None, total_blocks=None):
        self.root          = root
        self.exp_config    = exp_config
        self.modality      = modality
        self.folder        = exp_config["folder"]
        self.audio_device  = audio_device
        self.haptic_device = haptic_device
        self.on_complete   = on_complete
        self.block_number  = block_number
        self.total_blocks  = total_blocks

        self.audio_files     = []
        self.current_playing = None
        self.rows            = []
        self._sort_job       = None
        self._procs          = []

        self._build_ui()
        self._load_files()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        mod_label = MODALITY_LABEL[self.modality]
        set_label = (f"Set {self.block_number}/{self.total_blocks} — "
                     if self.block_number and self.total_blocks else "")
        self.root.title(f"{set_label}{self.exp_config['ui_title']} — {mod_label}")
        self.root.state("zoomed")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        banner = tk.Frame(self.root, bg="#f0f0f0",
                          highlightbackground="#ddd", highlightthickness=1)
        banner.pack(fill=tk.X, padx=20, pady=(16, 0))
        bi = tk.Frame(banner, bg="#f0f0f0")
        bi.pack(fill=tk.X, padx=20, pady=16)

        tk.Label(bi, text=self.exp_config["ui_title"],
                 bg="#f0f0f0", font=("Arial", 18, "bold")).pack(anchor="w")

        if self.exp_config.get("show_condition", True):
            tk.Label(bi, text=f"Condition: {mod_label}",
                     bg="#f0f0f0", fg="#555", font=("Arial", 12)).pack(anchor="w", pady=(2, 10))

        for heading, text in self.exp_config.get("definitions", []):
            tk.Label(bi, text=heading, bg="#f0f0f0", fg="#111",
                     font=("Arial", 13, "bold")).pack(anchor="w", pady=(6, 0))
            tk.Label(bi, text=text, bg="#f0f0f0", fg="#333",
                     font=("Arial", 12), justify="left",
                     wraplength=1000).pack(anchor="w")

        bullets_frame = tk.Frame(bi, bg="#f0f0f0")
        bullets_frame.pack(anchor="w", pady=(12, 0), fill=tk.X)
        for bullet in self.exp_config.get("rating_bullets", []):
            tk.Label(bullets_frame, text=f"•  {bullet}", bg="#f0f0f0", fg="#111",
                     font=("Arial", 13), justify="left",
                     wraplength=1000).pack(anchor="w", pady=2)

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=10)

        wrap = tk.Frame(self.root, bg="#f5f5f5")
        wrap.pack(fill=tk.BOTH, expand=True, padx=20)

        self.canvas = tk.Canvas(wrap, bg="#f5f5f5", highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="#f5f5f5")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._cwin = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._cwin, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_scroll)
        self.canvas.bind_all("<Button-4>",   self._on_scroll)
        self.canvas.bind_all("<Button-5>",   self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=(10, 0))

        footer = tk.Frame(self.root, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=20, pady=10)
        self.progress_label = tk.Label(footer, text="", bg="#f5f5f5",
                                       fg="#888", font=("Arial", 10))
        self.progress_label.pack(side=tk.LEFT)
        tk.Button(footer, text="Save & Continue →",
                  font=("Arial", 12, "bold"), bg="#333", fg="white",
                  relief=tk.FLAT, padx=22, pady=10,
                  activebackground="#555", cursor="hand2",
                  command=self._save_and_continue).pack(side=tk.RIGHT)

    def _on_scroll(self, event):
        if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1, "units")

    # ── LOAD ──────────────────────────────────────────────────────────────────

    def _load_files(self):
        folder = os.path.abspath(self.folder)
        files = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(AUDIO_EXTENSIONS)
        ])
        if not files:
            messagebox.showwarning("No audio", f"No audio files found in:\n{folder}")
            return
        random.shuffle(files)
        self.audio_files = [[f, 0.0] for f in files]
        self._build_rows()
        self._update_progress()

    # ── ROWS ──────────────────────────────────────────────────────────────────

    def _build_rows(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = []
        for index in range(len(self.audio_files)):
            row = self._make_row(index)
            self.rows.append(row)
            row.pack(fill=tk.X, pady=3)

    def _make_row(self, index):
        row = tk.Frame(self.inner, bg="white",
                       highlightbackground="#ddd", highlightthickness=1)
        inner = tk.Frame(row, bg="white")
        inner.pack(fill=tk.X, padx=12, pady=10)

        rank_lbl = tk.Label(inner, text=str(index + 1), bg="white",
                            fg="#aaa", font=("Arial", 11), width=3, anchor="e")
        rank_lbl.grid(row=0, column=0, padx=(0, 10))

        play_btn = tk.Button(inner, text="▶", bg="white", fg="#333",
                             font=("Arial", 11), width=2, relief=tk.FLAT,
                             activebackground="#eee", cursor="hand2",
                             command=lambda i=index: self._toggle_play(i))
        play_btn.grid(row=0, column=1, padx=(0, 16))

        slider_frame = tk.Frame(inner, bg="white")
        slider_frame.grid(row=0, column=2, sticky="ew")
        tk.Label(slider_frame, text="-10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)
        slider = tk.Scale(slider_frame, from_=-10.0, to=10.0, resolution=0.1,
                          orient=tk.HORIZONTAL, showvalue=0, bg="white",
                          troughcolor="#e8e8e8", highlightthickness=0, bd=0,
                          state=tk.DISABLED,
                          command=lambda val, i=index: self._on_slide(i, val))
        slider.set(0.0)
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(slider_frame, text="+10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)

        score_lbl = tk.Label(inner, text="0.0", bg="white", fg="#ddd",
                              font=("Arial", 12, "bold"), width=6, anchor="e")
        score_lbl.grid(row=0, column=3, padx=(10, 0))

        inner.grid_columnconfigure(2, weight=1)

        row._index     = index
        row._rank_lbl  = rank_lbl
        row._play_btn  = play_btn
        row._score_lbl = score_lbl
        row._slider    = slider
        row._played    = False
        return row

    def _resort(self):
        sorted_rows = sorted(self.rows, key=lambda r: self.audio_files[r._index][1])
        for i, row in enumerate(sorted_rows):
            row.pack_forget()
            row.pack(fill=tk.X, pady=3)
            row._rank_lbl.config(text=str(i + 1))

    # ── PLAYBACK ──────────────────────────────────────────────────────────────

    def _toggle_play(self, index):
        filepath = self.audio_files[index][0]
        self._stop_all()
        if self.current_playing == index:
            self._set_icon(index, False)
            self.current_playing = None
            return
        try:
            if self.modality == "audio":
                self._launch(self.audio_device, filepath)
            elif self.modality == "haptic":
                self._launch(self.haptic_device, filepath)
                self._launch_noise(self.audio_device, filepath)
            elif self.modality == "both":
                self._launch(self.audio_device,  filepath)
                self._launch(self.haptic_device, filepath)
            self._set_icon(index, True)
            self.current_playing = index
            self.root.after(200, lambda: self._check_end(index))
            for row in self.rows:
                if row._index == index and not row._played:
                    row._played = True
                    row._slider.config(state=tk.NORMAL, troughcolor="#e0e0e0")
                    row._score_lbl.config(fg="#222")
                    break
        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _launch(self, device_id, filepath):
        proc = subprocess.Popen(
            [sys.executable, PLAYER_SCRIPT, str(device_id), filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._procs.append(proc)

    def _launch_noise(self, device_id, filepath):
        import soundfile as sf
        try:
            duration = sf.info(filepath).duration
        except Exception:
            duration = 10.0
        log = open(os.path.join(HERE, '_noise_error.log'), 'a')
        proc = subprocess.Popen(
            [sys.executable, NOISE_SCRIPT, str(device_id), str(duration)],
            stdout=subprocess.DEVNULL, stderr=log)
        self._procs.append(proc)

    def _stop_all(self):
        for proc in self._procs:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        self._procs.clear()
        if self.current_playing is not None:
            self._set_icon(self.current_playing, False)

    def _set_icon(self, index, playing):
        for row in self.rows:
            if row._index == index:
                row._play_btn.config(text="■" if playing else "▶")
                break

    def _check_end(self, index):
        self._procs = [p for p in self._procs if p.poll() is None]
        if not self._procs and self.current_playing == index:
            self._set_icon(index, False)
            self.current_playing = None
        elif self.current_playing == index:
            self.root.after(200, lambda: self._check_end(index))

    # ── RATING ────────────────────────────────────────────────────────────────

    def _on_slide(self, index, val):
        score = round(float(val), 1)
        self.audio_files[index][1] = score
        for row in self.rows:
            if row._index == index:
                color = "#c0392b" if score < 0 else "#27ae60" if score > 0 else "#aaa"
                row._score_lbl.config(
                    text=f"{score:+.1f}" if score != 0 else "0.0", fg=color)
                break
        self._update_progress()
        if self._sort_job is not None:
            self.root.after_cancel(self._sort_job)
        self._sort_job = self.root.after(500, self._resort)

    def _update_progress(self):
        if not self.exp_config.get("show_progress", True):
            self.progress_label.config(text="")
            return
        rated = sum(1 for _, s in self.audio_files if s != 0.0)
        total = len(self.audio_files)
        self.progress_label.config(text=f"{rated} / {total} rated")

    # ── SAVE ──────────────────────────────────────────────────────────────────

    def _save_and_continue(self):
        self._stop_all()
        self.current_playing = None
        for _ in range(20):
            self._procs = [p for p in self._procs if p.poll() is None]
            if not self._procs:
                break
            time.sleep(0.1)
        time.sleep(0.3)
        ratings = [(os.path.basename(f), s) for f, s in self.audio_files]
        self.root.destroy()
        self.on_complete(ratings)