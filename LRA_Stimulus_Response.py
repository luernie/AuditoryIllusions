# lra_stimulus_response.py
# Plays each MP3 file from a folder through the audio jack → Syntacts → LRA
# while simultaneously recording MPU-6050 accelerometer data.
# Produces a time-series plot per file showing:
#   - Top:    RMS acceleration over time (vibration intensity)
#   - Bottom: Dominant frequency over time (what frequency the motor outputs)
#
# SETUP:
#   - Same hardware as lra_characterize_v2.py
#   - Arduino Uno running lra_accel_stream.ino (MPU-6050 on A4/A5)
#   - Syntacts board via audio jack → LRA motor touching MPU-6050
#
# INSTALL (run once):
#   pip install pydub sounddevice numpy matplotlib pyserial
#   Also install ffmpeg: https://ffmpeg.org/download.html
#   Then add ffmpeg to your PATH, or set FFMPEG_PATH below
#
# USAGE:
#   1. Set STIMULI_FOLDER to your folder of MP3 files
#   2. Set AUDIO_DEVICE and SERIAL_PORT
#   3. Run: python lra_stimulus_response.py

import os
import threading
import time
import serial
import numpy as np
import sounddevice as sd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend so plots save without popping up
import matplotlib.pyplot as plt
from pydub import AudioSegment

# ── Config ─────────────────────────────────────────────────────────────────────

# Folder containing your MP3 stimulus files
STIMULI_FOLDER = r"C:\Users\Luke\Documents\Code\AuditoryIllusions\stimuli"

# Audio device index — same as lra_characterize_v2.py (device 12)
AUDIO_DEVICE = 12

# Arduino COM port
SERIAL_PORT = "COM3"

# Analysis window settings
WINDOW_MS   = 200    # ms per FFT window — 200ms gives good freq resolution
STEP_MS     = 50     # ms between windows — 50ms = ~20 time points per second

# Accelerometer
ACCEL_SCALE = 16384.0   # LSB/g at ±2g range

# Audio
AUDIO_RATE  = 48000     # Hz — Windows HD Audio default

# ffmpeg path — set this if ffmpeg is not on your system PATH
# e.g. FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_PATH = None

# ──────────────────────────────────────────────────────────────────────────────


def setup_ffmpeg():
    """Point pydub at ffmpeg if not on PATH."""
    if FFMPEG_PATH:
        AudioSegment.converter = FFMPEG_PATH
        print(f"  ffmpeg: {FFMPEG_PATH}")
    else:
        print("  ffmpeg: using system PATH")


def load_mp3(filepath):
    """Load MP3 file and return (float32 array, sample_rate)."""
    audio = AudioSegment.from_mp3(filepath)
    audio = audio.set_frame_rate(AUDIO_RATE).set_channels(1)  # mono, 48kHz
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    # Normalize to -1.0 to +1.0
    samples /= float(2 ** (audio.sample_width * 8 - 1))
    return samples, AUDIO_RATE


def measure_sample_rate(ser, duration=2.0):
    """Measure actual Arduino serial sample rate."""
    ser.reset_input_buffer()
    samples = []
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
    Thread function — records accelerometer samples for `duration` seconds.
    Stores (samples_array, timestamps_array) in result_dict.
    """
    samples    = []
    timestamps = []
    deadline   = time.time() + duration + 1.0  # small buffer
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


def play_audio(audio_array, sample_rate, device, start_event, result_dict):
    """
    Thread function — plays audio array through sounddevice.
    Fires start_event exactly when playback begins so accel thread
    can align its timestamps.
    """
    stream = sd.OutputStream(
        samplerate=sample_rate,
        channels=1,
        dtype='float32',
        device=device,
        latency='high'
    )
    stream.start()
    result_dict['play_start'] = time.time()
    start_event.set()           # signal to main thread: playback has begun
    stream.write(audio_array)
    stream.stop()
    stream.close()
    result_dict['play_end'] = time.time()


def compute_time_series(samples, timestamps, play_start, accel_rate,
                         window_ms=200, step_ms=50):
    """
    Sliding window FFT over the accelerometer recording.
    Returns (time_axis, rms_array, peak_freq_array).
    """
    window_samples = int(accel_rate * window_ms / 1000)
    step_samples   = int(accel_rate * step_ms   / 1000)

    # Align timestamps to playback start
    t_rel = timestamps - play_start  # seconds relative to audio start

    # Only keep samples from after playback started
    mask    = t_rel >= 0
    samples = samples[mask]
    t_rel   = t_rel[mask]

    if len(samples) < window_samples:
        print("  WARNING: Not enough samples for analysis")
        return np.array([]), np.array([]), np.array([])

    time_axis  = []
    rms_vals   = []
    peak_freqs = []

    i = 0
    while i + window_samples <= len(samples):
        window = samples[i : i + window_samples]
        t_mid  = t_rel[i + window_samples // 2]

        # Remove DC
        w = window - np.mean(window)

        # RMS
        rms = float(np.sqrt(np.mean(w ** 2)))

        # FFT peak frequency
        fft_mag  = np.abs(np.fft.rfft(w))
        freqs    = np.fft.rfftfreq(len(w), d=1.0 / accel_rate)
        fft_mag[0] = 0  # zero DC bin
        peak_f   = float(freqs[np.argmax(fft_mag)]) if np.max(fft_mag) > 1e-8 else 0.0

        time_axis.append(t_mid)
        rms_vals.append(rms)
        peak_freqs.append(peak_f)

        i += step_samples

    return np.array(time_axis), np.array(rms_vals), np.array(peak_freqs)


def plot_and_save(time_axis, rms_vals, peak_freqs, filename, out_path, duration):
    """Save a two-panel time-series plot for one stimulus file."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle(f"LRA Response — {filename}", fontsize=13, fontweight="bold")

    # Top: RMS amplitude over time
    ax1.plot(time_axis, rms_vals, color="royalblue", linewidth=1.5)
    ax1.fill_between(time_axis, rms_vals, alpha=0.2, color="royalblue")
    ax1.set_ylabel("RMS Acceleration (g)", fontsize=11)
    ax1.set_title("Vibration Intensity Over Time", fontsize=11)
    ax1.set_ylim(bottom=0)
    ax1.grid(True, alpha=0.3)
    ax1.axvline(0, color="gray", linestyle="--", linewidth=0.8, label="Audio start")

    # Bottom: dominant frequency over time
    ax2.plot(time_axis, peak_freqs, color="darkorange", linewidth=1.5)
    ax2.set_ylabel("Dominant Frequency (Hz)", fontsize=11)
    ax2.set_xlabel("Time (seconds)", fontsize=11)
    ax2.set_title("Motor Output Frequency Over Time", fontsize=11)
    ax2.set_ylim(0, 500)
    ax2.set_xlim(0, duration)
    ax2.axhline(200, color="red", linestyle="--", linewidth=1,
                label="LRA resonance (~200 Hz)")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved → {os.path.basename(out_path)}")


