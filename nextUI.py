"""
Audio Perception Ranker
=======================
Install:  pip install pygame
Run:      python audio_ranker.py

Set AUDIO_FOLDER below to point at your audio files.
"""

import tkinter as tk
from tkinter import messagebox
import os
from datetime import datetime
import pygame

# ── CONFIG ────────────────────────────────────────────────────────────────────
AUDIO_FOLDER = "./audio"          # <-- change this to your folder path
# ─────────────────────────────────────────────────────────────────────────────

os.environ['SDL_AUDIODRIVER'] = 'directsound' if os.name == 'nt' else 'alsa'
pygame.mixer.init()

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')

BG      = "#0d0d0f"
SURFACE = "#141418"
BORDER  = "#2a2a32"
ACCENT  = "#c8f060"
TEXT    = "#e8e8ec"
MUTED   = "#666672"
NEG     = "#ff6b6b"
POS     = "#6bffb8"
BTN_BG  = "#1e1e24"


class AudioRatingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pitch Perception Ranker")
        self.root.geometry("1100x700")
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.audio_files = []    # list of [filepath, score]
        self.current_playing = None
        self.audio_widgets = []
        self._sort_job = None

        self._build_ui()
        self._load_folder()

    # ── UI SETUP ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill=tk.X, padx=24, pady=(24, 0))

        tk.Label(header, text="Pitch Perception Ranker",
                 bg=BG, fg=ACCENT, font=("Georgia", 20, "italic")).pack(side=tk.LEFT)

        self.folder_label = tk.Label(header, text="", bg=SURFACE, fg=MUTED,
                                     font=("Courier", 9), padx=10, pady=4)
        self.folder_label.pack(side=tk.RIGHT)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X, padx=24, pady=12)

        # Scrollable canvas
        canvas_frame = tk.Frame(self.root, bg=BG)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=24)

        self.canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical",
                                 command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        self._canvas_win = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(
                             self._canvas_win, width=e.width))

        self.canvas.bind_all("<MouseWheel>", self._on_scroll)
        self.canvas.bind_all("<Button-4>",   self._on_scroll)
        self.canvas.bind_all("<Button-5>",   self._on_scroll)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Footer
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X, padx=24, pady=(12, 0))

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill=tk.X, padx=24, pady=12)

        self.progress_label = tk.Label(footer, text="0 / 0 rated",
                                       bg=BG, fg=MUTED, font=("Courier", 10))
        self.progress_label.pack(side=tk.LEFT)

        tk.Button(footer, text="Clear All", bg=BTN_BG, fg=TEXT,
                  font=("Courier", 10), relief=tk.FLAT, padx=16, pady=6,
                  activebackground=BORDER, activeforeground=TEXT,
                  cursor="hand2", command=self._clear).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Button(footer, text="Export Results  v", bg=ACCENT, fg="#0d0d0f",
                  font=("Courier", 10, "bold"), relief=tk.FLAT, padx=16, pady=6,
                  activebackground="#d4f570", cursor="hand2",
                  command=self._export).pack(side=tk.RIGHT)

    def _on_scroll(self, event):
        if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1, "units")

    # ── LOAD ──────────────────────────────────────────────────────────────────

    def _load_folder(self):
        folder = os.path.abspath(AUDIO_FOLDER)
        if not os.path.isdir(folder):
            messagebox.showerror("Folder not found", f"Could not find:\n{folder}")
            return

        files = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(AUDIO_EXTENSIONS)
        ])

        if not files:
            messagebox.showwarning("No audio", "No audio files found in folder.")
            return

        self.audio_files = [[f, 0] for f in files]
        self.folder_label.config(text=folder)
        self._render()

    # ── RENDER ────────────────────────────────────────────────────────────────

    def _render(self):
        try:
            scroll_pos = self.canvas.yview()[0]
        except Exception:
            scroll_pos = 0.0

        for w in self.inner.winfo_children():
            w.destroy()
        self.audio_widgets = []

        order = sorted(range(len(self.audio_files)), key=lambda i: self.audio_files[i][1])

        for rank, idx in enumerate(order):
            self._make_row(rank, idx)

        self._update_progress()
        self.root.after(20, lambda: self.canvas.yview_moveto(scroll_pos))

    def _make_row(self, rank, index):
        filepath, score = self.audio_files[index]
        filename = os.path.basename(filepath)

        row = tk.Frame(self.inner, bg=SURFACE, pady=10, padx=14)
        row.pack(fill=tk.X, pady=4)

        # Rank badge
        tk.Label(row, text=str(rank + 1), bg=SURFACE, fg=MUTED,
                 font=("Courier", 10), width=3).grid(row=0, column=0, rowspan=2)

        # Play button
        is_playing = self.current_playing == index
        play_btn = tk.Button(
            row,
            text="||" if is_playing else ">",
            bg=BTN_BG, fg=ACCENT if is_playing else TEXT,
            font=("Courier", 12, "bold"), width=3, relief=tk.FLAT,
            activebackground=BORDER, activeforeground=ACCENT,
            cursor="hand2",
            command=lambda i=index: self._toggle_play(i)
        )
        play_btn.grid(row=0, column=1, rowspan=2, padx=(6, 14))

        # Filename
        tk.Label(row, text=filename, bg=SURFACE, fg=TEXT,
                 font=("Courier", 10), anchor="w").grid(
            row=0, column=2, sticky="w", pady=(0, 4))

        # Slider row
        slider_frame = tk.Frame(row, bg=SURFACE)
        slider_frame.grid(row=1, column=2, sticky="ew")

        tk.Label(slider_frame, text="-10", bg=SURFACE, fg=NEG,
                 font=("Courier", 8)).pack(side=tk.LEFT)

        slider = tk.Scale(
            slider_frame, from_=-10, to=10, resolution=1,
            orient=tk.HORIZONTAL, showvalue=0,
            bg=SURFACE, fg=TEXT, troughcolor=BORDER,
            highlightthickness=0, activebackground=ACCENT,
            command=lambda val, i=index: self._on_slide(i, val)
        )
        slider.set(score)
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        tk.Label(slider_frame, text="+10", bg=SURFACE, fg=POS,
                 font=("Courier", 8)).pack(side=tk.LEFT)

        # Score display
        color = NEG if score < 0 else POS if score > 0 else MUTED
        score_lbl = tk.Label(
            row,
            text=f"{score:+d}" if score != 0 else "0",
            bg=SURFACE, fg=color,
            font=("Courier", 13, "bold"), width=5
        )
        score_lbl.grid(row=0, column=3, rowspan=2, padx=(14, 0))

        row.grid_columnconfigure(2, weight=1)

        self.audio_widgets.append({
            'index': index,
            'play_btn': play_btn,
            'score_lbl': score_lbl,
            'slider': slider,
        })

    # ── PLAYBACK ──────────────────────────────────────────────────────────────

    def _toggle_play(self, index):
        try:
            filepath = self.audio_files[index][0]

            if self.current_playing is not None and self.current_playing != index:
                pygame.mixer.music.stop()
                self._set_play_icon(self.current_playing, playing=False)

            if self.current_playing == index:
                pygame.mixer.music.stop()
                self._set_play_icon(index, playing=False)
                self.current_playing = None
            else:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                self._set_play_icon(index, playing=True)
                self.current_playing = index
                self.root.after(100, lambda: self._check_end(index))

        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _set_play_icon(self, index, playing):
        for w in self.audio_widgets:
            if w['index'] == index:
                w['play_btn'].config(
                    text="||" if playing else ">",
                    fg=ACCENT if playing else TEXT
                )
                break

    def _check_end(self, index):
        if not pygame.mixer.music.get_busy() and self.current_playing == index:
            self._set_play_icon(index, playing=False)
            self.current_playing = None
        elif self.current_playing == index:
            self.root.after(100, lambda: self._check_end(index))

    # ── RATING ────────────────────────────────────────────────────────────────

    def _on_slide(self, index, val):
        score = int(float(val))
        self.audio_files[index][1] = score

        for w in self.audio_widgets:
            if w['index'] == index:
                color = NEG if score < 0 else POS if score > 0 else MUTED
                w['score_lbl'].config(
                    text=f"{score:+d}" if score != 0 else "0",
                    fg=color
                )
                break

        self._update_progress()

        if self._sort_job is not None:
            self.root.after_cancel(self._sort_job)
        self._sort_job = self.root.after(400, self._render)

    def _update_progress(self):
        rated = sum(1 for _, s in self.audio_files if s != 0)
        total = len(self.audio_files)
        self.progress_label.config(text=f"{rated} / {total} rated")

    # ── EXPORT ────────────────────────────────────────────────────────────────

    def _export(self):
        if not self.audio_files:
            messagebox.showwarning("No data", "No files loaded.")
            return

        sorted_files = sorted(self.audio_files, key=lambda x: x[1])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(os.path.abspath(AUDIO_FOLDER),
                                f"rankings_{timestamp}.txt")

        lines = [
            "=" * 60,
            "PITCH PERCEPTION RANKINGS",
            datetime.now().strftime("%B %d, %Y  %I:%M %p"),
            f"Folder: {os.path.abspath(AUDIO_FOLDER)}",
            f"Files:  {len(self.audio_files)}",
            "=" * 60, ""
        ]

        for rank, (path, score) in enumerate(sorted_files, 1):
            sign = "+" if score > 0 else ""
            lines.append(f"  {rank:>2}.  [{sign}{int(score):>3}]  {os.path.basename(path)}")

        lines += ["", "=" * 60]

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        messagebox.showinfo("Saved", f"Rankings saved to:\n{out_path}")

    # ── CLEAR ─────────────────────────────────────────────────────────────────

    def _clear(self):
        if not self.audio_files:
            return
        if messagebox.askyesno("Clear", "Reset all ratings to 0?"):
            if self.current_playing is not None:
                pygame.mixer.music.stop()
                self.current_playing = None
            for item in self.audio_files:
                item[1] = 0
            self._render()


def main():
    root = tk.Tk()
    AudioRatingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()