# lra_stimulus_response.py
# Plays each MP3 file from multiple folders through audio jack → Syntacts → LRA
# while simultaneously recording MPU-6050 accelerometer data.
# Produces a time-series plot per file saved next to each MP3.
#
# SETUP:
#   - Arduino Uno running lra_accel_stream.ino (MPU-6050 on A4/A5)
#   - Syntacts board via audio jack → LRA motor touching MPU-6050
#
# INSTALL (run once):
#   pip install pydub sounddevice numpy matplotlib pyserial
#   Install ffmpeg: https://ffmpeg.org/download.html → add to PATH
#   or set FFMPEG_PATH below

import os
import threading
import time
import serial
import numpy as np
import sounddevice as sd
import matplotlib
matplotlib.use('Agg')  # non-interactive — saves plots without popping up
import matplotlib.pyplot as plt
from pydub import AudioSegment

# ── Config ─────────────────────────────────────────────────────────────────────

# ══ MODE ══════════════════════════════════════════════════════════════════════
# "collect" — Full hardware run. Plays each MP3 through the Syntacts board,
#             records the accelerometer, then saves plots + all txt files.
#             This is what you run when gathering new data.
#
# "replot"  — No hardware needed. Reads the _fft_full.txt files saved by a
#             previous "collect" run and regenerates the plots using whatever
#             SPECTROGRAM_SCALE / POWER_SPECTRUM_SCALE are currently set below.
#             Use this to switch between g and dB views (or tweak any other
#             plot setting) without re-running the LRA. Takes ~1 second.
#             Overwrites the existing PNG for each file.
#
# Typical workflow: run once in "collect", then flip to "replot" and iterate
# on the plot settings as much as you like.
MODE = "collect"   # "collect" | "replot"
# ══════════════════════════════════════════════════════════════════════════════

# Add as many folders as you want — script processes all MP3s in each
STIMULI_FOLDERS = [
    r"C:\Users\Luke\Documents\Code\AuditoryIllusions\AudioRatingST",
    r"C:\Users\Luke\Documents\Code\AuditoryIllusions\AudioRatingRR",
]

# Files that get the full 4-panel plot + peaks companion file, on top of
# automatic detection of "shepard"/"risset" in the name. Add entries here for
# any control/baseline file you also want fully characterized (e.g. steady-state
# references to compare test stimuli against). Matching is case-insensitive
# substring — you don't need the full exact filename, just enough to identify it.
#
# NOTE: _fft_full.txt is saved for EVERY file regardless of this list, so any
# recording can be re-plotted later in "replot" mode.
FULL_ANALYSIS_FILES = [
    "ramp_90to90bpm",           # Risset rhythm steady-state control
    "pitch_constant_220to220hz",  # Shepard tone steady-state control
    # Add more filenames/substrings here as needed, e.g.:
    # "another_control_file_name",
]

# Audio device index — same as lra_characterize_v2.py
AUDIO_DEVICE = 3        # MME device — device 3 confirmed working (12 is WDM-KS)

# Arduino COM port
SERIAL_PORT = "COM3"

# Analysis window settings
WINDOW_MS = 200   # ms per FFT window
STEP_MS   = 50    # ms between windows (~20 time points per second)

# ── Amplitude scale for the two frequency-domain panels ───────────────────────
# "g"    = linear amplitude in g. Shows true physical intensity delivered to
#          the finger. Directly comparable to your LRA characterization data.
#          Downside: weak components (e.g. the quieter octave partner in a
#          Shepard tone, often 15-20 dB down = ~6-10x smaller) get squashed
#          near zero and become hard to see.
#
# "db"   = decibels (20*log10). Compresses dynamic range, so strong and weak
#          components are visible simultaneously. This is what makes the
#          Shepard octave crossfade legible. Downside: not a direct physical
#          intensity number.
#
# "both" = plot both. Power spectrum gets a twin y-axis (g left, dB right).
#          Spectrogram gets a second colorbar. Note: dB and g are related
#          logarithmically, so the two scales' tick marks will NOT line up
#          evenly — this is expected, not a bug.
#
SPECTROGRAM_SCALE    = "g"    # "g" | "db" | "both"
POWER_SPECTRUM_SCALE = "g"  # "g" | "db" | "both"

# Dynamic range shown in the spectrogram when using dB (in dB below the peak).
# Lower = more contrast on the strongest components; higher = more weak
# detail visible. 40 dB is a reasonable default for these stimuli.
SPECTROGRAM_DB_RANGE = 40

# ── Input vs output overlay on the power spectrum panel ───────────────────────
# When True, the bottom-right panel plots TWO curves:
#   INPUT  = FFT of the MP3 audio itself (what was commanded)
#   OUTPUT = FFT of the accelerometer signal (what the finger actually felt)
# This directly visualizes the transfer function of the whole chain —
# which frequency components survived, and which got attenuated by the LRA.
#
# The input spectrum is computed in software from the MP3 (no hardware needed),
# using the SAME sliding-window averaging and the SAME clipped time range as
# the output, so the two are a like-for-like comparison.
SHOW_INPUT_SPECTRUM = True

# How to scale the two curves against each other:
#
# True  = NORMALIZED. Each curve is scaled so its own peak = 1.0. Answers
#         "which frequencies survived the chain?" — a SHAPE comparison.
#         This is what you want most of the time: audio amplitude
#         (dimensionless, ~-1..+1) and accelerometer output (g) are totally
#         different units, so without normalizing, one curve visually dwarfs
#         the other and the comparison is useless.
#
# False = ABSOLUTE, on a twin y-axis (input left, output in g on right).
#         Answers "how much g did a given amount of audio drive produce?" —
#         a GAIN question. Note your characterization sweep already answers
#         this more cleanly using controlled single-frequency sine tones;
#         deriving gain from a complex multi-component stimulus is messier.
#         Mostly useful as a sanity check that absolute levels are sane.
NORMALIZE_INPUT_OUTPUT = True

# ── Dominant frequency panel (bottom-left) ────────────────────────────────────
# How many frequency tracks to plot over time.
#
# 1 = Single track — the strongest peak in each window. Simple, but during a
#     Shepard octave crossfade (when two partials are nearly equal amplitude)
#     it flip-flops between them, producing sharp spikes that look like noise
#     but are actually the FFT switching allegiance between two real tones.
#
# 2 = Top TWO tracks, sorted by frequency (not by amplitude) within each
#     window. This keeps the lower partial on one line and the upper partial
#     on another, so a Shepard crossfade shows up as two smooth converging /
#     diverging bands instead of one jumpy line. Reveals the octave structure
#     directly in the time domain. Recommended for Shepard stimuli.
#
# 3+ = More tracks. Useful for Risset rhythm (broadband clicks excite several
#      bins at once), but gets cluttered fast.
N_DOMINANT_TRACKS = 2

# Minimum separation (Hz) between tracks. Peaks closer together than this are
# treated as the SAME physical tone spread across adjacent FFT bins, not as
# two separate components. Prevents both tracks from locking onto opposite
# shoulders of a single peak. ~15 Hz works well at 200ms window size.
TRACK_MIN_SEPARATION_HZ = 15.0

# Accelerometer
ACCEL_SCALE = 16384.0   # LSB/g at ±2g range

# Audio
AUDIO_RATE = 48000      # Hz — Windows HD Audio default

# ffmpeg — set path if not on system PATH
# e.g. FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_PATH = None

# ──────────────────────────────────────────────────────────────────────────────


def setup_ffmpeg():
    if FFMPEG_PATH:
        AudioSegment.converter = FFMPEG_PATH
        print(f"  ffmpeg: {FFMPEG_PATH}")
    else:
        print("  ffmpeg: using system PATH")


