# lra_characterize_v2.py
# Sweeps sine waves through Windows audio output → Syntacts board → LRA
# while logging MPU-6050 accelerometer data from Arduino over serial.
#
# SETUP:
#   - Arduino Uno running lra_accel_stream.ino (MPU-6050 on A4/A5)
#   - Syntacts board connected via PC audio jack → LRA motor
#   - LRA motor physically taped/pressed against MPU-6050 board
#
# STEP 1: Run with LIST_DEVICES = True to find your audio output device
# STEP 2: Set LIST_DEVICES = False, fill in AUDIO_DEVICE and SERIAL_PORT

import serial
import time
import os
import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LIST_DEVICES = False       # Set False after you find your device index

AUDIO_DEVICE = 3          # MME Headphones (HD Audio) — device 12 is WDM-KS, avoid
SERIAL_PORT  = "COM3"

FREQ_START   = 0
FREQ_END     = 600
FREQ_STEP    = 10
AMPLITUDE    = 0.8        # 0.0–1.0, don't clip at 1.0

SETTLE_TIME  = 0.5        # seconds to wait after changing frequency
CAPTURE_TIME = 0.5        # seconds of accelerometer data per step

SAMPLE_RATE  = 1000       # Hz — placeholder, auto-measured at runtime before sweep
ACCEL_SCALE  = 16384.0    # LSB/g at ±2g range
AUDIO_RATE   = 48000      # Hz — Windows HD Audio default

# ──────────────────────────────────────────────────────────────────────────────


def list_audio_devices():
    """Print all audio output devices with their API type."""
    print("\n── Available Audio Output Devices ───────────────────────")
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_output_channels'] > 0:
            marker = " ◄ DEFAULT" if i == sd.default.device[1] else ""
            print(f"  [{i:2d}]  {dev['name']}{marker}")
    print("─────────────────────────────────────────────────────────")
    print("Look for your HD Audio device with MME or WASAPI — NOT WDM-KS.")
    print("Set AUDIO_DEVICE = that index, LIST_DEVICES = False, then re-run.\n")


def find_mme_device(preferred_index):
    """
    Try to find the MME version of the preferred device.
    WDM-KS devices cause PortAudio errors on Windows — MME is most compatible.
    Returns the best device index to use.
    """
    devices = sd.query_devices()
    preferred_name = devices[preferred_index]['name']

    # Strip API suffix if present (e.g. "Speakers (HD Audio) - WDM-KS" → "Speakers (HD Audio)")
    base_name = preferred_name.split(' - ')[0].strip()

    # Look for MME version of same device
    for i, dev in enumerate(devices):
        if dev['max_output_channels'] > 0:
            if base_name.lower() in dev['name'].lower() and 'MME' in dev['name']:
                print(f"  Auto-selected MME device [{i}]: {dev['name']}")
                return i

    # Fall back to preferred index and hope for the best
    print(f"  Using device [{preferred_index}]: {preferred_name}")
    return preferred_index


def play_sine_nonblocking(freq, amplitude, device, samplerate):
    """Play a continuous sine wave non-blocking. Returns the stream."""
    # Use a callback-based stream — more reliable than write() on Windows
    duration = SETTLE_TIME + CAPTURE_TIME + 1.0  # enough buffer for full step
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    wave = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    pos = [0]  # mutable counter for callback closure

    def callback(outdata, frames, time_info, status):
        end = pos[0] + frames
        chunk = wave[pos[0]:end]
        if len(chunk) < frames:
            # Wrap around if we run out — keeps playing continuously
            chunk = np.tile(wave, 3)[pos[0]:pos[0]+frames]
        outdata[:, 0] = chunk[:frames]
        pos[0] = (pos[0] + frames) % len(wave)

    stream = sd.OutputStream(
        samplerate=samplerate,
        channels=1,
        dtype='float32',
        device=device,
        latency='high',       # 'high' = most stable on Windows
        callback=callback
    )
    stream.start()
    return stream


def stop_audio(stream):
    try:
        stream.stop()
        stream.close()
    except Exception:
        pass


