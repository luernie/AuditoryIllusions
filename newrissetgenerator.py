"""
Risset Eternal Accelerando/Decelerando
Faithful Python translation of Dan Stowell's SuperCollider code:
  swiki.hfbk-hamburg.de/MusicTechnology/826

Key facts from the SC source:
  - 5 streams (PlayBuf), each loops independently at its own rate
  - pos: master phasor, advances at 0.007/SR per sample, wraps 0→1
  - posses[i] = (pos + i/5) % 1.0  — evenly offset phases of the phasor
  - rate[i]   = 0.2 * 2^(posses[i] * 5)  — exponential: 0.2x to 6.4x speed
  - amp[i]    = hann(posses[i])^2         — bell curve, peaks at centre
  - Each PlayBuf loops the breakbeat at rate[i], INDEPENDENT playhead
  - output = softclip(mean(stream * amp) * 10)
  - Decelerando = run the same algorithm but phasor goes 1→0 (reversed direction)
"""

import numpy as np
import soundfile as sf
from pydub import AudioSegment
import os

# ── Settings ──────────────────────────────────────────────────────────────────
OUTPUT_DIR   = "risset_output"
DURATION_S   = 60.0
SR           = 44100
N_STREAMS    = 5
N_OCTAVES    = 5        # posses * 5 in SC
BASE_RATE    = 0.2      # 0.2 * 2^0 = 0.2x at bottom, 0.2 * 2^5 = 6.4x at top
PHASOR_STEP  = 0.007 / SR   # matches SC: Phasor.ar(1, 0.007/SampleRate.ir, 0, 1)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Synthetic breakbeat loop ───────────────────────────────────────────────────
def make_breakbeat(sr, bpm=90, bars=2):
    """
    Simple but clear breakbeat: kick, snare, hihat.
    The loop needs to be tight and transient-heavy so the Risset
    speed changes are audibly obvious.
    """
    beat   = int(sr * 60.0 / bpm)
    bar    = beat * 4
    total  = bar * bars
    buf    = np.zeros(total, dtype=np.float32)

    def place(hit, sample_pos):
        n = min(len(hit), total - sample_pos)
        if n > 0:
            buf[sample_pos:sample_pos+n] += hit[:n]

    def kick(decay=0.15):
        n = int(decay * sr)
        t = np.linspace(0, decay, n)
        freq = 120 * np.exp(-t * 30)           # pitch drop
        env  = np.exp(-t * 25)
        return (np.sin(2*np.pi * np.cumsum(freq) / sr) * env).astype(np.float32)

    def snare(decay=0.10):
        n = int(decay * sr)
        t = np.linspace(0, decay, n)
        env   = np.exp(-t * 30)
        noise = np.random.randn(n).astype(np.float32) * env
        tone  = np.sin(2*np.pi*200*t).astype(np.float32) * env * 0.4
        return noise + tone

    def hihat(decay=0.025):
        n = int(decay * sr)
        t = np.linspace(0, decay, n)
        env = np.exp(-t * 60)
        return (np.random.randn(n) * env).astype(np.float32)

    k, s, h = kick(), snare(), hihat()
    s16 = beat // 4  # one sixteenth note

    for bar_i in range(bars):
        b = bar_i * bar
        # Kick: beat 1, and beat 3 (offset slightly for groove)
        place(k, b)
        place(k, b + 8*s16)
        # Snare: beats 2 and 4
        place(s, b + 4*s16)
        place(s, b + 12*s16)
        # Hihats: every 16th note
        for step in range(16):
            place(h, b + step*s16)

    peak = np.max(np.abs(buf))
    return (buf / peak) if peak > 0 else buf


# ── Hanning^2 amplitude table (matches SC: Signal.hanningWindow.squared) ──────
def make_amp_table(n=1024):
    return np.hanning(n).astype(np.float64) ** 2


# ── Core renderer ──────────────────────────────────────────────────────────────
def render_risset(loop, sr, duration_s, phasor_step, decelerando=False):
    """
    Faithful translation of Stowell's SC code.

    SC Phasor.ar(1, 0.007/SR, 0, 1):
      - starts at 0, increments by 0.007/SR each audio sample, wraps at 1
      - for decelerando we simply negate the step so pos goes 0→-1 (same as 1→0)

    Each of the 5 PlayBuf instances:
      - has its own independent read-head (loop_pos[s])
      - advances by rate[s] samples per sample-tick
      - loops seamlessly when it hits the end of the buffer
    """
    n_out     = int(duration_s * sr)
    loop_len  = len(loop)
    amp_table = make_amp_table(1024)
    amp_len   = len(amp_table)
    out       = np.zeros(n_out, dtype=np.float64)

    offsets   = np.arange(N_STREAMS, dtype=np.float64) / N_STREAMS  # [0, 0.2, 0.4, 0.6, 0.8]

    # Independent playhead per stream (in fractional samples)
    loop_pos  = np.zeros(N_STREAMS, dtype=np.float64)

    # Master phasor
    pos       = 0.0
    step      = phasor_step if not decelerando else -phasor_step

    dot_every = n_out // 20
    print("  [", end="", flush=True)

    for i in range(n_out):
        if i % dot_every == 0:
            print("=", end="", flush=True)

        # posses: 5 evenly-spaced points on the phasor circle
        posses = (pos + offsets) % 1.0

        # Playback rates: 0.2 * 2^(posses * 5)
        rates  = BASE_RATE * np.power(2.0, posses * N_OCTAVES)

        # Amplitudes: hann^2 at each posses value
        ai     = np.clip((posses * (amp_len - 1)).astype(np.int64), 0, amp_len-1)
        amps   = amp_table[ai]

        # Read each stream with linear interpolation
        mixed  = 0.0
        for s in range(N_STREAMS):
            p    = loop_pos[s]
            i0   = int(p) % loop_len
            i1   = (i0 + 1) % loop_len
            frac = p - int(p)
            samp = loop[i0] + frac * (loop[i1] - loop[i0])
            mixed += samp * amps[s]
            loop_pos[s] = (p + rates[s]) % loop_len

        # mean * 10, then softclip (SC: .softclip ≈ tanh)
        out[i] = np.tanh((mixed / N_STREAMS) * 10.0)

        # Advance master phasor
        pos = (pos + step) % 1.0

    print("]")

    # Normalise
    peak = np.max(np.abs(out))
    if peak > 0:
        out /= peak

    return out.astype(np.float32)


# ── Save MP3 ───────────────────────────────────────────────────────────────────
def save_mp3(audio, sr, path):
    tmp = path + ".tmp.wav"
    sf.write(tmp, audio, sr)
    AudioSegment.from_wav(tmp).export(path, format="mp3", bitrate="192k")
    os.remove(tmp)
    print(f"  ✓ {path}")


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    np.random.seed(42)

    print("Building breakbeat loop...")
    loop = make_breakbeat(SR, bpm=90, bars=2)
    print(f"  {len(loop)} samples ({len(loop)/SR:.3f}s)\n")

    for label, decel in [("risset_accelerando", False), ("risset_decelerando", True)]:
        print(f"Rendering {label} ...")
        audio = render_risset(loop, SR, DURATION_S, PHASOR_STEP, decelerando=decel)
        save_mp3(audio, SR, os.path.join(OUTPUT_DIR, f"{label}.mp3"))
        print()

    print("Done →", OUTPUT_DIR)