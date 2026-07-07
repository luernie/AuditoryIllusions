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

# Add as many folders as you want — script processes all MP3s in each
STIMULI_FOLDERS = [
    r"C:\Users\Luke\Documents\Code\AuditoryIllusions\AudioRatingST",
    r"C:\Users\Luke\Documents\Code\AuditoryIllusions\AudioRatingRR",
]

# Audio device index — same as lra_characterize_v2.py
AUDIO_DEVICE = 12

# Arduino COM port
SERIAL_PORT = "COM3"

# Analysis window settings
WINDOW_MS = 200   # ms per FFT window
STEP_MS   = 50    # ms between windows (~20 time points per second)

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
    """Thread: records accelerometer for duration seconds."""
    samples    = []
    timestamps = []
    deadline   = time.time() + duration + 1.0
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
    """Find MME version of preferred device — avoids WDM-KS errors on Windows."""
    devices = sd.query_devices()
    preferred_name = devices[preferred_index]['name'].split(' - ')[0].strip()
    for i, dev in enumerate(devices):
        if dev['max_output_channels'] > 0:
            if preferred_name.lower() in dev['name'].lower() and 'MME' in dev['name']:
                print(f"  Auto-selected MME device [{i}]: {dev['name']}")
                return i
    print(f"  Using device [{preferred_index}]: {devices[preferred_index]['name']}")
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


def compute_time_series(samples, timestamps, play_start, accel_rate,
                        window_ms=200, step_ms=50):
    """Sliding window FFT. Returns (time_axis, rms_array, peak_freq_array)."""
    window_samples = int(accel_rate * window_ms / 1000)
    step_samples   = int(accel_rate * step_ms   / 1000)

    t_rel   = timestamps - play_start
    mask    = t_rel >= 0
    samples = samples[mask]
    t_rel   = t_rel[mask]

    if len(samples) < window_samples:
        print("  WARNING: Not enough samples for analysis")
        return np.array([]), np.array([]), np.array([])

    time_axis, rms_vals, peak_freqs = [], [], []
    i = 0
    while i + window_samples <= len(samples):
        window = samples[i : i + window_samples]
        t_mid  = t_rel[i + window_samples // 2]
        w      = window - np.mean(window)

        rms      = float(np.sqrt(np.mean(w ** 2)))
        fft_mag  = np.abs(np.fft.rfft(w))
        freqs    = np.fft.rfftfreq(len(w), d=1.0 / accel_rate)
        fft_mag[0] = 0
        peak_f   = float(freqs[np.argmax(fft_mag)]) if np.max(fft_mag) > 1e-8 else 0.0

        time_axis.append(t_mid)
        rms_vals.append(rms)
        peak_freqs.append(peak_f)
        i += step_samples

    return np.array(time_axis), np.array(rms_vals), np.array(peak_freqs)


def plot_and_save(time_axis, rms_vals, peak_freqs, filename, out_path, duration):
    """Save two-panel time-series plot next to the source MP3."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle(f"LRA Response — {filename}", fontsize=13, fontweight="bold")

    ax1.plot(time_axis, rms_vals, color="royalblue", linewidth=1.5)
    ax1.fill_between(time_axis, rms_vals, alpha=0.2, color="royalblue")
    ax1.set_ylabel("RMS Acceleration (g)", fontsize=11)
    ax1.set_title("Vibration Intensity Over Time", fontsize=11)
    ax1.set_ylim(bottom=0)
    ax1.grid(True, alpha=0.3)

    ax2.plot(time_axis, peak_freqs, color="darkorange", linewidth=1.5)
    ax2.set_ylabel("Dominant Frequency (Hz)", fontsize=11)
    ax2.set_xlabel("Time (seconds)", fontsize=11)
    ax2.set_title("Motor Output Frequency Over Time", fontsize=11)
    ax2.set_ylim(0, 500)
    ax2.set_xlim(0, duration)
    ax2.axhline(210, color="red", linestyle="--", linewidth=1,
                label="LRA resonance (210 Hz)")
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

    time_axis, rms_vals, peak_freqs = compute_time_series(
        samples, timestamps, play_start, accel_rate,
        window_ms=WINDOW_MS, step_ms=STEP_MS
    )

    if len(time_axis) == 0:
        print("  ERROR: No valid windows — skipping")
        return {'status': 'error', 'filename': filename, 'error': 'No valid FFT windows'}

    plot_and_save(time_axis, rms_vals, peak_freqs, filename, out_path, duration)

    # Save raw time-series data as txt
    save_timeseries_txt(time_axis, rms_vals, peak_freqs, filepath,
                        duration, accel_rate, WINDOW_MS, STEP_MS)

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
                         duration, accel_rate, window_ms, step_ms):
    """
    Save raw time-series data to a tab-delimited txt file.
    Columns: time_s, rms_g, peak_freq_hz
    Header includes all metadata needed to recreate the plot.
    """
    stem     = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(os.path.dirname(filepath), f"{stem}_response.txt")

    with open(out_path, 'w', encoding='utf-8') as f:
        # Metadata header
        f.write(f"# LRA Stimulus Response — Time Series Data\n")
        f.write(f"# Source file:    {os.path.basename(filepath)}\n")
        f.write(f"# Generated:      {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Duration:       {duration:.3f} s\n")
        f.write(f"# Accel rate:     {accel_rate:.1f} Hz\n")
        f.write(f"# Window size:    {window_ms} ms\n")
        f.write(f"# Step size:      {step_ms} ms\n")
        f.write(f"# LRA resonance:  210 Hz\n")
        f.write(f"# Rows:           {len(time_axis)}\n")
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


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    setup_ffmpeg()

    # Collect MP3s from all folders
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

    # Process each folder
    try:
        for folder, mp3s in folder_groups:
            folder_name = os.path.basename(folder)
            print(f"\n{'═'*55}")
            print(f"  Folder: {folder_name}  ({len(mp3s)} files)")
            print(f"{'═'*55}")

            folder_results = []
            for filepath in mp3s:
                result = process_file(filepath, ser, accel_rate)
                if result:
                    folder_results.append(result)

            # Save summary text file for this folder
            if folder_results:
                save_folder_summary(folder, folder_results)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    finally:
        ser.close()
        print("\nDone. Serial closed.")
        print("Plots saved next to each MP3 file.")