def process_file(filepath, ser, accel_rate):
    """Load, play, record, and plot one MP3 file."""
    filename = os.path.basename(filepath)
    stem     = os.path.splitext(filename)[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_response.png")

    print(f"\n── {filename} ──────────────────────────────────────")

    # Load and decode MP3
    print("  Loading MP3...")
    try:
        audio_array, sample_rate = load_mp3(filepath)
    except Exception as e:
        print(f"  ERROR loading file: {e}")
        return

    duration = len(audio_array) / sample_rate
    print(f"  Duration: {duration:.2f}s  |  Samples: {len(audio_array)}")

    # Shared result dicts for threads
    audio_result = {}
    accel_result = {}
    start_event  = threading.Event()

    # Start accelerometer recording thread first
    accel_thread = threading.Thread(
        target=record_accel,
        args=(ser, duration, accel_rate, accel_result),
        daemon=True
    )
    accel_thread.start()

    # Start audio playback thread — fires start_event when playback begins
    audio_thread = threading.Thread(
        target=play_audio,
        args=(audio_array, sample_rate, AUDIO_DEVICE, start_event, audio_result),
        daemon=True
    )
    audio_thread.start()

    # Wait for playback to actually start before doing anything else
    start_event.wait(timeout=5.0)
    play_start = audio_result.get('play_start', time.time())
    print(f"  Playback started — recording for {duration:.1f}s...")

    # Wait for both threads to finish
    audio_thread.join(timeout=duration + 5.0)
    accel_thread.join(timeout=duration + 5.0)

    print(f"  Captured {len(accel_result.get('samples', []))} accelerometer samples")

    # Compute time series
    samples    = accel_result.get('samples',    np.array([]))
    timestamps = accel_result.get('timestamps', np.array([]))

    if len(samples) < 10:
        print("  ERROR: Too few accelerometer samples — skipping plot")
        return

    time_axis, rms_vals, peak_freqs = compute_time_series(
        samples, timestamps, play_start, accel_rate,
        window_ms=WINDOW_MS, step_ms=STEP_MS
    )

    if len(time_axis) == 0:
        print("  ERROR: No valid windows computed — skipping plot")
        return

    # Save plot
    plot_and_save(time_axis, rms_vals, peak_freqs, filename, out_path, duration)

    # Brief pause between files so motor settles
    time.sleep(1.0)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    setup_ffmpeg()

    # Find MP3 files
    if not os.path.isdir(STIMULI_FOLDER):
        print(f"ERROR: Folder not found: {STIMULI_FOLDER}")
        print("Update STIMULI_FOLDER at the top of this script.")
        exit(1)

    mp3_files = sorted([
        os.path.join(STIMULI_FOLDER, f)
        for f in os.listdir(STIMULI_FOLDER)
        if f.lower().endswith(".mp3")
    ])

    if not mp3_files:
        print(f"No MP3 files found in: {STIMULI_FOLDER}")
        exit(1)

    print(f"Found {len(mp3_files)} MP3 files in {STIMULI_FOLDER}")
    for f in mp3_files:
        print(f"  {os.path.basename(f)}")

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

    # Wait for READY signal
    t0 = time.time()
    while time.time() - t0 < 10:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line == "READY":
                print("Arduino ready.")
                break

    # Measure actual sample rate
    print("\nMeasuring Arduino sample rate...")
    accel_rate = measure_sample_rate(ser, duration=2.0)

    # Process each file
    print(f"\nProcessing {len(mp3_files)} files...")
    try:
        for filepath in mp3_files:
            process_file(filepath, ser, accel_rate)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        ser.close()
        print("\nDone. Serial closed.")
        print(f"Plots saved to: {STIMULI_FOLDER}")