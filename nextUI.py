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
AUDIO_FOLDER = "AudioRatingRR"   # <-- change this to your folder path
# ─────────────────────────────────────────────────────────────────────────────

os.environ['SDL_AUDIODRIVER'] = 'directsound' if os.name == 'nt' else 'alsa'
pygame.mixer.init()

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')


class AudioRatingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Ranker")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        self.audio_files = []   # list of [filepath, score]
        self.current_playing = None
        self.rows = []          # row frames in order of creation
        self._sort_job = None

        self._build_ui()
        self._load_folder()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#f5f5f5")
        header.pack(fill=tk.X, padx=20, pady=(16, 4))

        tk.Label(header, text="Audio Ranker", bg="#f5f5f5",
                 font=("Arial", 16, "bold")).pack(side=tk.LEFT)

        self.progress_label = tk.Label(header, text="", bg="#f5f5f5",
                                       fg="#888", font=("Arial", 10))
        self.progress_label.pack(side=tk.RIGHT)

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20, pady=(8, 0))

        wrap = tk.Frame(self.root, bg="#f5f5f5")
        wrap.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

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

        tk.Frame(self.root, bg="#ddd", height=1).pack(fill=tk.X, padx=20)

        footer = tk.Frame(self.root, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=20, pady=10)

        tk.Button(footer, text="Clear All", font=("Arial", 10),
                  relief=tk.FLAT, bg="#e0e0e0", padx=14, pady=6,
                  cursor="hand2", command=self._clear).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(footer, text="Export Results", font=("Arial", 10, "bold"),
                  relief=tk.FLAT, bg="#333", fg="white", padx=14, pady=6,
                  activebackground="#555", cursor="hand2",
                  command=self._export).pack(side=tk.RIGHT)

    def _on_scroll(self, event):
        if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1, "units")

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
        self._build_rows()
        self._update_progress()

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
            slider_frame, from_=-10, to=10, resolution=1,
            orient=tk.HORIZONTAL, showvalue=0,
            bg="white", troughcolor="#e0e0e0",
            highlightthickness=0, bd=0,
            command=lambda val, i=index: self._on_slide(i, val)
        )
        slider.set(0)
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        tk.Label(slider_frame, text="+10", bg="white", fg="#999",
                 font=("Arial", 8)).pack(side=tk.LEFT)

        score_lbl = tk.Label(inner, text="0", bg="white", fg="#aaa",
                              font=("Arial", 12, "bold"), width=4, anchor="e")
        score_lbl.grid(row=0, column=3, padx=(10, 0))

        inner.grid_columnconfigure(2, weight=1)

        row._index = index
        row._rank_lbl = rank_lbl
        row._play_btn = play_btn
        row._score_lbl = score_lbl
        row._slider = slider

        return row

    def _resort(self):
        sorted_rows = sorted(self.rows, key=lambda r: self.audio_files[r._index][1])
        for i, row in enumerate(sorted_rows):
            row.pack_forget()
            row.pack(fill=tk.X, pady=3)
            row._rank_lbl.config(text=str(i + 1))

    def _toggle_play(self, index):
        try:
            filepath = self.audio_files[index][0]

            if self.current_playing is not None and self.current_playing != index:
                pygame.mixer.music.stop()
                self._set_icon(self.current_playing, False)

            if self.current_playing == index:
                pygame.mixer.music.stop()
                self._set_icon(index, False)
                self.current_playing = None
            else:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                self._set_icon(index, True)
                self.current_playing = index
                self.root.after(100, lambda: self._check_end(index))

        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _set_icon(self, index, playing):
        for row in self.rows:
            if row._index == index:
                row._play_btn.config(text="■" if playing else "▶")
                break

    def _check_end(self, index):
        if not pygame.mixer.music.get_busy() and self.current_playing == index:
            self._set_icon(index, False)
            self.current_playing = None
        elif self.current_playing == index:
            self.root.after(100, lambda: self._check_end(index))

    def _on_slide(self, index, val):
        score = int(float(val))
        self.audio_files[index][1] = score

        for row in self.rows:
            if row._index == index:
                color = "#c0392b" if score < 0 else "#27ae60" if score > 0 else "#aaa"
                row._score_lbl.config(
                    text=f"{score:+d}" if score != 0 else "0",
                    fg=color
                )
                break

        self._update_progress()

        if self._sort_job is not None:
            self.root.after_cancel(self._sort_job)
        self._sort_job = self.root.after(500, self._resort)

    def _update_progress(self):
        rated = sum(1 for _, s in self.audio_files if s != 0)
        total = len(self.audio_files)
        self.progress_label.config(text=f"{rated} / {total} rated")

    def _export(self):
        if not self.audio_files:
            messagebox.showwarning("No data", "No files loaded.")
            return

        sorted_files = sorted(self.audio_files, key=lambda x: x[1])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(os.path.abspath(AUDIO_FOLDER),
                                f"rankings_{timestamp}.txt")

        lines = [
            "=" * 50,
            "AUDIO PERCEPTION RANKINGS",
            datetime.now().strftime("%B %d, %Y  %I:%M %p"),
            f"Folder: {os.path.abspath(AUDIO_FOLDER)}",
            f"Files:  {len(self.audio_files)}",
            "=" * 50, ""
        ]

        for rank, (path, score) in enumerate(sorted_files, 1):
            sign = "+" if score > 0 else ""
            lines.append(f"  {rank:>2}.  [{sign}{int(score):>3}]  {os.path.basename(path)}")

        lines += ["", "=" * 50]

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        messagebox.showinfo("Saved", f"Saved to:\n{out_path}")

    def _clear(self):
        if not self.audio_files:
            return
        if messagebox.askyesno("Clear", "Reset all ratings to 0?"):
            if self.current_playing is not None:
                pygame.mixer.music.stop()
                self.current_playing = None
            for item in self.audio_files:
                item[1] = 0
            for row in self.rows:
                row._slider.set(0)
                row._score_lbl.config(text="0", fg="#aaa")
            self._resort()
            self._update_progress()


def main():
    root = tk.Tk()
    AudioRatingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()