"""
Risset Eternal Accelerando/Decelerando Generator
Faithful Python translation of Dan Stowell's SuperCollider code.

Produces 4 files:
  risset_accelerando.mp3          — standard illusion, eternally speeding up
  risset_decelerando.mp3          — reversed phasor, eternally slowing down
  risset_accelerando_1p5x.mp3     — 1.5x steeper acceleration gradient
  risset_decelerando_1p5x.mp3     — 1.5x steeper deceleration gradient

What "1.5x" means:
  The Risset illusion has two separable properties:
    1. The TEMPO RANGE  — which playback rates the streams span (0.2x to 6.4x)
                          This stays the same. The perceptual centre is unchanged.
    2. The GRADIENT     — how fast the phasor sweeps through that range,
                          i.e. how many perceived tempo doublings occur per second.
  Multiplying PHASOR_STEP by 1.5 increases the gradient (steeper acceleration)
  without changing the pitch/tempo range or the perceptual anchor point.
  This is the correct parameter — analogous to sweeping a Shepard tone faster.
  Simply speeding up the audio file would destroy the illusion.
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
N_OCTAVES    = 5
BASE_RATE    = 0.2
# Matches SC: Phasor.ar(1, 0.007 / SampleRate.ir, 0, 1)
# One full cycle = 1.0 / PHASOR_STEP / SR = ~142.9 seconds
PHASOR_STEP  = 0.007 / SR

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Synthetic breakbeat ────────────────────────────────────────────────────────
def make_breakbeat(sr, bpm=90, bars=2):
    beat  = int(sr * 60.0 / bpm)
    bar   = beat * 4
    total = bar * bars
    buf   = np.zeros(total, dtype=np.float32)

    def place(hit, pos):
        n = min(len(hit), total - pos)
        if n > 0:
            buf[pos:pos+n] += hit[:n]

    def kick():
        n = int(0.18 * sr)
        t = np.linspace(0, 0.18, n)
        freq = 120 * np.exp(-t * 30)
        env  = np.exp(-t * 20)
        return (np.sin(2*np.pi * np.cumsum(freq/sr)) * env).astype(np.float32)

    def snare():
        n = int(0.12 * sr)
        t = np.linspace(0, 0.12, n)
        env = np.exp(-t * 30)
        return ((np.random.randn(n) * 0.8 + np.sin(2*np.pi*200*t) * 0.4) * env).astype(np.float32)

    def hihat():
        n = int(0.025 * sr)
        env = np.exp(-np.linspace(0, 6, n))
        return (np.random.randn(n) * env).astype(np.float32)

    k, s, h = kick(), snare(), hihat()
    s16 = beat // 4

    for b in range(bars):
        o = b * bar
        place(k, o + 0*s16);  place(k, o + 8*s16)
        place(s, o + 4*s16);  place(s, o + 12*s16)
        for step in range(16):
            place(h, o + step*s16)

    peak = np.max(np.abs(buf))
    return buf / peak if peak > 0 else buf


# ── Hanning² amplitude table ───────────────────────────────────────────────────
def make_amp_table(n=1024):
    return np.hanning(n).astype(np.float64) ** 2


# ── Core renderer ──────────────────────────────────────────────────────────────
def render_risset(loop, sr, duration_s, phasor_step, decelerando=False):
    """
    SC translation:
      pos      = Phasor.ar(1, phasor_step, 0, 1)         — master phasor
      posses   = (pos + [0, 0.2, 0.4, 0.6, 0.8]) % 1.0  — 5 stream offsets
      rates    = 0.2 * 2^(posses * 5)                    — exponential rates
      amps     = hann²(posses)                            — bell amplitude
      each stream: independent PlayBuf looping at rates[s]
      output   = softclip(mean(streams * amps) * 10)

    Decelerando: phasor runs backwards (step negated), so the stream that
    was fading in from the fast end now fades in from the slow end.
    """
    n_out     = int(duration_s * sr)
    loop_len  = len(loop)
    amp_table = make_amp_table(1024)
    amp_len   = len(amp_table)
    out       = np.zeros(n_out, dtype=np.float64)
    offsets   = np.arange(N_STREAMS, dtype=np.float64) / N_STREAMS
    loop_pos  = np.zeros(N_STREAMS, dtype=np.float64)  # independent per stream
    pos       = 0.0
    step      = -phasor_step if decelerando else phasor_step

    dot_every = n_out // 40
    print("  [", end="", flush=True)

    for i in range(n_out):
        if i % dot_every == 0:
            print("=", end="", flush=True)

        posses = (pos + offsets) % 1.0
        rates  = BASE_RATE * np.power(2.0, posses * N_OCTAVES)
        ai     = np.clip((posses * (amp_len - 1)).astype(np.int64), 0, amp_len-1)
        amps   = amp_table[ai]

        mixed = 0.0
        for s in range(N_STREAMS):
            p    = loop_pos[s]
            i0   = int(p) % loop_len
            i1   = (i0 + 1) % loop_len
            frac = p - int(p)
            mixed += (loop[i0] + frac * (loop[i1] - loop[i0])) * amps[s]
            loop_pos[s] = (p + rates[s]) % loop_len

        out[i] = np.tanh((mixed / N_STREAMS) * 10.0)
        pos = (pos + step) % 1.0

    print("]")
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

    variants = [
        # label                        phasor_step          decel   description
        ("risset_accelerando",         PHASOR_STEP,         False), # standard
        ("risset_decelerando",         PHASOR_STEP,         True),  # standard reversed
        ("risset_accelerando_1p5x",    PHASOR_STEP * 1.5,   False), # steeper gradient
        ("risset_decelerando_1p5x",    PHASOR_STEP * 1.5,   True),  # steeper reversed
    ]

    for label, step, decel in variants:
        cycle_s = 1.0 / step / SR
        print(f"Rendering {label}")
        print(f"  phasor_step={step:.8f}  cycle={cycle_s:.1f}s  decel={decel}")
        audio = render_risset(loop, SR, DURATION_S, step, decelerando=decel)
        save_mp3(audio, SR, os.path.join(OUTPUT_DIR, f"{label}.mp3"))
        print()

    print("Done →", OUTPUT_DIR)