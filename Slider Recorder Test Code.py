import tkinter as tk
import time
import numpy as np

class SliderRecorder:
    def __init__(self, master):
        self.master = master
        master.title("Slider Motion Recorder")

        self.slider = tk.Scale(master, from_=-10, to=10, 
                               orient="horizontal", length=400)
        self.slider.set(0)
        self.slider.pack()

        self.start_button = tk.Button(master, text="Start Recording", command=self.start_recording)
        self.start_button.pack()

        self.stop_button = tk.Button(master, text="Stop Recording", command=self.stop_recording)
        self.stop_button.pack()

        # Data storage
        self.recording = False
        self.data = []  # list of (time, position)

    def start_recording(self):
        self.recording = True
        self.data = []
        self.start_time = time.time()
        self.record_loop()

    def stop_recording(self):
        self.recording = False
        print("\n--- Raw Data (time, position) ---")
        for t, x in self.data:
            print(f"{t:.4f} s   {x}")

        self.calculate_acceleration()

    def record_loop(self):
        if self.recording:
            t = time.time() - self.start_time
            x = self.slider.get()
            self.data.append((t, x))

            # Sample every 10 ms (100 Hz)
            self.master.after(10, self.record_loop)

    def calculate_acceleration(self):
        times = np.array([p[0] for p in self.data])
        positions = np.array([p[1] for p in self.data])

        # Compute velocity and acceleration with numerical derivative
        velocities = np.gradient(positions, times)
        accelerations = np.gradient(velocities, times)

        print("\n--- Velocity (approx) ---")
        for t, v in zip(times, velocities):
            print(f"{t:.4f} s   {v:.4f}")

        print("\n--- Acceleration (approx) ---")
        for t, a in zip(times, accelerations):
            print(f"{t:.4f} s   {a:.4f}")

        print("\nEnd position:", positions[-1])

# Run GUI
root = tk.Tk()
app = SliderRecorder(root)
root.mainloop()