def load_mp3(filepath):
    """Load MP3 and return (float32 array, sample_rate)."""
    audio = AudioSegment.from_mp3(filepath)
    audio = audio.set_frame_rate(AUDIO_RATE).set_channels(1)
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    samples /= float(2 ** (audio.sample_width * 8 - 1))
    return samples, AUDIO_RATE


def measure_sample_rate(ser, duration=2.0):
    """Measure actual Arduino serial sample rate via timestamps."""
    ser.reset_input_buffer()
    samples    = []
    timestamps = []
    t0 = time.time()
    while time.time() - t0 < duration:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        try:
            samples.append(int(line))
            timestamps.append(time.time())
        except ValueError:
            pass
    if len(timestamps) >= 2:
        rate = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
    else:
        rate = 1000.0
    print(f"  Arduino sample rate: {rate:.0f} Hz ({len(samples)} samples in {duration:.0f}s)")
    return rate


def record_accel(ser, duration, accel_rate, result_dict):
    """
    Thread: records accelerometer for duration seconds.

    Starts recording immediately (before audio actually begins — see
    play_audio, which has device lookup + stream setup overhead before the
    first sample plays). The extra 1.5s buffer at the end accounts for that
    startup lag so we don't cut off real stimulus data early; the alignment
    to the true audio start time happens later in compute_time_series via
    the play_start timestamp (samples before play_start are discarded there).
    """
    samples    = []
    timestamps = []
    deadline   = time.time() + duration + 1.5
    ser.reset_input_buffer()
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        try:
            val = int(line)
            samples.append(val / ACCEL_SCALE)
            timestamps.append(time.time())
        except ValueError:
            pass
    result_dict['samples']    = np.array(samples,    dtype=np.float64)
    result_dict['timestamps'] = np.array(timestamps, dtype=np.float64)


def find_mme_device(preferred_index):
    """Return device index as-is — callback stream handles WDM-KS correctly."""
    dev_name = sd.query_devices()[preferred_index]['name']
    print(f"  Using device [{preferred_index}]: {dev_name}")
    return preferred_index


def play_audio(audio_array, sample_rate, device, start_event, result_dict):
    """Thread: plays audio via callback stream, fires start_event when playback begins."""
    # Find MME version of device to avoid WDM-KS blocking API error
    mme_device = find_mme_device(device)

    pos = [0]
    def callback(outdata, frames, time_info, status):
        end   = pos[0] + frames
        chunk = audio_array[pos[0]:end]
        if len(chunk) < frames:
            outdata[:len(chunk), 0] = chunk
            outdata[len(chunk):, 0] = 0  # pad with silence at end
        else:
            outdata[:, 0] = chunk
        pos[0] = min(pos[0] + frames, len(audio_array))

    stream = sd.OutputStream(
        samplerate=sample_rate,
        channels=1,
        dtype='float32',
        device=mme_device,
        latency='high',
        callback=callback
    )
    stream.start()
    result_dict['play_start'] = time.time()
    start_event.set()  # signal: playback has begun

    # Wait for audio to finish playing
    duration = len(audio_array) / sample_rate
    time.sleep(duration + 0.5)

    stream.stop()
    stream.close()
    result_dict['play_end'] = time.time()


def find_separated_peaks(fft_mag, freqs, n_peaks, min_sep_hz):
    """
    Find the top n_peaks in a spectrum, enforcing a minimum frequency
    separation between them.

    Greedy: take the strongest bin, then exclude everything within
    min_sep_hz of it, then take the next strongest remaining, and so on.
    Without this, two "peaks" can land on opposite shoulders of the SAME
    physical tone (adjacent bins), which is useless — we want distinct
    components, e.g. the two octave partials of a Shepard tone.

    Returns a list of (freq_hz, magnitude), sorted by FREQUENCY ascending.
    Sorting by frequency (not amplitude) is what keeps each track on a
    consistent partial across time — sorting by amplitude would make the
    tracks swap places whenever the partials cross in loudness, which is
    exactly the flip-flopping we're trying to eliminate.

    Returns fewer than n_peaks if the spectrum is too sparse; caller pads.
    """
    mag  = fft_mag.copy()
    hits = []

    for _ in range(n_peaks):
        idx = int(np.argmax(mag))
        if mag[idx] <= 1e-8:
            break                       # nothing meaningful left
        hits.append((float(freqs[idx]), float(mag[idx])))
        # Suppress this peak and its neighbourhood so the next pick is a
        # genuinely different component, not the same tone one bin over
        mask = np.abs(freqs - freqs[idx]) < min_sep_hz
        mag[mask] = 0.0

    hits.sort(key=lambda p: p[0])       # by frequency, ascending
    return hits


