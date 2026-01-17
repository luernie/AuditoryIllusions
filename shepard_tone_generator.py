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
        
        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
    
    def gaussian_envelope(self, x, center, width):
        """
        Create a Gaussian envelope for smooth fading
        
        Parameters:
        -----------
        x : float
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
        
        # Calculate frequency sweep based on rise_rate
        # Sweep one octave over the duration
        if self.direction == 'up':
            frequency = octave_freq * (2 ** (t / self.duration_seconds * self.rise_rate))
        else:
            frequency = octave_freq * (2 ** (-t / self.duration_seconds * self.rise_rate))
        
        # Generate sine wave with changing frequency
        phase = 2 * np.pi * np.cumsum(frequency) / self.sample_rate
        wave = np.sin(phase)
        
        # Apply Gaussian envelope (fade in at bottom, fade out at top)
        # Map frequency position to 0-1 range across all octaves
        freq_position = (np.log2(frequency / self.base_frequency) % self.num_octaves) / self.num_octaves
        
        # Create envelope that fades in and out
        envelope = self.gaussian_envelope(freq_position, 0.5, 0.3)
        
        return wave * envelope
    
    def generate(self, filename="shepard_tone.mp3"):
        """Generate the complete Shepard Tone"""
        print(f"Generating Shepard Tone ({self.direction})...")
        print(f"Duration: {self.duration_seconds}s, Base freq: {self.base_frequency} Hz")
        print(f"Rise rate: {self.rise_rate}x, Octaves: {self.num_octaves}")
        
        num_samples = int(self.duration_seconds * self.sample_rate)
        
        # Initialize output array
        output = np.zeros(num_samples)
        
        # Generate and sum all octave layers
        for octave in range(self.num_octaves):
            print(f"Generating octave {octave+1}/{self.num_octaves}...")
            layer = self.generate_shepard_layer(octave, num_samples)
            output += layer / self.num_octaves  # Normalize by number of layers
        
        # Normalize to prevent clipping
        output = output / np.max(np.abs(output)) * 0.8
        
        # Convert to 16-bit PCM
        output_int16 = np.int16(output * 32767)
        
        # Save as WAV first
        temp_wav = os.path.join(self.output_folder, "temp.wav")
        wavfile.write(temp_wav, self.sample_rate, output_int16)
        
        # Convert to MP3 using pydub
        audio = AudioSegment.from_wav(temp_wav)
        output_path = os.path.join(self.output_folder, filename)
        
        print(f"Saving to {output_path}...")
        audio.export(output_path, format="mp3", bitrate="192k")
        
        # Clean up temporary WAV file
        os.remove(temp_wav)
        
        print(f"Done! Saved to {output_path}")
        return output_path


# Example usage
if __name__ == "__main__":
    # Standard rising Shepard Tone
    generator = ShepardToneGenerator(
        output_folder="shepard_output",
        duration_seconds=30,
        base_frequency=55.0,
        rise_rate=1.0,
        direction='up'
    )
    generator.generate("shepard_rising_standard.mp3")
    
    # Fast rising version
    generator_fast = ShepardToneGenerator(
        output_folder="shepard_output",
        duration_seconds=30,
        base_frequency=55.0,
        rise_rate=2.0,  # 2x faster
        direction='up'
    )
    generator_fast.generate("shepard_rising_fast.mp3")
    
    # Falling Shepard Tone
    generator_falling = ShepardToneGenerator(
        output_folder="shepard_output",
        duration_seconds=30,
        base_frequency=55.0,
        rise_rate=1.0,
        direction='down'
    )
    generator_falling.generate("shepard_falling_standard.mp3")
    
    # Slow rising version
    generator_slow = ShepardToneGenerator(
        output_folder="shepard_output",
        duration_seconds=60,
        base_frequency=55.0,
        rise_rate=0.5,  # Half speed
        direction='up'
    )
    generator_slow.generate("shepard_rising_slow.mp3")
    
    print("\nAll files generated successfully!")
    print("Adjust the parameters in the script to customize your Shepard Tones.")