def read_accel_samples(ser, n_samples, sample_rate=None):
    """Flush buffer then collect n_samples accelerometer readings.
    Returns (samples_array, actual_rate) where actual_rate is measured
    from real timestamps rather than assumed from Arduino config."""
    rate = sample_rate if sample_rate else SAMPLE_RATE
    ser.reset_input_buffer()
    samples = []
    timestamps = []
    deadline = time.time() + (n_samples / rate) * 4  # generous timeout
    while len(samples) < n_samples:
        if time.time() > deadline:
            print(f"  WARNING: Only got {len(samples)}/{n_samples} samples")
            break
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        try:
            samples.append(int(line))
            timestamps.append(time.time())
        except ValueError:
            pass

    # Compute actual sample rate from timestamps
    if len(timestamps) >= 2:
        actual_rate = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
    else:
        actual_rate = rate  # fallback

    return np.array(samples, dtype=np.float32) / ACCEL_SCALE, actual_rate


def compute_rms(signal):
    """AC RMS — DC (gravity) removed before computing."""
    s = signal - np.mean(signal)
    return float(np.sqrt(np.mean(s ** 2)))


def compute_peak_freq(signal, sample_rate=None):
    """Dominant frequency via FFT, ignoring DC."""
    rate = sample_rate if sample_rate else SAMPLE_RATE
    s = signal - np.mean(signal)
    if len(s) == 0 or np.max(np.abs(s)) < 1e-6:
        return 0.0
    fft_mag      = np.abs(np.fft.rfft(s))
    freqs        = np.fft.rfftfreq(len(s), d=1.0 / rate)
    fft_mag[0]   = 0  # zero out DC bin
    return float(freqs[np.argmax(fft_mag)])


def measure_sample_rate(ser, duration=3.0):
    """Measure actual serial sample rate by counting samples over `duration` seconds."""
    print(f"Measuring actual Arduino sample rate ({duration:.0f}s)...")
    ser.reset_input_buffer()
    samples = []
    t0 = time.time()
    while time.time() - t0 < duration:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        try:
            samples.append(int(line))
        except ValueError:
            pass
    rate = len(samples) / duration
    print(f"  Measured rate: {rate:.1f} Hz  ({len(samples)} samples in {duration:.0f}s)")
    return rate


def run_sweep(ser, audio_device, samplerate, accel_rate=None):
    freqs_to_test = np.arange(FREQ_START, FREQ_END + FREQ_STEP, FREQ_STEP)
    effective_rate = accel_rate if accel_rate else SAMPLE_RATE
    n_samples     = int(effective_rate * CAPTURE_TIME)
    est_time      = len(freqs_to_test) * (SETTLE_TIME + CAPTURE_TIME)

    commanded_hz, peak_hz, rms_g = [], [], []

    print(f"\nSweeping {FREQ_START}–{FREQ_END} Hz in {FREQ_STEP} Hz steps")
    print(f"Each step: {SETTLE_TIME}s settle + {CAPTURE_TIME}s capture")
    print(f"Total steps: {len(freqs_to_test)}  |  Est. time: ~{est_time:.0f}s\n")
    print(f"  {'Commanded':>10}  {'Peak (FFT)':>12}  {'RMS Accel':>12}")
    print(f"  {'─'*10}  {'─'*12}  {'─'*12}")

    for freq in freqs_to_test:
        freq = float(freq)

        # Start playing sine wave
        stream = play_sine_nonblocking(freq, AMPLITUDE, audio_device, samplerate)

        # Wait for motor to settle at this frequency
        time.sleep(SETTLE_TIME)

        # Capture accelerometer data — returns (samples, actual_rate_this_step)
        samples, step_rate = read_accel_samples(ser, n_samples, sample_rate=effective_rate)

        # Stop audio
        stop_audio(stream)
        time.sleep(0.1)

        # Guard against empty samples
        if len(samples) == 0:
            print(f"  {freq:>9.0f} Hz  {'NO DATA':>10}  {'NO DATA':>12}")
            commanded_hz.append(freq)
            peak_hz.append(0.0)
            rms_g.append(0.0)
            continue

        rms  = compute_rms(samples)
        # Use per-step measured rate for accurate FFT frequency axis
        peak = compute_peak_freq(samples, sample_rate=step_rate)

        commanded_hz.append(freq)
        peak_hz.append(peak)
        rms_g.append(rms)

        print(f"  {freq:>9.0f} Hz  {peak:>10.1f} Hz  {rms:>11.4f} g")

    return np.array(commanded_hz), np.array(peak_hz), np.array(rms_g)


