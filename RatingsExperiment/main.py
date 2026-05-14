"""
main.py — experiment runner
============================
Install:  pip install pygame sounddevice soundfile
Run:      python main.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_block_order, OUTPUT_FOLDER, EXPERIMENTS, get_exp_config, MODE
from test_ports import TestPortsWindow
from rating_ui import RatingWindow
from flashcard_ui import FlashcardWindow, show_break_screen

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def _prefix():
    return "DEV_" if MODE == "dev" else ""

state = {
    "participant":   None,
    "exp_key":       None,
    "exp_config":    None,
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
    root.geometry("420x280")
    root.resizable(False, False)
    root.configure(bg="#f5f5f5")

    tk.Label(root, text="Experiment Setup", bg="#f5f5f5",
             font=("Arial", 16, "bold")).pack(pady=(24, 4), padx=24, anchor="w")
    tk.Label(root, text="Select experiment and enter participant number.",
             bg="#f5f5f5", fg="#555", font=("Arial", 10)).pack(padx=24, anchor="w")

    tk.Frame(root, bg="#ddd", height=1).pack(fill=tk.X, padx=24, pady=14)

    f = tk.Frame(root, bg="#f5f5f5")
    f.pack(padx=24, fill=tk.X)

    tk.Label(f, text="Experiment:", bg="#f5f5f5",
             font=("Arial", 11)).grid(row=0, column=0, sticky="w", pady=8)
    exp_var = tk.StringVar(value="risset")
    ttk.Combobox(f, textvariable=exp_var, state="readonly", width=20,
                 values=["risset", "shepard"]).grid(row=0, column=1, sticky="w", padx=(12, 0))

    tk.Label(f, text="Participant number:", bg="#f5f5f5",
             font=("Arial", 11)).grid(row=1, column=0, sticky="w", pady=8)
    p_entry = tk.Entry(f, font=("Courier", 12), width=8, relief=tk.SOLID, bd=1)
    p_entry.grid(row=1, column=1, sticky="w", padx=(12, 0))
    p_entry.focus()

    def on_start():
        try:
            p = int(p_entry.get().strip())
            if p < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Please enter a positive integer.")
            return

        exp_key = exp_var.get()
        state["participant"]   = p
        state["exp_key"]       = exp_key
        state["exp_config"]    = get_exp_config(exp_key)
        state["block_order"]   = get_block_order(p)
        state["current_block"] = 0
        state["all_results"]   = []

        order_str = "\n".join(
            f"  {i+1}. {mod}" for i, mod in enumerate(state["block_order"])
        )
        messagebox.showinfo("Block order",
            f"Participant {p} — {state['exp_config']['label']}\n\n"
            f"Block order:\n{order_str}\n\nNext: test your audio ports.")
        root.destroy()
        run_port_test()

    tk.Button(root, text="Start →", font=("Arial", 11, "bold"),
              bg="#333", fg="white", relief=tk.FLAT, padx=18, pady=8,
              activebackground="#555", cursor="hand2",
              command=on_start).pack(pady=20)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


# ── STEP 1: Port test ─────────────────────────────────────────────────────────

def run_port_test():
    root = tk.Tk()

    def on_done(audio_id, haptic_id):
        state["audio_device"]  = audio_id
        state["haptic_device"] = haptic_id
        run_next_block()

    TestPortsWindow(root, on_done)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


# ── STEP 2–4: Ranking blocks ──────────────────────────────────────────────────

def run_next_block():
    idx        = state["current_block"]
    total      = len(state["block_order"])
    exp_config = state["exp_config"]

    if idx >= total:
        run_flashcards()
        return

    modality = state["block_order"][idx]
    root     = tk.Tk()

    def on_complete(ratings):
        state["all_results"].append({
            "block":    idx + 1,
            "stimulus": state["exp_key"],
            "modality": modality,
            "ratings":  ratings,
        })
        state["current_block"] += 1
        export_block(state["all_results"][-1])
        run_next_block()

    RatingWindow(root, exp_config, modality,
                 state["audio_device"], state["haptic_device"], on_complete)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


# ── STEP 5: Break then flashcard phase ───────────────────────────────────────

def run_flashcards():
    root = tk.Tk()
    root.title("Break")
    root.geometry("480x280")
    root.resizable(False, False)

    def on_complete(results):
        export_flashcards(results)
        finish()

    def on_break_done():
        FlashcardWindow(root, state["exp_config"],
                        state["audio_device"], state["haptic_device"],
                        on_complete)

    show_break_screen(
        root,
        "Great work — the first part is complete.\n\nTake a short break before continuing.",
        "Continue →",
        on_break_done
    )
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


# ── EXPORT: ranking block ─────────────────────────────────────────────────────

def export_block(block_result):
    p        = state["participant"]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    mod      = block_result["modality"]
    stimulus = block_result["stimulus"]

    out_path = os.path.join(OUTPUT_FOLDER,
        f"{_prefix()}p{p:03d}_block{block_result['block']:02d}_{stimulus}_{mod}_{ts}.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Block", "Stimulus", "Modality",
                         "Rank", "Filename", "Score"])
        for rank, (fname, score) in enumerate(
                sorted(block_result["ratings"], key=lambda x: x[1]), 1):
            writer.writerow([p, block_result["block"], stimulus, mod,
                             rank, fname, score])
    print(f"Saved: {out_path}")


# ── EXPORT: flashcards ────────────────────────────────────────────────────────

def export_flashcards(results):
    from collections import defaultdict
    p        = state["participant"]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    stimulus = state["exp_key"]

    trial_path = os.path.join(OUTPUT_FOLDER,
                              f"{_prefix()}p{p:03d}_{stimulus}_flashcards_{ts}.csv")
    with open(trial_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Stimulus", "Run", "Filename", "Modality", "Score"])
        for r in results:
            writer.writerow([p, stimulus, r["run"], r["filename"], r["modality"], r["score"]])

    grouped = defaultdict(dict)
    for r in results:
        grouped[(r["filename"], r["modality"])][r["run"]] = r["score"]

    avg_path = os.path.join(OUTPUT_FOLDER,
                            f"{_prefix()}p{p:03d}_{stimulus}_flashcards_averages_{ts}.csv")
    with open(avg_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Stimulus", "Filename", "Modality",
                         "Score_Run1", "Score_Run2", "Score_Run3", "Average"])
        for (fname, mod), runs in sorted(grouped.items()):
            s1 = runs.get(1, "")
            s2 = runs.get(2, "")
            s3 = runs.get(3, "")
            scores = [s for s in [s1, s2, s3] if s != ""]
            avg = round(sum(scores) / len(scores), 3) if scores else ""
            writer.writerow([p, stimulus, fname, mod, s1, s2, s3, avg])

    print(f"Saved: {trial_path}")
    print(f"Saved: {avg_path}")


# ── FINISH ────────────────────────────────────────────────────────────────────

def finish():
    p        = state["participant"]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    stimulus = state["exp_key"]

    out_path = os.path.join(OUTPUT_FOLDER,
                            f"{_prefix()}p{p:03d}_{stimulus}_ranking_summary_{ts}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Participant", "Block", "Stimulus", "Modality",
                         "Rank", "Filename", "Score"])
        for block in state["all_results"]:
            for rank, (fname, score) in enumerate(
                    sorted(block["ratings"], key=lambda x: x[1]), 1):
                writer.writerow([p, block["block"], stimulus,
                                 block["modality"], rank, fname, score])

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("All done!",
        f"Experiment complete for participant {p}.\n\nResults saved to:\n{OUTPUT_FOLDER}")
    root.destroy()
    sys.exit(0)
 
 

if __name__ == "__main__":
    show_setup()