"""
Shepard Tone Generator
Creates an auditory illusion of continuously rising (or falling) pitch

The Shepard Tone works by layering multiple sine waves an octave apart,
fading them in at the bottom and out at the top to create the illusion of endless ascent.
"""

import numpy as np
from pydub import AudioSegment
from scipy.io import wavfile
import os


class ShepardToneGenerator:
    def __init__(self,
                 output_folder="output",
                 duration_seconds=30,
                 base_frequency=55.0,  # A1
                 num_octaves=8,
                 rise_rate=1.0,
                 direction='up',
                 sample_rate=44100):
        """
        Initialize Shepard Tone Generator

        Parameters:
        -----------
        output_folder : str
            Folder to save the generated audio files
        duration_seconds : int
            Total duration of the audio in seconds
        base_frequency : float
            Starting frequency in Hz (default is A1 = 55 Hz)
        num_octaves : int
            Number of octaves to layer (typically 6-10)
        rise_rate : float
            Rate of pitch change (higher = faster change)
            1.0 is standard, 2.0 is twice as fast, 0.5 is half speed
        direction : str
            'up' for rising pitch, 'down' for falling pitch
        sample_rate : int
            Audio sample rate in Hz
        """
        self.output_folder = output_folder
        self.duration_seconds = duration_seconds
        self.base_frequency = base_frequency
        self.num_octaves = num_octaves
        self.rise_rate = rise_rate
        self.direction = direction
        self.sample_rate = sample_rate

        os.makedirs(output_folder, exist_ok=True)

    def gaussian_envelope(self, x, center, width):
        """
        Create a Gaussian envelope for smooth fading

        Parameters:
        -----------
        x : float or np.ndarray
            Current position (0 to 1)
        center : float
            Center of the Gaussian
        width : float
            Width of the Gaussian curve
        """
        return np.exp(-((x - center) ** 2) / (2 * width ** 2))

    def generate_shepard_layer(self, octave_index, num_samples):
        """Generate a single octave layer of the Shepard tone"""
        # Time array
        t = np.linspace(0, self.duration_seconds, num_samples, endpoint=False)

        # Calculate starting frequency for this octave
        octave_freq = self.base_frequency * (2 ** octave_index)

        # Calculate frequency sweep across the duration
        # Each layer sweeps one octave (scaled by rise_rate) over the full duration
        if self.direction == 'up':
            frequency = octave_freq * (2 ** (t / self.duration_seconds * self.rise_rate))
        else:  # 'down'
            frequency = octave_freq * (2 ** (-t / self.duration_seconds * self.rise_rate))

        # Integrate instantaneous frequency to get phase (avoids clicks/discontinuities)
        phase = 2 * np.pi * np.cumsum(frequency) / self.sample_rate
        wave = np.sin(phase)

        # Map current frequency position logarithmically across all octaves (wraps 0→1)
        freq_position = (np.log2(frequency / self.base_frequency) % self.num_octaves) / self.num_octaves

        # Gaussian envelope: loud in the middle of the frequency range, silent at edges
        # This creates the seamless illusion — high layers fade out as low layers fade in
        envelope = self.gaussian_envelope(freq_position, 0.5, 0.25)

        return wave * envelope

    def generate(self, filename="shepard_tone.mp3"):
        """Generate the complete Shepard Tone and save as MP3"""
        print(f"\n{'='*60}")
        print(f"Generating Shepard Tone ({self.direction})")
        print(f"{'='*60}")
        print(f"Duration:   {self.duration_seconds}s")
        print(f"Base freq:  {self.base_frequency} Hz")
        print(f"Rise rate:  {self.rise_rate}x")
        print(f"Octaves:    {self.num_octaves}")
        print()

        num_samples = int(self.duration_seconds * self.sample_rate)
        output = np.zeros(num_samples)

        # Sum all octave layers
        for octave in range(self.num_octaves):
            print(f"  Generating octave {octave + 1}/{self.num_octaves}...")
            layer = self.generate_shepard_layer(octave, num_samples)
            output += layer / self.num_octaves  # Normalize by layer count

        # Normalize to prevent clipping
        output = output / np.max(np.abs(output)) * 0.8

        # Convert to 16-bit PCM
        output_int16 = np.int16(output * 32767)

        # Save as WAV, convert to MP3 via pydub, then clean up
        temp_wav = os.path.join(self.output_folder, "temp.wav")
        wavfile.write(temp_wav, self.sample_rate, output_int16)

        audio = AudioSegment.from_wav(temp_wav)
        output_path = os.path.join(self.output_folder, filename)

        print(f"Exporting to {output_path}...")
        audio.export(output_path, format="mp3", bitrate="192k")

        os.remove(temp_wav)

        print(f"✓ Done!\n")
        return output_path


# Example usage
if __name__ == "__main__":
    print("\n" + "="*60)
    print("SHEPARD TONE GENERATOR")
    print("="*60)

    # --- Rising tones ---
    for rate in [1.0, 1.5, 2.0]:
        generator = ShepardToneGenerator(
            output_folder="shepard_output",
            duration_seconds=8,
            base_frequency=55.0,
            rise_rate=rate,
            direction='up'
        )
        generator.generate(f"shepard_rising_{rate}.mp3")

    # --- Falling tones ---
    for rate in [1.0, 1.5, 2.0]:
        generator = ShepardToneGenerator(
            output_folder="shepard_output",
            duration_seconds=8,
            base_frequency=55.0,
            rise_rate=rate,
            direction='down'      # BUG FIX: was 'up' for 1.0 and 1.5 in original
        )
        generator.generate(f"shepard_falling_{rate}.mp3")

    print("\n" + "="*60)
    print("ALL FILES GENERATED!")
    print("="*60)
    print("\nFiles created:")
    print("  • shepard_rising_1.0.mp3  — Standard rising speed")
    print("  • shepard_rising_1.5.mp3  — Faster rising")
    print("  • shepard_rising_2.0.mp3  — Fastest rising")
    print("  • shepard_falling_1.0.mp3 — Standard falling speed")
    print("  • shepard_falling_1.5.mp3 — Faster falling")
    print("  • shepard_falling_2.0.mp3 — Fastest falling")
    print()
    print("Fixes applied vs original:")
    print("  ✓ Falling tones at 1.0x and 1.5x now correctly use direction='down'")
    print("  ✓ Gaussian envelope width tightened (0.25 vs 0.3) for cleaner crossfades")
    print("  ✓ Consistent loop structure for rising and falling sets")
    print()