def plot_results(commanded_hz, peak_hz, rms_g):
    resonant_freq = commanded_hz[np.argmax(rms_g)]
    print(f"\n★  Estimated LRA resonant frequency: {resonant_freq:.0f} Hz")
    print(f"   Peak RMS acceleration:             {np.max(rms_g):.4f} g")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    fig.suptitle("LRA-ZA-0832  Frequency Response Characterization", fontsize=14, fontweight="bold")

    ax1.plot(commanded_hz, rms_g, "b-o", markersize=5, linewidth=1.5)
    ax1.axvline(resonant_freq, color="red", linestyle="--", linewidth=1.5,
                label=f"Peak @ {resonant_freq:.0f} Hz")
    ax1.fill_between(commanded_hz, rms_g, alpha=0.15, color="blue")
    ax1.set_ylabel("RMS Acceleration (g)", fontsize=11)
    ax1.set_title("Mechanical Output Amplitude  (what participants actually feel)", fontsize=11)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    ax2.plot(commanded_hz, peak_hz, "g-o", markersize=5, linewidth=1.5,
             label="Actual Peak Frequency (FFT)")
    ax2.plot(commanded_hz, commanded_hz, "k--", alpha=0.4, linewidth=1,
             label="Ideal (commanded = actual)")
    ax2.axvline(resonant_freq, color="red", linestyle="--", linewidth=1.5,
                label=f"Resonance @ {resonant_freq:.0f} Hz")
    ax2.set_xlabel("Commanded Frequency (Hz)", fontsize=11)
    ax2.set_ylabel("Actual Peak Frequency (Hz)", fontsize=11)
    ax2.set_title("Does the LRA track the commanded frequency?", fontsize=11)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    # plt.savefig("lra_frequency_response.png", dpi=150, bbox_inches="tight")
    # print("Plot saved → lra_frequency_response.png")
    out_png = os.path.join(BASE_DIR, "lra_frequency_response.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {out_png}")
    plt.show()


def save_csv(commanded_hz, peak_hz, rms_g):
    out_csv = os.path.join(BASE_DIR, "lra_response_data.csv")
    np.savetxt(
        out_csv,
        np.column_stack([commanded_hz, peak_hz, rms_g]),
        delimiter=",",
        header="commanded_hz,peak_hz,rms_g",
        comments=""
    )
    print(f"Data saved → {out_csv}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    if LIST_DEVICES:
        list_audio_devices()

    else:
        # ── Connect to Arduino ─────────────────────────────────────────────
        print(f"Connecting to Arduino on {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=5)
        time.sleep(2)

        print("Waiting for Arduino to boot (5s)...")
        time.sleep(5)
        ser.reset_input_buffer()

        print("Waiting for READY signal...")
        t0 = time.time()
        got_ready = False
        while time.time() - t0 < 15:
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "READY":
                    got_ready = True
                    print("Arduino ready.\n")
                    break
        if not got_ready:
            print("No READY signal — continuing anyway.\n")

        # ── Find best audio device ─────────────────────────────────────────
        print(f"Finding best audio device for index {AUDIO_DEVICE}...")
        best_device = find_mme_device(AUDIO_DEVICE)

        # ── Confirm sample rate ────────────────────────────────────────────
        # Try 48000 first, fall back to 44100
        samplerate = AUDIO_RATE
        try:
            sd.check_output_settings(device=best_device, samplerate=48000, channels=1)
            samplerate = 48000
            print(f"Sample rate: 48000 Hz")
        except Exception:
            try:
                sd.check_output_settings(device=best_device, samplerate=44100, channels=1)
                samplerate = 44100
                print(f"Sample rate: 44100 Hz")
            except Exception as e:
                print(f"WARNING: Could not verify sample rate: {e}")

        # ── Auto-measure actual Arduino serial sample rate ─────────────────
        # Measured right before sweep so timing reflects real run conditions
        actual_sample_rate = measure_sample_rate(ser, duration=3.0)
        print(f"  Using {actual_sample_rate:.0f} Hz for FFT calculations\n")

        try:
            cmd, peak, rms = run_sweep(ser, best_device, samplerate,
                                       accel_rate=actual_sample_rate)
            plot_results(cmd, peak, rms)
            save_csv(cmd, peak, rms)

        except KeyboardInterrupt:
            print("\nSweep interrupted.")

        finally:
            ser.close()
            print("Serial closed.")