def compute_input_spectrum(audio_array, audio_rate, common_freqs,
                           t_start, t_end, window_ms=200, step_ms=50):
    """
    Compute the time-averaged FFT of the INPUT audio (the MP3 itself) —
    i.e. what was COMMANDED, before the LRA touched it.

    Deliberately mirrors compute_time_series() so input and output are a
    like-for-like comparison:
      - same sliding window size and step
      - same clipped time range (t_start..t_end) — so we're not comparing
        the full 8s of input against a ~6.8s clipped output
      - resampled onto the SAME common_freqs grid the output uses

    Returns a 1D array of mean magnitude, aligned to common_freqs.

    Note: audio is dimensionless (~-1..+1), accelerometer output is in g.
    They are NOT the same units — see NORMALIZE_INPUT_OUTPUT.
    """
    window_samples = int(audio_rate * window_ms / 1000)
    step_samples   = int(audio_rate * step_ms   / 1000)

    if window_samples < 2 or len(audio_array) < window_samples:
        return None

    # Audio frequency axis for one window (fixed — audio rate is exact,
    # unlike the accelerometer's jittery serial rate)
    audio_freqs = np.fft.rfftfreq(window_samples, d=1.0 / audio_rate)

    # Only analyze windows whose center falls in the same time range the
    # output analysis kept
    i_start = max(0, int(t_start * audio_rate) - window_samples // 2)
    i_end   = min(len(audio_array), int(t_end * audio_rate) + window_samples // 2)

    spectra = []
    i = i_start
    while i + window_samples <= i_end:
        w = audio_array[i : i + window_samples]
        w = w - np.mean(w)                      # remove DC, same as output
        fft_mag = np.abs(np.fft.rfft(w))
        fft_mag[0] = 0                          # zero DC bin, same as output
        spectra.append(fft_mag)
        i += step_samples

    if not spectra:
        return None

    mean_spectrum = np.mean(np.array(spectra), axis=0)

    # Resample onto the accelerometer's common frequency grid so the two
    # curves can be plotted against the same x-axis
    return np.interp(common_freqs, audio_freqs, mean_spectrum,
                     left=0.0, right=0.0)


def compute_time_series(samples, timestamps, play_start, accel_rate,
                        window_ms=200, step_ms=50,
                        clip_start=0.4, clip_end=0.8):
    """
    Sliding window FFT over accelerometer recording.
    Returns (time_axis, rms_vals, peak_freqs, peak_tracks,
             fft_matrix, common_freqs, rate_info).

    peak_tracks: (n_windows, N_DOMINANT_TRACKS) array of frequency tracks,
    sorted by frequency within each window — see find_separated_peaks().

    Calibration approach — per-window rate WITH cross-panel consistency:
      1. Each window's own sample rate is measured from its own timestamps
         (protects against rate drift within a single 8s recording, e.g. if
         CPU load isn't perfectly constant while a file plays).
      2. peak_freqs (the dominant-frequency line) uses each window's own
         rate directly — most accurate value for that instant.
      3. The magnitude spectrum for each window is then resampled (via
         linear interpolation) onto ONE common frequency grid shared by
         every window in the file. This is what feeds fft_matrix, so the
         spectrogram / power spectrum / peaks file all use the same
         frequency axis and can be validly compared/stacked across time —
         without silently assuming a single fixed rate for the whole file.

    rate_info: dict with 'overall' (rate from full clipped span, used to
    build the common grid) and 'min'/'max' (range of per-window rates
    actually observed) — for accurate reporting in file headers.

    clip_start: seconds to skip at beginning (motor spin-up)
    clip_end:   seconds to skip at end (fade-out)
    """
    t_rel = timestamps - play_start

    # Only keep samples from after playback started
    mask    = t_rel >= 0
    samples = samples[mask]
    t_rel   = t_rel[mask]

    # Overall rate — used only to size the window (sample count) and to
    # build the common frequency grid that every window gets resampled onto
    if len(t_rel) >= 2:
        overall_rate = (len(t_rel) - 1) / (t_rel[-1] - t_rel[0])
    else:
        overall_rate = accel_rate

    window_samples = int(overall_rate * window_ms / 1000)
    step_samples   = int(overall_rate * step_ms   / 1000)

    empty_rate_info = {'overall': overall_rate, 'min': overall_rate, 'max': overall_rate}

    if window_samples < 2 or len(samples) < window_samples:
        print("  WARNING: Not enough samples for analysis")
        return (np.array([]), np.array([]), np.array([]), None,
                None, None, empty_rate_info)

    # Common frequency grid — every window's spectrum gets resampled to this
    common_freqs = np.fft.rfftfreq(window_samples, d=1.0 / overall_rate)

    duration = t_rel[-1]
    t_start  = clip_start
    t_end    = duration - clip_end

    time_axis, rms_vals, peak_freqs, fft_matrix, win_rates = [], [], [], [], []
    peak_tracks = []   # shape will be (n_windows, N_DOMINANT_TRACKS)
    i = 0
    while i + window_samples <= len(samples):
        win_ts = t_rel[i : i + window_samples]
        t_mid  = win_ts[len(win_ts) // 2]

        if t_mid < t_start or t_mid > t_end:
            i += step_samples
            continue

        # This window's own actual rate, from its own timestamps
        if len(win_ts) >= 2:
            win_rate = (len(win_ts) - 1) / (win_ts[-1] - win_ts[0])
        else:
            win_rate = overall_rate

        window = samples[i : i + window_samples]
        w      = window - np.mean(window)

        rms = float(np.sqrt(np.mean(w ** 2)))

        # FFT calibrated with THIS window's own rate — most accurate
        fft_mag   = np.abs(np.fft.rfft(w))
        freqs_win = np.fft.rfftfreq(len(w), d=1.0 / win_rate)
        fft_mag_copy = fft_mag.copy()
        fft_mag_copy[0] = 0

        # Top-N frequency tracks, separated so they land on genuinely
        # different components (e.g. the two octave partials of a Shepard
        # tone) rather than adjacent bins of the same tone. Sorted by
        # frequency so each track stays on a consistent partial over time.
        hits = find_separated_peaks(fft_mag_copy, freqs_win,
                                    N_DOMINANT_TRACKS, TRACK_MIN_SEPARATION_HZ)
        track_row = [f for f, _ in hits]
        # Pad with 0.0 (plotted as NaN later) if fewer peaks than requested
        track_row += [0.0] * (N_DOMINANT_TRACKS - len(track_row))

        # peak_freq stays the single strongest component — kept for backward
        # compatibility with the txt files and folder summary stats
        peak_f = (float(freqs_win[np.argmax(fft_mag_copy)])
                  if np.max(fft_mag_copy) > 1e-8 else 0.0)

        # Resample this window's spectrum onto the common grid so every
        # row in fft_matrix shares the same frequency axis
        fft_mag_common = np.interp(common_freqs, freqs_win, fft_mag_copy,
                                   left=0.0, right=0.0)

        time_axis.append(t_mid)
        rms_vals.append(rms)
        peak_freqs.append(peak_f)
        peak_tracks.append(track_row)
        fft_matrix.append(fft_mag_common)
        win_rates.append(win_rate)

        i += step_samples

    if not time_axis:
        return (np.array([]), np.array([]), np.array([]), None,
                None, None, empty_rate_info)

    time_axis   = np.array(time_axis)
    rms_vals    = np.array(rms_vals)
    peak_freqs  = np.array(peak_freqs)
    peak_tracks = np.array(peak_tracks)
    fft_matrix  = np.array(fft_matrix)
    win_rates   = np.array(win_rates)

    print(f"  Recording rate: {overall_rate:.1f} Hz overall "
          f"(per-window range: {win_rates.min():.1f}-{win_rates.max():.1f} Hz, "
          f"{len(time_axis)} windows)")

    # Safety net: trim any trailing windows where RMS spikes or collapses
    # relative to the stable middle section (catches motor cutoff ring
    # that fixed time-based clipping alone may miss). Only trims from the
    # END — startup transients are already handled by clip_start.
    if len(rms_vals) > 10:
        mid_rms = np.median(rms_vals[len(rms_vals)//4 : 3*len(rms_vals)//4])
        stable_mask = np.ones(len(rms_vals), dtype=bool)
        for i in range(len(rms_vals) - 1, -1, -1):
            if 0.3 * mid_rms <= rms_vals[i] <= 1.8 * mid_rms:
                break
            stable_mask[i] = False
        time_axis   = time_axis[stable_mask]
        rms_vals    = rms_vals[stable_mask]
        peak_freqs  = peak_freqs[stable_mask]
        peak_tracks = peak_tracks[stable_mask]
        fft_matrix  = fft_matrix[stable_mask]
        win_rates   = win_rates[stable_mask]

    rate_info = {
        'overall': overall_rate,
        'min':     float(win_rates.min()) if len(win_rates) else overall_rate,
        'max':     float(win_rates.max()) if len(win_rates) else overall_rate,
    }

    return (time_axis, rms_vals, peak_freqs, peak_tracks,
            fft_matrix, common_freqs, rate_info)


def is_test_stimulus(filename):
    """Returns True if file is a test stimulus (shepard or risset) vs control.
    Used only for cosmetic labeling — full-analysis eligibility is decided
    by needs_full_analysis() below, which also includes FULL_ANALYSIS_FILES."""
    name = filename.lower()
    return "shepard" in name or "risset" in name


def needs_full_analysis(filename):
    """
    Returns True if this file should get the full 4-panel plot + FFT
    companion files (fft_full.txt, peaks.txt).
    True for: any shepard/risset test stimulus, OR any filename matching
    an entry in FULL_ANALYSIS_FILES (case-insensitive substring match).
    """
    if is_test_stimulus(filename):
        return True
    name = filename.lower()
    return any(entry.lower() in name for entry in FULL_ANALYSIS_FILES)


def _plot_freq_tracks(ax, time_axis, peak_freqs, peak_tracks):
    """
    Draw the dominant-frequency panel.

    If peak_tracks is available and N_DOMINANT_TRACKS > 1, plot each track as
    its own line (sorted by frequency within each window, so a track stays on
    a consistent partial over time). Otherwise fall back to the single
    strongest-peak line.

    Zeros in peak_tracks mean "no peak found in this window" — converted to
    NaN so matplotlib leaves a gap instead of drawing a line down to 0 Hz.
    """
    use_tracks = (peak_tracks is not None
                  and getattr(peak_tracks, 'ndim', 0) == 2
                  and peak_tracks.shape[1] > 1)

    if not use_tracks:
        ax.plot(time_axis, peak_freqs, color="darkorange", linewidth=1.5,
                label="Dominant frequency")
    else:
        n = peak_tracks.shape[1]
        # Warm -> cool, lower track first (it's sorted ascending by freq)
        colors = ["darkorange", "royalblue", "mediumseagreen",
                  "mediumorchid", "goldenrod"]
        for k in range(n):
            trk = peak_tracks[:, k].astype(float).copy()
            trk[trk <= 0] = np.nan          # gap, don't draw down to zero
            ax.plot(time_axis, trk,
                    color=colors[k % len(colors)],
                    linewidth=1.4, alpha=0.9,
                    label=f"Track {k+1} ({'lower' if k == 0 else 'upper' if k == n-1 else 'mid'})")

    ax.set_ylabel("Frequency (Hz)", fontsize=11)
    ax.set_ylim(0, 500)
    ax.axhline(210, color="red", linestyle="--", linewidth=1,
               label="LRA resonance (210 Hz)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")


def _add_db_twin_axis(ax):
    """
    Add a right-hand y-axis showing the same data in dB, given a left axis
    already plotted in linear g. Tick positions sit at even g values, so
    their dB labels come out unevenly spaced — expected, since the dB<->g
    relationship is logarithmic, not linear.
    """
    ax_db = ax.twinx()
    ax_db.set_ylim(ax.get_ylim())
    g_ticks = ax.get_yticks()
    g_ticks = g_ticks[g_ticks > 0]  # log10(0) is undefined — skip zero
    ax_db.set_yticks(g_ticks)
    ax_db.set_yticklabels([f"{20*np.log10(g):.0f}" for g in g_ticks])
    ax_db.set_ylabel("Mean Amplitude (dB)", fontsize=11, color="gray")
    ax_db.tick_params(axis='y', labelcolor="gray")
    return ax_db


def plot_and_save(time_axis, rms_vals, peak_freqs, peak_tracks,
                  fft_matrix, fft_freqs, filename, out_path, duration,
                  do_full, input_spectrum=None):
    """
    Save plot next to source MP3.

    Simple files: 2 panels stacked (RMS + dominant frequency, both vs time).

    Full-analysis files (shepard/risset, or listed in FULL_ANALYSIS_FILES):
    2x2 grid —
      Left column  (vs time):      RMS on top, dominant frequency below
      Right column (vs frequency): Spectrogram on top, power spectrum below
    """
    if not do_full:
        # ── Control: simple 2-panel stack ───────────────────────────────────
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        fig.suptitle(f"LRA Response — {filename}", fontsize=13, fontweight="bold")

        ax1.plot(time_axis, rms_vals, color="royalblue", linewidth=1.5)
        ax1.fill_between(time_axis, rms_vals, alpha=0.2, color="royalblue")
        ax1.set_ylabel("RMS Acceleration (g)", fontsize=11)
        ax1.set_title("Vibration Intensity Over Time", fontsize=11)
        ax1.set_ylim(bottom=0)
        ax1.grid(True, alpha=0.3)

        _plot_freq_tracks(ax2, time_axis, peak_freqs, peak_tracks)
        ax2.set_xlabel("Time (seconds)", fontsize=11)
        ax2.set_title("Motor Output Frequency Over Time", fontsize=11)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Plot saved -> {os.path.basename(out_path)}")
        return

    # ── Test stimulus: 2x2 grid ──────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 9))
    fig.suptitle(f"LRA Response — {filename}", fontsize=14, fontweight="bold")

    ax_tl = fig.add_subplot(2, 2, 1)                # top-left: RMS vs time
    ax_bl = fig.add_subplot(2, 2, 3, sharex=ax_tl)   # bottom-left: freq vs time
    ax_tr = fig.add_subplot(2, 2, 2)                # top-right: spectrogram
    ax_br = fig.add_subplot(2, 2, 4)                # bottom-right: power spectrum

    # ── Top-left: RMS over time ───────────────────────────────────────────────
    ax_tl.plot(time_axis, rms_vals, color="royalblue", linewidth=1.5)
    ax_tl.fill_between(time_axis, rms_vals, alpha=0.2, color="royalblue")
    ax_tl.set_ylabel("RMS Acceleration (g)", fontsize=11)
    ax_tl.set_title("Vibration Intensity Over Time", fontsize=11)
    ax_tl.set_ylim(bottom=0)
    ax_tl.grid(True, alpha=0.3)

    # ── Bottom-left: dominant frequency over time ─────────────────────────────
    _plot_freq_tracks(ax_bl, time_axis, peak_freqs, peak_tracks)
    ax_bl.set_xlabel("Time (seconds)", fontsize=11)
    ax_bl.set_title("Motor Output Frequency Over Time", fontsize=11)

    # ── Top-right: spectrogram ─────────────────────────────────────────────────
    if fft_matrix is not None and len(fft_matrix) > 0:
        freq_mask  = (fft_freqs >= 50) & (fft_freqs <= 500)
        fft_plot   = fft_matrix[:, freq_mask].T   # shape: (freqs, time)
        freqs_plot = fft_freqs[freq_mask]

        # Choose what the colormap encodes based on SPECTROGRAM_SCALE.
        # For "both", the image itself is dB (better dynamic range for seeing
        # structure) and a second colorbar is added showing the equivalent g
        # values at each dB level.
        if SPECTROGRAM_SCALE == "g":
            spec_data  = fft_plot
            spec_label = "Amplitude (g)"
        else:  # "db" or "both"
            spec_data  = 20 * np.log10(fft_plot + 1e-10)
            spec_data  = np.clip(spec_data,
                                 np.max(spec_data) - SPECTROGRAM_DB_RANGE,
                                 np.max(spec_data))
            spec_label = "Amplitude (dB)"

        im = ax_tr.imshow(
            spec_data,
            aspect='auto',
            origin='lower',
            extent=[time_axis[0], time_axis[-1],
                    freqs_plot[0], freqs_plot[-1]],
            cmap='inferno',
            interpolation='nearest'
        )
        ax_tr.axhline(210, color="cyan", linestyle="--", linewidth=1,
                      label="LRA resonance (210 Hz)")
        ax_tr.set_ylabel("Frequency (Hz)", fontsize=11)
        ax_tr.set_xlabel("Time (seconds)", fontsize=11)
        ax_tr.set_title("Spectrogram — Full Frequency Content Over Time", fontsize=11)
        ax_tr.legend(fontsize=9, loc="upper right")

        cbar = plt.colorbar(im, ax=ax_tr, pad=0.01)
        cbar.set_label(spec_label, fontsize=9)

        if SPECTROGRAM_SCALE == "both":
            # Second colorbar: same colors, but ticks relabeled in g.
            # Since the image is in dB, convert each dB tick back to g via
            # g = 10^(dB/20). Ticks won't be evenly spaced in g — expected,
            # because the dB<->g relationship is logarithmic.
            cbar2 = plt.colorbar(im, ax=ax_tr, pad=0.09)
            db_ticks = cbar.get_ticks()
            cbar2.set_ticks(db_ticks)
            cbar2.set_ticklabels([f"{10**(d/20):.3g}" for d in db_ticks])
            cbar2.set_label("Amplitude (g)", fontsize=9)

        # ── Bottom-right: power spectrum (OUTPUT, optionally vs INPUT) ────────
        # Own frequency mask (starts at 0 Hz, unlike spectrogram which starts
        # at 50 Hz) — DC bin is already zeroed in compute_time_series, so the
        # 0 Hz point correctly shows ~0 amplitude rather than gravity offset.
        power_mask       = (fft_freqs >= 0) & (fft_freqs <= 500)
        power_freqs_plot = fft_freqs[power_mask]

        # fft_matrix holds raw FFT magnitude of the g-unit accel signal,
        # so the time-average is already in g — no conversion needed.
        out_g = np.mean(fft_matrix[:, power_mask], axis=0)

        has_input = (SHOW_INPUT_SPECTRUM
                     and input_spectrum is not None
                     and len(input_spectrum) == len(fft_freqs))
        in_raw = input_spectrum[power_mask] if has_input else None

        C_OUT, C_IN = "mediumseagreen", "steelblue"

        if not has_input:
            # ── Single curve (output only) — original behavior ─────────────
            out_db = 20 * np.log10(out_g + 1e-10)
            if POWER_SPECTRUM_SCALE == "db":
                ax_br.plot(power_freqs_plot, out_db, color=C_OUT, linewidth=1.5)
                ax_br.fill_between(power_freqs_plot, out_db, out_db.min(),
                                   alpha=0.2, color=C_OUT)
                ax_br.set_ylabel("Mean Amplitude (dB)", fontsize=11)
            else:
                ax_br.plot(power_freqs_plot, out_g, color=C_OUT, linewidth=1.5)
                ax_br.fill_between(power_freqs_plot, out_g, 0,
                                   alpha=0.2, color=C_OUT)
                ax_br.set_ylabel("Mean Amplitude (g)", fontsize=11)
                ax_br.set_ylim(bottom=0)
                if POWER_SPECTRUM_SCALE == "both":
                    _add_db_twin_axis(ax_br)
            ax_br.set_title("Power Spectrum — Time-Averaged Frequency Content",
                            fontsize=11)

        elif NORMALIZE_INPUT_OUTPUT:
            # ── NORMALIZED: shape comparison. Each curve scaled to its own
            #    peak = 1.0. This is the meaningful comparison — audio is
            #    dimensionless, accel is in g, so absolute values are not
            #    comparable. Answers: "which frequencies survived the chain?"
            out_n = out_g  / (out_g.max()  + 1e-12)
            in_n  = in_raw / (in_raw.max() + 1e-12)

            if POWER_SPECTRUM_SCALE == "db":
                out_p = 20 * np.log10(out_n + 1e-10)
                in_p  = 20 * np.log10(in_n  + 1e-10)
                floor = max(min(out_p.min(), in_p.min()), -60)
                ax_br.set_ylim(floor, 3)
                ax_br.set_ylabel("Normalized Amplitude (dB, peak = 0 dB)",
                                 fontsize=11)
            else:
                out_p, in_p = out_n, in_n
                ax_br.set_ylim(0, 1.08)
                ax_br.set_ylabel("Normalized Amplitude (peak = 1.0)", fontsize=11)

            ax_br.plot(power_freqs_plot, in_p, color=C_IN, linewidth=1.5,
                       linestyle="--", label="INPUT (commanded — MP3)")
            ax_br.plot(power_freqs_plot, out_p, color=C_OUT, linewidth=1.8,
                       label="OUTPUT (measured — accelerometer)")
            ax_br.fill_between(power_freqs_plot, out_p,
                               ax_br.get_ylim()[0], alpha=0.15, color=C_OUT)
            ax_br.set_title("Power Spectrum — Input vs Output (normalized)",
                            fontsize=11)

        else:
            # ── ABSOLUTE: twin y-axis. Input (dimensionless) on left,
            #    output (g) on right. Answers the GAIN question: how much g
            #    did a given amount of audio drive actually produce?
            ax_in = ax_br
            ax_in.plot(power_freqs_plot, in_raw, color=C_IN, linewidth=1.5,
                       linestyle="--", label="INPUT (commanded — MP3)")
            ax_in.set_ylabel("Input Amplitude (audio units)",
                             fontsize=11, color=C_IN)
            ax_in.tick_params(axis='y', labelcolor=C_IN)
            ax_in.set_ylim(bottom=0)

            ax_out = ax_br.twinx()
            ax_out.plot(power_freqs_plot, out_g, color=C_OUT, linewidth=1.8,
                        label="OUTPUT (measured — accelerometer)")
            ax_out.fill_between(power_freqs_plot, out_g, 0,
                                alpha=0.15, color=C_OUT)
            ax_out.set_ylabel("Output Amplitude (g)", fontsize=11, color=C_OUT)
            ax_out.tick_params(axis='y', labelcolor=C_OUT)
            ax_out.set_ylim(bottom=0)

            # Merge legends from both axes into one box
            h1, l1 = ax_in.get_legend_handles_labels()
            h2, l2 = ax_out.get_legend_handles_labels()
            ax_out.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right")

            ax_br.set_title("Power Spectrum — Input vs Output (absolute)",
                            fontsize=11)

        ax_br.axvline(210, color="red", linestyle=":", linewidth=1.2,
                      label="LRA resonance (210 Hz)")
        ax_br.set_xlabel("Frequency (Hz)", fontsize=11)
        ax_br.set_xlim(0, 500)
        ax_br.grid(True, alpha=0.3)

        # In absolute mode the legend already lives on the twin axis
        if not (has_input and not NORMALIZE_INPUT_OUTPUT):
            ax_br.legend(fontsize=8, loc="upper right")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved -> {os.path.basename(out_path)}")

def process_file(filepath, ser, accel_rate):
    """Load, play, record, and plot one MP3 file."""
    filename = os.path.basename(filepath)
    stem     = os.path.splitext(filename)[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_response.png")

    print(f"\n  ── {filename}")

    try:
        audio_array, sample_rate = load_mp3(filepath)
    except Exception as e:
        print(f"  ERROR loading: {e}")
        return {'status': 'error', 'filename': filename, 'error': str(e)}

    duration = len(audio_array) / sample_rate
    print(f"  Duration: {duration:.2f}s")

    audio_result = {}
    accel_result = {}
    start_event  = threading.Event()

    accel_thread = threading.Thread(
        target=record_accel,
        args=(ser, duration, accel_rate, accel_result),
        daemon=True
    )
    audio_thread = threading.Thread(
        target=play_audio,
        args=(audio_array, sample_rate, AUDIO_DEVICE, start_event, audio_result),
        daemon=True
    )

    accel_thread.start()
    audio_thread.start()

    start_event.wait(timeout=5.0)
    play_start = audio_result.get('play_start', time.time())
    print(f"  Playing — recording for {duration:.1f}s...")

    audio_thread.join(timeout=duration + 5.0)
    accel_thread.join(timeout=duration + 5.0)

    samples    = accel_result.get('samples',    np.array([]))
    timestamps = accel_result.get('timestamps', np.array([]))

    print(f"  Captured {len(samples)} accelerometer samples")

    if len(samples) < 10:
        print("  ERROR: Too few samples — skipping")
        return {'status': 'error', 'filename': filename, 'error': 'Too few accelerometer samples'}

    (time_axis, rms_vals, peak_freqs, peak_tracks,
     fft_matrix, fft_freqs, rate_info) = compute_time_series(
        samples, timestamps, play_start, accel_rate,
        window_ms=WINDOW_MS, step_ms=STEP_MS
    )

    if len(time_axis) == 0:
        print("  ERROR: No valid windows — skipping")
        return {'status': 'error', 'filename': filename, 'error': 'No valid FFT windows'}

    do_full = needs_full_analysis(filename)

    # Compute the INPUT spectrum from the MP3 itself (no hardware involved).
    # Matched to the output's time range so the comparison is like-for-like.
    input_spectrum = None
    if SHOW_INPUT_SPECTRUM and fft_freqs is not None and len(time_axis) > 0:
        input_spectrum = compute_input_spectrum(
            audio_array, sample_rate, fft_freqs,
            t_start=time_axis[0], t_end=time_axis[-1],
            window_ms=WINDOW_MS, step_ms=STEP_MS
        )
        if input_spectrum is None:
            print("  WARNING: could not compute input spectrum from audio")

    plot_and_save(time_axis, rms_vals, peak_freqs, peak_tracks,
                  fft_matrix, fft_freqs, filename, out_path, duration,
                  do_full, input_spectrum)

    # Save raw time-series data as txt — report the real measured rate range
    save_timeseries_txt(time_axis, rms_vals, peak_freqs, filepath,
                        duration, rate_info, WINDOW_MS, STEP_MS,
                        clip_start=0.4, clip_end=0.8)

    # Replot source file — saved for EVERY file so any recording can be
    # re-plotted later in "replot" mode without touching the hardware
    if fft_matrix is not None and len(fft_matrix) > 0:
        save_fft_full(fft_matrix, fft_freqs, time_axis, rms_vals, peak_freqs,
                      peak_tracks, filepath, rate_info, duration,
                      input_spectrum)

        # Peaks summary only for full-analysis files (shepard/risset +
        # anything in FULL_ANALYSIS_FILES) — it's an interpretation aid,
        # not needed for the simple 2-panel control plots
        if do_full:
            save_fft_peaks(fft_matrix, fft_freqs, time_axis, filepath,
                           rate_info, n_peaks=5)

    time.sleep(1.0)  # let motor settle between files

    # Compute summary metrics for this file
    peak_rms_idx = int(np.argmax(rms_vals))
    valid_freqs  = peak_freqs[peak_freqs > 10]  # exclude near-DC noise

    return {
        'status':        'ok',
        'filename':      filename,
        'duration':      duration,
        'peak_rms':      float(np.max(rms_vals)),
        'peak_rms_time': float(time_axis[peak_rms_idx]),
        'avg_freq':      float(np.mean(valid_freqs))   if len(valid_freqs) > 0 else 0.0,
        'min_freq':      float(np.min(valid_freqs))    if len(valid_freqs) > 0 else 0.0,
        'max_freq':      float(np.max(valid_freqs))    if len(valid_freqs) > 0 else 0.0,
    }


def save_timeseries_txt(time_axis, rms_vals, peak_freqs, filepath,
                         duration, rate_info, window_ms, step_ms,
                         clip_start=0.4, clip_end=0.8):
    """
    Save raw time-series data to a tab-delimited txt file.
    Columns: time_s, rms_g, peak_freq_hz
    Header includes all metadata needed to recreate the plot.

    rate_info: dict with 'overall'/'min'/'max' accelerometer sample rate
    (Hz) for this recording. peak_freq_hz values use EACH WINDOW'S OWN
    rate (most accurate per-instant), so min/max shows the real range —
    this is not a single approximation but the true measured spread.
    """
    stem     = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_response.txt")

    overall_rate    = rate_info['overall']
    window_samples  = int(overall_rate * window_ms / 1000)
    freq_resolution = overall_rate / window_samples if window_samples > 0 else 0.0
    rate_spread     = rate_info['max'] - rate_info['min']

    with open(out_path, 'w', encoding='utf-8') as f:
        # Metadata header
        f.write(f"# LRA Stimulus Response — Time Series Data\n")
        f.write(f"# Source file:      {os.path.basename(filepath)}\n")
        f.write(f"# Generated:        {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Stimulus duration:{duration:.3f} s\n")
        f.write(f"# Analysis window:  {time_axis[0]:.3f}s to {time_axis[-1]:.3f}s "
                f"(clipped {clip_start:.1f}s at start, {clip_end:.1f}s+ at end,\n")
        f.write(f"#                    plus automatic trim of any trailing cutoff-ring artifact)\n")
        f.write(f"# Accel sample rate: {rate_info['min']:.1f}-{rate_info['max']:.1f} Hz "
                f"(range across windows; {overall_rate:.1f} Hz overall for this recording)\n")
        f.write(f"#                    peak_freq_hz below uses EACH WINDOW'S OWN rate "
                f"(spread: {rate_spread:.1f} Hz) for maximum accuracy per instant\n")
        f.write(f"# FFT window size:  {window_ms} ms ({window_samples} samples)\n")
        f.write(f"# FFT step size:    {step_ms} ms\n")
        f.write(f"# FFT freq resolution: ~{freq_resolution:.2f} Hz per bin (at overall rate)\n")
        f.write(f"# LRA resonance:    210 Hz (free-air, characterized separately)\n")
        f.write(f"# Rows:             {len(time_axis)}\n")
        f.write(f"#\n")
        f.write(f"# To recreate plot in Python:\n")
        f.write(f"#   import numpy as np, matplotlib.pyplot as plt\n")
        f.write(f"#   data = np.loadtxt('filename.txt', delimiter='\t', comments='#')\n")
        f.write(f"#   t, rms, freq = data[:,0], data[:,1], data[:,2]\n")
        f.write(f"#   fig, (ax1, ax2) = plt.subplots(2,1, sharex=True)\n")
        f.write(f"#   ax1.plot(t, rms);  ax1.set_ylabel('RMS Acceleration (g)')\n")
        f.write(f"#   ax2.plot(t, freq); ax2.set_ylabel('Dominant Frequency (Hz)')\n")
        f.write(f"#   plt.show()\n")
        f.write(f"#\n")
        f.write(f"# Columns:\n")
        f.write(f"# time_s\trms_g\tpeak_freq_hz\n")

        # Data rows — tab delimited
        for t, r, fq in zip(time_axis, rms_vals, peak_freqs):
            f.write(f"{t:.4f}\t{r:.6f}\t{fq:.2f}\n")

    print(f"  Data saved  → {os.path.basename(out_path)}")
    return out_path


def save_fft_full(fft_matrix, fft_freqs, time_axis, rms_vals, peak_freqs,
                  peak_tracks, filepath, rate_info, duration,
                  input_spectrum=None):
    """
    Save the complete analysis result to a companion file — everything needed
    to fully regenerate all four plots later WITHOUT re-running the hardware.

    Written for EVERY file (not just full-analysis ones), so any recording can
    be re-plotted in "replot" mode.

    Format: one row per time window.
      col 0     = time_s
      col 1     = rms_g
      col 2     = peak_freq_hz  (computed with that window's own sample rate)
      col 3..N  = FFT magnitude bins, resampled onto the common frequency grid

    Frequency bins span the FULL range (0 Hz up) — not clipped — because the
    power spectrum panel starts at 0 Hz. Panel-specific clipping happens at
    plot time, not here.
    """
    stem     = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_fft_full.txt")

    # Keep the full frequency range up to 500 Hz (0 Hz included — the power
    # spectrum needs it; DC bin is already zeroed in compute_time_series)
    freq_mask  = fft_freqs <= 500
    freqs_clip = fft_freqs[freq_mask]
    fft_clip   = fft_matrix[:, freq_mask]

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# LRA Full Analysis Data — Replot Source File\n")
        f.write(f"# Source file: {os.path.basename(filepath)}\n")
        f.write(f"# Generated:   {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Accel sample rate: {rate_info['min']:.1f}-{rate_info['max']:.1f} Hz "
                f"per-window range ({rate_info['overall']:.1f} Hz overall)\n")
        f.write(f"#                    Each window measured with its own real rate, then\n")
        f.write(f"#                    resampled onto the common freq_bins grid below\n")
        f.write(f"# Rows:        {len(time_axis)} (one per time window)\n")
        f.write(f"# Freq bins:   {len(freqs_clip)} bins, "
                f"{freqs_clip[0]:.1f} to {freqs_clip[-1]:.1f} Hz\n")
        f.write(f"#\n")
        f.write(f"# MACHINE-READABLE METADATA (used by replot mode — do not edit):\n")
        f.write(f"#@duration={duration:.6f}\n")
        f.write(f"#@rate_overall={rate_info['overall']:.6f}\n")
        f.write(f"#@rate_min={rate_info['min']:.6f}\n")
        f.write(f"#@rate_max={rate_info['max']:.6f}\n")
        f.write(f"#@freq_bins={','.join(f'{fq:.4f}' for fq in freqs_clip)}\n")
        n_tracks = peak_tracks.shape[1] if peak_tracks is not None and peak_tracks.ndim == 2 else 0
        f.write(f"#@n_tracks={n_tracks}\n")
        if input_spectrum is not None:
            # Time-averaged FFT of the source MP3 (what was COMMANDED), on the
            # same freq grid. Lets replot mode redraw the input-vs-output
            # comparison without re-decoding the audio.
            inp_clip = input_spectrum[freq_mask]
            f.write(f"#@input_spectrum={','.join(f'{v:.6e}' for v in inp_clip)}\n")
        f.write(f"#\n")
        f.write(f"# Columns: time_s  rms_g  peak_freq_hz  "
                f"{n_tracks} track_hz cols  then "
                f"{len(freqs_clip)} FFT magnitude bins (in g)\n")
        f.write(f"#\n")

        for i, (t, rms, pk, row) in enumerate(zip(time_axis, rms_vals,
                                                  peak_freqs, fft_clip)):
            trk_str = ""
            if n_tracks:
                trk_str = " ".join(f"{v:.4f}" for v in peak_tracks[i]) + " "
            row_str = " ".join(f"{v:.6f}" for v in row)
            f.write(f"{t:.6f} {rms:.6f} {pk:.4f} {trk_str}{row_str}\n")

    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Replot data saved -> {os.path.basename(out_path)}  "
          f"({len(time_axis)} rows x {len(freqs_clip)} bins, {size_kb:.0f} KB)")
    return out_path


def load_fft_full(fft_full_path):
    """
    Read a _fft_full.txt file written by save_fft_full().
    Returns (time_axis, rms_vals, peak_freqs, peak_tracks, fft_matrix,
             fft_freqs, rate_info, duration, input_spectrum).

    input_spectrum is None if the file was collected with SHOW_INPUT_SPECTRUM
    off, or was written by an older version of this script.
    """
    meta = {}
    with open(fft_full_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('#'):
                break
            if line.startswith('#@'):
                key, _, val = line[2:].strip().partition('=')
                meta[key] = val

    required = {'duration', 'rate_overall', 'rate_min', 'rate_max', 'freq_bins'}
    missing  = required - set(meta)
    if missing:
        raise ValueError(
            f"{os.path.basename(fft_full_path)} is missing metadata {sorted(missing)}. "
            f"It was likely written by an older version of this script — "
            f"re-run in 'collect' mode to regenerate it."
        )

    fft_freqs = np.array([float(x) for x in meta['freq_bins'].split(',')])
    duration  = float(meta['duration'])
    rate_info = {
        'overall': float(meta['rate_overall']),
        'min':     float(meta['rate_min']),
        'max':     float(meta['rate_max']),
    }

    data = np.loadtxt(fft_full_path, comments='#')
    if data.ndim == 1:
        data = data.reshape(1, -1)

    n_tracks = int(meta.get('n_tracks', 0))

    time_axis  = data[:, 0]
    rms_vals   = data[:, 1]
    peak_freqs = data[:, 2]
    if n_tracks:
        peak_tracks = data[:, 3 : 3 + n_tracks]
        fft_matrix  = data[:, 3 + n_tracks :]
    else:
        peak_tracks = None
        fft_matrix  = data[:, 3:]

    if fft_matrix.shape[1] != len(fft_freqs):
        raise ValueError(
            f"{os.path.basename(fft_full_path)}: {fft_matrix.shape[1]} FFT columns "
            f"but {len(fft_freqs)} freq bins in header — file may be corrupt."
        )

    # Optional — only present if SHOW_INPUT_SPECTRUM was on during collect
    input_spectrum = None
    if 'input_spectrum' in meta:
        input_spectrum = np.array([float(x) for x in meta['input_spectrum'].split(',')])
        if len(input_spectrum) != len(fft_freqs):
            print(f"  WARNING: input_spectrum length mismatch in "
                  f"{os.path.basename(fft_full_path)} — ignoring it")
            input_spectrum = None

    return (time_axis, rms_vals, peak_freqs, peak_tracks, fft_matrix,
            fft_freqs, rate_info, duration, input_spectrum)

def save_fft_peaks(fft_matrix, fft_freqs, time_axis, filepath, rate_info, n_peaks=5):
    """
    Save condensed top-N frequency peaks per time window.
    Small, pasteable file — captures multi-component structure
    (e.g. octave components in a Shepard tone) without full bin data.
    """
    stem     = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_peaks.txt")

    freq_mask  = (fft_freqs >= 50) & (fft_freqs <= 500)
    freqs_clip = fft_freqs[freq_mask]
    fft_clip   = fft_matrix[:, freq_mask]
    freq_res   = fft_freqs[1] - fft_freqs[0] if len(fft_freqs) > 1 else 0.0

    header_cols = ["time_s"]
    for i in range(1, n_peaks + 1):
        header_cols += [f"peak{i}_hz", f"peak{i}_g", f"peak{i}_db"]

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# LRA Top-{n_peaks} Frequency Peaks — Condensed Summary\n")
        f.write(f"# Source file: {os.path.basename(filepath)}\n")
        f.write(f"# Generated:   {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Accel sample rate: {rate_info['min']:.1f}-{rate_info['max']:.1f} Hz "
                f"per-window range ({rate_info['overall']:.1f} Hz overall)\n")
        f.write(f"# Freq resolution:   {freq_res:.2f} Hz per bin "
                f"(peaks below are quantized to this common grid;\n")
        f.write(f"#                    each window measured at its own real rate, then\n")
        f.write(f"#                    resampled here for cross-window comparability)\n")
        f.write(f"# Rows:        {len(time_axis)}\n")
        f.write(f"#\n")
        f.write(f"# For each time window, the top {n_peaks} frequency peaks by magnitude,\n")
        f.write(f"# sorted strongest first. Each peak is reported in BOTH units:\n")
        f.write(f"#   peakN_g  = linear amplitude in g (true physical intensity)\n")
        f.write(f"#   peakN_db = 20*log10(g) (compressed range — easier to compare\n")
        f.write(f"#              strong vs weak components, e.g. Shepard octave partners)\n")
        f.write(f"#\n")
        f.write(f"# NOTE: adjacent bins around one physical tone can both appear as\n")
        f.write(f"# separate 'peaks' — treat peaks within 1-2 bins of each other as\n")
        f.write(f"# the same component.\n")
        f.write(f"#\n")
        f.write("\t".join(header_cols) + "\n")

        for t, row in zip(time_axis, fft_clip):
            row_db  = 20 * np.log10(row + 1e-10)
            top_idx = np.argsort(row)[::-1][:n_peaks]        # top N by magnitude (g)
            top_idx = top_idx[np.argsort(row[top_idx])[::-1]]  # ensure descending

            vals = [f"{t:.4f}"]
            for idx in top_idx:
                vals.append(f"{freqs_clip[idx]:.1f}")     # Hz
                vals.append(f"{row[idx]:.5f}")            # g
                vals.append(f"{row_db[idx]:.1f}")         # dB
            while len(vals) < 1 + 3 * n_peaks:
                vals += ["", "", ""]
            f.write("\t".join(vals) + "\n")

    print(f"  Peaks summary saved -> {os.path.basename(out_path)}")
    return out_path


def save_folder_summary(folder, results):
    """Save a one-line-per-file summary for the whole folder."""
    folder_name = os.path.basename(folder)
    out_path    = os.path.join(folder, f"{folder_name}_summary.txt")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# LRA Folder Summary\n")
        f.write(f"# Folder:    {folder}\n")
        f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Files:     {len(results)}\n")
        f.write(f"#\n")
        f.write(f"# filename\tduration_s\tpeak_rms_g\tpeak_rms_time_s\t"
                f"avg_freq_hz\tmin_freq_hz\tmax_freq_hz\n")

        good = [r for r in results if r['status'] == 'ok']
        for r in results:
            if r['status'] == 'error':
                f.write(f"# ERROR: {r['filename']} — {r['error']}\n")
                continue
            f.write(
                f"{r['filename']}\t"
                f"{r['duration']:.3f}\t"
                f"{r['peak_rms']:.6f}\t"
                f"{r['peak_rms_time']:.3f}\t"
                f"{r['avg_freq']:.2f}\t"
                f"{r['min_freq']:.2f}\t"
                f"{r['max_freq']:.2f}\n"
            )

    print(f"  Folder summary → {os.path.basename(out_path)}")
    return out_path


def collect_mp3s(folders):
    """Collect all MP3 files from a list of folders."""
    all_files = []
    for folder in folders:
        if not os.path.isdir(folder):
            print(f"WARNING: Folder not found, skipping: {folder}")
            continue
        mp3s = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".mp3")
        ])
        if mp3s:
            all_files.append((folder, mp3s))
        else:
            print(f"WARNING: No MP3s found in: {folder}")
    return all_files


def replot_file(filepath):
    """
    Regenerate the plot for one file from its saved _fft_full.txt, using the
    CURRENT plot settings (SPECTROGRAM_SCALE, POWER_SPECTRUM_SCALE, etc).
    Touches no hardware. Overwrites the existing PNG.
    """
    filename      = os.path.basename(filepath)
    stem          = os.path.splitext(filename)[0]
    folder        = os.path.dirname(filepath)
    fft_full_path = os.path.join(folder, f"{stem}_fft_full.txt")
    out_path      = os.path.join(folder, f"{stem}_response.png")

    if not os.path.exists(fft_full_path):
        print(f"  SKIP {filename} — no {stem}_fft_full.txt "
              f"(run in 'collect' mode first)")
        return None

    try:
        (time_axis, rms_vals, peak_freqs, peak_tracks, fft_matrix,
         fft_freqs, rate_info, duration, input_spectrum) = load_fft_full(fft_full_path)
    except Exception as e:
        print(f"  ERROR reading {stem}_fft_full.txt: {e}")
        return {'status': 'error', 'filename': filename, 'error': str(e)}

    do_full = needs_full_analysis(filename)

    if SHOW_INPUT_SPECTRUM and input_spectrum is None:
        print(f"  NOTE: {stem}_fft_full.txt has no saved input spectrum "
              f"(collected before SHOW_INPUT_SPECTRUM was enabled).")
        print(f"        Re-run in 'collect' mode to add it.")

    print(f"\n  ── {filename}  ({len(time_axis)} windows)")
    plot_and_save(time_axis, rms_vals, peak_freqs, peak_tracks,
                  fft_matrix, fft_freqs, filename, out_path, duration,
                  do_full, input_spectrum)

    # Regenerate the peaks file too — it carries both g and dB columns, so
    # it stays valid regardless of plot scale, but this keeps it in sync if
    # n_peaks or the freq range ever changes.
    if do_full:
        save_fft_peaks(fft_matrix, fft_freqs, time_axis, filepath,
                       rate_info, n_peaks=5)

    peak_rms_idx = int(np.argmax(rms_vals))
    valid_freqs  = peak_freqs[peak_freqs > 10]
    return {
        'status':        'ok',
        'filename':      filename,
        'duration':      duration,
        'peak_rms':      float(np.max(rms_vals)),
        'peak_rms_time': float(time_axis[peak_rms_idx]),
        'avg_freq':      float(np.mean(valid_freqs)) if len(valid_freqs) else 0.0,
        'min_freq':      float(np.min(valid_freqs))  if len(valid_freqs) else 0.0,
        'max_freq':      float(np.max(valid_freqs))  if len(valid_freqs) else 0.0,
    }


def run_replot_mode(folder_groups):
    """Regenerate all plots from saved data. No hardware needed."""
    print(f"\n{'='*60}")
    print(f"  MODE: replot  (no hardware — reading saved _fft_full.txt files)")
    print(f"{'='*60}")
    print(f"  Spectrogram scale:    {SPECTROGRAM_SCALE}")
    print(f"  Power spectrum scale: {POWER_SPECTRUM_SCALE}")
    if SPECTROGRAM_SCALE in ("db", "both"):
        print(f"  Spectrogram dB range: {SPECTROGRAM_DB_RANGE} dB below peak")

    n_ok = n_skip = 0
    for folder, mp3s in folder_groups:
        print(f"\n{'─'*55}")
        print(f"  Folder: {os.path.basename(folder)}  ({len(mp3s)} files)")
        print(f"{'─'*55}")

        folder_results = []
        for filepath in mp3s:
            result = replot_file(filepath)
            if result is None:
                n_skip += 1
            else:
                folder_results.append(result)
                if result['status'] == 'ok':
                    n_ok += 1

        if folder_results:
            save_folder_summary(folder, folder_results)

    print(f"\n{'='*60}")
    print(f"  Replotted {n_ok} file(s)." + (f"  Skipped {n_skip} (no saved data)." if n_skip else ""))
    if n_skip:
        print(f"  To generate data for skipped files, set MODE = \"collect\" and re-run.")
    print(f"{'='*60}")


def run_collect_mode(folder_groups):
    """Full hardware run — play stimuli, record accelerometer, save everything."""
    print(f"\n{'='*60}")
    print(f"  MODE: collect  (hardware run — LRA + accelerometer)")
    print(f"{'='*60}")

    setup_ffmpeg()

    # Connect to Arduino
    print(f"\nConnecting to Arduino on {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=3)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {SERIAL_PORT}: {e}")
        exit(1)

    print("Waiting for Arduino to boot (5s)...")
    time.sleep(5)
    ser.reset_input_buffer()

    t0 = time.time()
    while time.time() - t0 < 10:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line == "READY":
                print("Arduino ready.")
                break

    print("\nMeasuring Arduino sample rate...")
    accel_rate = measure_sample_rate(ser, duration=2.0)

    if accel_rate <= 0 or accel_rate == 1000.0:
        # 1000.0 is the hardcoded fallback used when zero timestamps came in —
        # i.e. the Arduino sent nothing at all during the measurement window.
        print("\n" + "!"*60)
        print("!  WARNING: No accelerometer data received from Arduino.")
        print("!  Before running through all files, check:")
        print("!    - Arduino IDE Serial Monitor is fully CLOSED")
        print("!    - MPU-6050 wiring (SDA->A4, SCL->A5, VCC->3.3V, GND->GND)")
        print("!    - Correct COM port (currently: " + SERIAL_PORT + ")")
        print("!    - lra_accel_stream.ino sketch is actually flashed and running")
        print("!"*60)
        response = input("\nContinue anyway? Every file will likely fail. [y/N]: ")
        if response.strip().lower() != 'y':
            ser.close()
            print("Aborted.")
            exit(1)

    try:
        for folder, mp3s in folder_groups:
            print(f"\n{'═'*55}")
            print(f"  Folder: {os.path.basename(folder)}  ({len(mp3s)} files)")
            print(f"{'═'*55}")

            folder_results = []
            for filepath in mp3s:
                result = process_file(filepath, ser, accel_rate)
                if result:
                    folder_results.append(result)

            if folder_results:
                save_folder_summary(folder, folder_results)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    finally:
        ser.close()
        print("\nDone. Serial closed.")
        print("Plots + data saved next to each MP3 file.")
        print("\nTIP: set MODE = \"replot\" to regenerate plots with different")
        print("     scale settings (g / dB) without re-running the hardware.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    if MODE not in ("collect", "replot"):
        print(f"ERROR: MODE must be \"collect\" or \"replot\", got: {MODE!r}")
        exit(1)

    folder_groups = collect_mp3s(STIMULI_FOLDERS)

    if not folder_groups:
        print("No MP3 files found in any of the specified folders.")
        exit(1)

    total = sum(len(mp3s) for _, mp3s in folder_groups)
    print(f"\nFound {total} MP3 files across {len(folder_groups)} folders:")
    for folder, mp3s in folder_groups:
        print(f"\n  {folder}  ({len(mp3s)} files)")
        for f in mp3s:
            print(f"    {os.path.basename(f)}")

    if MODE == "replot":
        run_replot_mode(folder_groups)
    else:
        run_collect_mode(folder_groups)