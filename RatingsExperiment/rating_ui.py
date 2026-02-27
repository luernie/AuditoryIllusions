"""
rating_ui.py — rating screen for one block
"""

import tkinter as tk
from tkinter import messagebox
import os
import pygame

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')

MODALITY_LABEL = {
    "audio":  "Audio only",
    "haptic": "Haptic only",
    "both":   "Audio + Haptic",
}

INSTRUCTIONS = (
    "Listen to each audio sample and rate how you perceive the tempo using the slider:\n"
    "  -10 = strongly slowing down          +10 = strongly speeding up\n"
    "     0 = no clear change in tempo\n\n"
    "You can replay a sample as many times as you like before rating it.\n"
    "When you have rated all samples, press Save & Continue."
)


class RatingWindow:
    def __init__(self, root, stimulus, modality, folder,
                 audio_device, haptic_device, on_complete):
        self.root          = root
        self.stimulus      = stimulus
        self.modality      = modality
        self.folder        = folder
        self.audio_device  = audio_device
        self.haptic_device = haptic_device
        self.on_complete   = on_complete

        self.audio_files    = []
        self.current_playing = None
        self.rows           = []
        self._sort_job      = None

        pygame.mixer.init()
        self._build_ui()
        self._load_files()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        mod_label = MODALITY_LABEL[self.modality]
        self.root.title(f"Risset Rhythm — {mod_label}")
        self.root.geometry("860x660")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        # Instructions banner
        banner = tk.Frame(self.root, bg="#f0f0f0",
                          highlightbackground="#ddd", highlightthickness=1)
        banner.pack(fill=tk.X, padx=20, pady=(16, 0))

        bi = tk.Frame(banner, bg="#f0f0f0")
        bi.pack(fill=tk.X, padx=16, pady=12)

        tk.Label(bi, text="Risset Rhythm — Tempo Perception",
                 bg="#f0f0f0", font=("Arial", 13, "bold")).pack(anchor="w")
        tk.Label(bi, text=f"Condition: {mod_label}",
                 bg="#f0f0f0", fg="#555", font=("Arial", 10)).pack(anchor="w", pady=(2, 6))
        tk.Label(bi, text=INSTRUCTIONS, bg="#f0f0f0", fg="#333",
                 font=("Arial", 9), justify="left").pack(anchor="w")

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=10)

        # Scrollable list
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

        # Footer
        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=(10, 0))

        footer = tk.Frame(self.root, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=20, pady=10)

        self.progress_label = tk.Label(footer, text="", bg="#f5f5f5",
                                       fg="#888", font=("Arial", 10))
        self.progress_label.pack(side=tk.LEFT)

        tk.Button(footer, text="Save & Continue →",
                  font=("Arial", 11, "bold"), bg="#333", fg="white",
                  relief=tk.FLAT, padx=18, pady=7,
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

        play_btn = tk.Button(
            inner, text="▶", bg="white", fg="#333",
            font=("Arial", 11), width=2, relief=tk.FLAT,
            activebackground="#eee", cursor="hand2",
            command=lambda i=index: self._toggle_play(i)
        )
        play_btn.grid(row=0, column=1, padx=(0, 16))

        slider_frame = tk.Frame(inner, bg="white")
        slider_frame.grid(row=0, column=2, sticky="ew")

        tk.Label(slider_frame, text="-10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)

        slider = tk.Scale(
            slider_frame, from_=-10.0, to=10.0, resolution=0.1,
            orient=tk.HORIZONTAL, showvalue=0,
            bg="white", troughcolor="#e0e0e0",
            highlightthickness=0, bd=0,
            command=lambda val, i=index: self._on_slide(i, val)
        )
        slider.set(0.0)
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        tk.Label(slider_frame, text="+10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)

        score_lbl = tk.Label(inner, text="0.0", bg="white", fg="#aaa",
                              font=("Arial", 12, "bold"), width=6, anchor="e")
        score_lbl.grid(row=0, column=3, padx=(10, 0))

        inner.grid_columnconfigure(2, weight=1)

        row._index    = index
        row._rank_lbl = rank_lbl
        row._play_btn = play_btn
        row._score_lbl = score_lbl
        row._slider   = slider
        return row

    def _resort(self):
        sorted_rows = sorted(self.rows, key=lambda r: self.audio_files[r._index][1])
        for i, row in enumerate(sorted_rows):
            row.pack_forget()
            row.pack(fill=tk.X, pady=3)
            row._rank_lbl.config(text=str(i + 1))

    # ── PLAYBACK ──────────────────────────────────────────────────────────────

    def _toggle_play(self, index):
        try:
            filepath = self.audio_files[index][0]

            if self.current_playing is not None and self.current_playing != index:
                self._stop_all()
                self._set_icon(self.current_playing, False)

            if self.current_playing == index:
                self._stop_all()
                self._set_icon(index, False)
                self.current_playing = None
            else:
                self._play_on_devices(filepath)
                self._set_icon(index, True)
                self.current_playing = index
                self.root.after(200, lambda: self._check_end(index))

        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _stop_all(self):
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _play_on_devices(self, filepath):
        import sounddevice as sd
        import soundfile as sf
        import threading

        def play_to(device_id):
            try:
                data, sr = sf.read(filepath)
                sd.play(data, sr, device=device_id)
                sd.wait()
            except Exception:
                pass

        if self.modality == "audio":
            threading.Thread(target=play_to, args=(self.audio_device,),  daemon=True).start()
        elif self.modality == "haptic":
            threading.Thread(target=play_to, args=(self.haptic_device,), daemon=True).start()
        elif self.modality == "both":
            threading.Thread(target=play_to, args=(self.audio_device,),  daemon=True).start()
            threading.Thread(target=play_to, args=(self.haptic_device,), daemon=True).start()

    def _set_icon(self, index, playing):
        for row in self.rows:
            if row._index == index:
                row._play_btn.config(text="■" if playing else "▶")
                break

    def _check_end(self, index):
        import sounddevice as sd
        try:
            still_playing = sd.get_stream().active
        except Exception:
            still_playing = False

        if not still_playing and self.current_playing == index:
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
                    text=f"{score:+.1f}" if score != 0 else "0.0",
                    fg=color
                )
                break

        self._update_progress()

        if self._sort_job is not None:
            self.root.after_cancel(self._sort_job)
        self._sort_job = self.root.after(500, self._resort)

    def _update_progress(self):
        rated = sum(1 for _, s in self.audio_files if s != 0.0)
        total = len(self.audio_files)
        self.progress_label.config(text=f"{rated} / {total} rated")

    # ── SAVE ──────────────────────────────────────────────────────────────────

    def _save_and_continue(self):
        if self.current_playing is not None:
            self._stop_all()
            self.current_playing = None

        ratings = [(os.path.basename(f), s) for f, s in self.audio_files]
        self.root.destroy()
        self.on_complete(ratings)