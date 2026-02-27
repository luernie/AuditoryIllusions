"""
main.py — experiment runner
============================
Install:  pip install pygame sounddevice soundfile
Run:      python main.py
"""

import tkinter as tk
from tkinter import messagebox
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_block_order, RISSET_FOLDER, OUTPUT_FOLDER
from test_ports import TestPortsWindow
from rating_ui import RatingWindow
from flashcard_ui import FlashcardWindow

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

state = {
    "participant":    None,
    "audio_device":  None,
    "haptic_device": None,
    "block_order":   [],
    "current_block": 0,
    "all_results":   [],
}


# ── STEP 0: Setup ─────────────────────────────────────────────────────────────

def show_setup():
    root = tk.Tk()
    root.title("Experiment Setup")
    root.geometry("420x240")
    root.resizable(False, False)
    root.configure(bg="#f5f5f5")

    tk.Label(root, text="Experiment Setup", bg="#f5f5f5",
             font=("Arial", 16, "bold")).pack(pady=(24, 4), padx=24, anchor="w")
    tk.Label(root, text="Enter participant number to begin.",
             bg="#f5f5f5", fg="#555", font=("Arial", 10)).pack(padx=24, anchor="w")

    tk.Frame(root, bg="#ddd", height=1).pack(fill=tk.X, padx=24, pady=14)

    f = tk.Frame(root, bg="#f5f5f5")
    f.pack(padx=24, fill=tk.X)

    tk.Label(f, text="Participant number:", bg="#f5f5f5",
             font=("Arial", 11)).grid(row=0, column=0, sticky="w", pady=8)
    p_entry = tk.Entry(f, font=("Courier", 12), width=8, relief=tk.SOLID, bd=1)
    p_entry.grid(row=0, column=1, sticky="w", padx=(12, 0))
    p_entry.focus()

    def on_start():
        try:
            p = int(p_entry.get().strip())
            if p < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Please enter a positive integer.")
            return

        state["participant"]   = p
        state["block_order"]   = get_block_order(p)
        state["current_block"] = 0
        state["all_results"]   = []

        order_str = "\n".join(
            f"  {i+1}. {mod}" for i, mod in enumerate(state["block_order"])
        )
        messagebox.showinfo(
            "Block order",
            f"Participant {p} — Block order:\n\n{order_str}\n\nNext: test your audio ports."
        )
        root.destroy()
        run_port_test()

    tk.Button(root, text="Start →", font=("Arial", 11, "bold"),
              bg="#333", fg="white", relief=tk.FLAT, padx=18, pady=8,
              activebackground="#555", cursor="hand2",
              command=on_start).pack(pady=20)

    root.mainloop()


# ── STEP 1: Port test ─────────────────────────────────────────────────────────

def run_port_test():
    root = tk.Tk()

    def on_done(audio_id, haptic_id):
        state["audio_device"]  = audio_id
        state["haptic_device"] = haptic_id
        run_next_block()

    TestPortsWindow(root, on_done)
    root.mainloop()


# ── STEP 2–4: Ranking blocks ──────────────────────────────────────────────────

def run_next_block():
    idx   = state["current_block"]
    total = len(state["block_order"])

    if idx >= total:
        run_flashcards()
        return

    modality = state["block_order"][idx]

    root = tk.Tk()

    def on_complete(ratings):
        state["all_results"].append({
            "block":    idx + 1,
            "stimulus": "risset",
            "modality": modality,
            "ratings":  ratings,
        })
        state["current_block"] += 1
        export_block(state["all_results"][-1])
        run_next_block()

    RatingWindow(root, "risset", modality, RISSET_FOLDER,
                 state["audio_device"], state["haptic_device"], on_complete)
    root.mainloop()


# ── STEP 5: Break then flashcard phase ───────────────────────────────────────

def run_flashcards():
    root = tk.Tk()
    root.title("Break")
    root.geometry("480x280")
    root.resizable(False, False)

    from flashcard_ui import show_break_screen

    def on_break_done():
        def on_complete(results):
            export_flashcards(results)
            finish()
        FlashcardWindow(root, RISSET_FOLDER,
                        state["audio_device"], state["haptic_device"],
                        on_complete)

    show_break_screen(
        root,
        "Great work — the first part is complete.\n\nTake a short break before continuing.",
        "Continue →",
        on_break_done
    )
    root.mainloop()


# ── EXPORT: ranking block ─────────────────────────────────────────────────────

def export_block(block_result):
    p   = state["participant"]
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    mod = block_result["modality"]

    filename = f"p{p:03d}_block{block_result['block']:02d}_risset_{mod}_{ts}.csv"
    out_path = os.path.join(OUTPUT_FOLDER, filename)

    sorted_ratings = sorted(block_result["ratings"], key=lambda x: x[1])

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Block", "Stimulus", "Modality",
                         "Rank", "Filename", "Score"])
        for rank, (fname, score) in enumerate(sorted_ratings, 1):
            writer.writerow([p, block_result["block"], "risset", mod,
                             rank, fname, score])

    print(f"Saved: {out_path}")


# ── EXPORT: flashcards ────────────────────────────────────────────────────────

def export_flashcards(results):
    p  = state["participant"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Per-trial CSV
    trial_path = os.path.join(OUTPUT_FOLDER, f"p{p:03d}_flashcards_{ts}.csv")
    with open(trial_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Run", "Filename", "Modality", "Score"])
        for r in results:
            writer.writerow([p, r["run"], r["filename"], r["modality"], r["score"]])

    # Averages CSV — one row per (filename, modality) with scores for each run + average
    from collections import defaultdict
    grouped = defaultdict(dict)   # grouped[(filename, modality)][run] = score
    for r in results:
        grouped[(r["filename"], r["modality"])][r["run"]] = r["score"]

    avg_path = os.path.join(OUTPUT_FOLDER, f"p{p:03d}_flashcards_averages_{ts}.csv")
    with open(avg_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Filename", "Modality",
                         "Score_Run1", "Score_Run2", "Score_Run3", "Average"])
        for (fname, mod), runs in sorted(grouped.items()):
            s1 = runs.get(1, "")
            s2 = runs.get(2, "")
            s3 = runs.get(3, "")
            scores = [s for s in [s1, s2, s3] if s != ""]
            avg = round(sum(scores) / len(scores), 3) if scores else ""
            writer.writerow([p, fname, mod, s1, s2, s3, avg])

    print(f"Saved: {trial_path}")
    print(f"Saved: {avg_path}")


# ── FINISH ────────────────────────────────────────────────────────────────────

def finish():
    p  = state["participant"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Combined ranking summary
    out_path = os.path.join(OUTPUT_FOLDER, f"p{p:03d}_ranking_summary_{ts}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Block", "Stimulus", "Modality",
                         "Rank", "Filename", "Score"])
        for block in state["all_results"]:
            for rank, (fname, score) in enumerate(
                    sorted(block["ratings"], key=lambda x: x[1]), 1):
                writer.writerow([p, block["block"], "risset",
                                 block["modality"], rank, fname, score])

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "All done!",
        f"Experiment complete for participant {p}.\n\nResults saved to:\n{OUTPUT_FOLDER}"
    )
    root.destroy()


if __name__ == "__main__":
    show_setup()