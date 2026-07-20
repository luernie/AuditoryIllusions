"""
Linear Tempo Ramp Generator (Event-Based Beeps)
Haptic-optimized version — carrier frequency set to LRA resonance peak

Changes from original:
  - beep_freq changed from 700 Hz to 210 Hz (LRA-ZA-0832 resonance peak)
  - sample_rate changed from 44100 to 48000 Hz (matches Windows HD Audio)
  - Added mild envelope shaping to reduce click artifacts at 210 Hz
  - BPM ramp 90→110 and 90→70 kept as mild ramps per original design
  - Output is uncompressed WAV (no MP3); duration 12 s per file
"""

import numpy as np
import soundfile as sf
import os

# ── Settings ───────────────────────────────────────────────────────────────────
sr         = 48000                    # Hz — matches Windows HD Audio / Syntacts
output_dir = "AudioRatingRR"  # Output folder for generated ramps
os.makedirs(output_dir, exist_ok=True)

# LRA resonance peak from characterization — use this as carrier for all beeps
LRA_RESONANCE_HZ = 210

DURATION_S = 12   # seconds per stimulus (matches illusion stimulus length)

# ── Ramp definitions ───────────────────────────────────────────────────────────
# Format: [start_BPM, end_BPM, duration_s, beep_freq_Hz, beep_duration_s]
#
# beep_freq is now LRA_RESONANCE_HZ for all — motor responds strongest here
# beep_duration kept at 0.1s (100ms) — long enough to feel, short enough
#   that at 120 BPM (0.5s between beats) there's no overlap
#
ramps = [
    [90,  90,  DURATION_S, LRA_RESONANCE_HZ, 0.1],   # Constant — control/zero ramp
    [90, 120,  DURATION_S, LRA_RESONANCE_HZ, 0.1],   # Fast acceleration (up)
    [90, 110,  DURATION_S, LRA_RESONANCE_HZ, 0.1],   # Mild acceleration (up)
    [90,  60,  DURATION_S, LRA_RESONANCE_HZ, 0.1],   # Fast deceleration (down)
    [90,  70,  DURATION_S, LRA_RESONANCE_HZ, 0.1],   # Mild deceleration (down)
]


# ── Generator ──────────────────────────────────────────────────────────────────
def generate_ramp(bpm_start, bpm_end, duration, beep_freq, beep_duration,
                  sample_rate, output_dir):

    # ── Build beep waveform ────────────────────────────────────────────────────
    beep_samples = int(beep_duration * sample_rate)
    t_beep = np.linspace(0, beep_duration, beep_samples, endpoint=False)

    # Pure sine at LRA resonance
    beep = np.sin(2 * np.pi * beep_freq * t_beep)

    # Hanning envelope — removes click artifacts at onset/offset
    # At 210 Hz this matters more than at 700 Hz because the period is longer
    beep *= np.hanning(beep_samples)

    # ── Build tempo ramp ───────────────────────────────────────────────────────
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples)

    # Linear BPM ramp across full duration
    bpm = np.linspace(bpm_start, bpm_end, n_samples)

    # Place beeps using phase accumulator
    signal = np.zeros(n_samples)
    phase  = 0.0
    for i in range(n_samples):
        phase += bpm[i] / 60.0 / sample_rate
        if phase >= 1.0:
            end = min(i + beep_samples, n_samples)
            signal[i:end] += beep[:end - i]
            phase -= 1.0

    # Normalize to peak 0.9 (leave headroom, avoid clipping through Syntacts)
    peak = np.max(np.abs(signal))
    if peak > 1e-9:
        signal *= 0.9 / peak

    # 50ms fade-out on the whole file — prevents any residual ring artifact
    # Individual beeps already have Hanning envelopes so fade-in not needed
    fade_out = int(0.050 * sample_rate)
    signal[-fade_out:] *= np.linspace(1, 0, fade_out)

    # ── Save (uncompressed WAV) ────────────────────────────────────────────────
    fname_base = f"ramp_{bpm_start}to{bpm_end}BPM_{duration}s_{beep_freq}Hz"
    wav_path   = os.path.join(output_dir, fname_base + ".wav")

    sf.write(wav_path, signal, sample_rate)

    print(f"  ✓ {wav_path}")
    return wav_path


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Generating haptic tempo ramps")
    print(f"  LRA carrier frequency: {LRA_RESONANCE_HZ} Hz")
    print(f"  Sample rate:           {sr} Hz")
    print(f"  Duration:              {DURATION_S}s per stimulus")
    print(f"  Output folder:         {output_dir}/\n")

    for ramp in ramps:
        bpm0, bpm1, dur, freq, beep_dur = ramp
        direction = "constant" if bpm0 == bpm1 else ("up" if bpm1 > bpm0 else "down")
        print(f"  {bpm0}→{bpm1} BPM ({direction})...")
        generate_ramp(bpm0, bpm1, dur, freq, beep_dur, sr, output_dir)

    print(f"\nDone — {len(ramps)} files saved to {output_dir}/")