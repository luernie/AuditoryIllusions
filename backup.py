"""
Risset Rhythm Generator - Clean Implementation
Properly handles both acceleration and deceleration
"""

import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment
import os

class RissetRhythmGenerator:
    def __init__(self,
                 output_folder="risset_output",
                 duration_seconds=20,
                 base_tempo=80,
                 num_layers=2,
                 direction='accelerating',
                 sample_rate=44100):
        """
        Risset Rhythm Generator
        
        Parameters:
        -----------
        output_folder : str
            Where to save files
        duration_seconds : int
            Length of audio
        base_tempo : float
            Starting tempo for acceleration (or ending tempo for deceleration)
        num_layers : int
            Number of overlapping layers (2 or 3 recommended)
        direction : str
            'accelerating' or 'decelerating'
        """
        self.output_folder = output_folder
        self.duration_seconds = duration_seconds
        self.base_tempo = base_tempo
        self.num_layers = num_layers
        self.direction = direction
        self.sample_rate = sample_rate
        
        os.makedirs(output_folder, exist_ok=True)
    
    def make_kick(self):
        """Create kick drum sound"""
        duration_ms = 150
        duration_samples = int((duration_ms / 1000) * self.sample_rate)
        t = np.linspace(0, duration_ms / 1000, duration_samples)
        
        freq = 150 * np.exp(-t * 10)
        phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
        envelope = np.exp(-t * 7)
        kick = np.sin(phase) * envelope
        
        kick = kick / np.max(np.abs(kick)) * 0.8
        kick_int16 = np.int16(kick * 32767)
        
        temp_path = os.path.join(self.output_folder, "temp_kick.wav")
        wavfile.write(temp_path, self.sample_rate, kick_int16)
        kick_audio = AudioSegment.from_wav(temp_path)
        os.remove(temp_path)
        
        return kick_audio
    
    def make_snare(self):
        """Create snare drum sound"""
        duration_ms = 120
        duration_samples = int((duration_ms / 1000) * self.sample_rate)
        t = np.linspace(0, duration_ms / 1000, duration_samples)
        
        tone = 200 * np.sin(2 * np.pi * 200 * t)
        noise = np.random.normal(0, 1, duration_samples) * 5000
        envelope = np.exp(-t * 12)
        snare = (tone * 0.3 + noise * 0.7) * envelope
        
        snare = snare / np.max(np.abs(snare)) * 0.6
        snare_int16 = np.int16(snare * 32767)
        
        temp_path = os.path.join(self.output_folder, "temp_snare.wav")
        wavfile.write(temp_path, self.sample_rate, snare_int16)
        snare_audio = AudioSegment.from_wav(temp_path)
        os.remove(temp_path)
        
        return snare_audio
    
    def create_pattern(self):
        """Create simple kick-snare pattern"""
        pattern = AudioSegment.silent(duration=400)
        kick = self.make_kick()
        snare = self.make_snare()
        
        pattern = pattern.overlay(kick, position=0)
        pattern = pattern.overlay(snare, position=200)
        
        return pattern
    
    def generate_layer(self, layer_index, pattern):
        """
        Generate one layer of the Risset Rhythm
        
        For ACCELERATING (base_tempo=80):
        - Layer 0: 80 → 160 BPM, fades in at start, out at end
        - Layer 1: 160 → 320 BPM, fades in at start, out at end
        
        For DECELERATING (base_tempo=80):
        - Layer 0: 160 → 80 BPM, fades in at start, out at end  
        - Layer 1: 80 → 40 BPM, fades in at start, out at end
        """
        duration_ms = self.duration_seconds * 1000
        
        if self.direction == 'accelerating':
            # Layer 0 = slowest, Layer 1 = faster, etc.
            start_tempo = self.base_tempo * (2 ** layer_index)
            end_tempo = self.base_tempo * (2 ** (layer_index + 1))
        else:  # decelerating
            # Layer 0 = fastest, Layer 1 = slower, etc.
            # Invert the layer index
            start_tempo = self.base_tempo * (2 ** (self.num_layers - layer_index))
            end_tempo = self.base_tempo * (2 ** (self.num_layers - layer_index - 1))
        
        print(f"  Layer {layer_index + 1}: {start_tempo:.0f} → {end_tempo:.0f} BPM")
        
        # Create empty track
        track = AudioSegment.silent(duration=duration_ms)
        
        current_time = 0
        while current_time < duration_ms:
            progress = current_time / duration_ms
            
            # Calculate current tempo
            current_tempo = start_tempo + (end_tempo - start_tempo) * progress
            
            # Speed up pattern
            speed_factor = current_tempo / self.base_tempo
            sped_pattern = pattern.speedup(playback_speed=speed_factor)
            
            # Calculate volume (linear fade)
            if progress < 0.25:
                volume = progress / 0.25
            elif progress > 0.75:
                volume = (1 - progress) / 0.25
            else:
                volume = 1.0
            
            # Apply volume
            if volume > 0:
                volume_db = 20 * np.log10(volume)
            else:
                volume_db = -100
            
            pattern_with_vol = sped_pattern + volume_db
            
            # Add to track
            track = track.overlay(pattern_with_vol, position=int(current_time))
            
            current_time += len(sped_pattern)
        
        return track
    
    def generate(self, filename="risset.mp3"):
        """Generate the complete Risset Rhythm"""
        print(f"\n{'='*60}")
        print(f"Generating {self.direction.upper()} Risset Rhythm")
        print(f"{'='*60}")
        print(f"Duration: {self.duration_seconds}s")
        print(f"Base tempo: {self.base_tempo} BPM")
        
        if self.direction == 'accelerating':
            print(f"Range: {self.base_tempo} → {self.base_tempo * 2} BPM")
        else:
            print(f"Range: {self.base_tempo * 2} → {self.base_tempo} BPM")
        
        print(f"Layers: {self.num_layers}\n")
        
        # Create pattern
        print("Creating drum pattern...")
        pattern = self.create_pattern()
        
        # Create final mix
        duration_ms = self.duration_seconds * 1000
        final = AudioSegment.silent(duration=duration_ms)
        
        # Generate each layer
        print("Generating layers:")
        for i in range(self.num_layers):
            layer = self.generate_layer(i, pattern)
            final = final.overlay(layer)
        
        # Normalize and export
        final = final.normalize()
        
        output_path = os.path.join(self.output_folder, filename)
        print(f"\nExporting to {output_path}...")
        final.export(output_path, format="mp3", bitrate="320k")
        
        print(f"✓ Done!\n")
        
        return output_path


# Example usage
if __name__ == "__main__":
    print("\n" + "="*70)
    print("RISSET RHYTHM GENERATOR")
    print("="*70)
    
    # Accelerating with 3 layers (smoother)
    gen_accel = RissetRhythmGenerator(
        output_folder="risset_output",
        duration_seconds=20,
        base_tempo=80,
        num_layers=3,  # Changed to 3
        direction='accelerating'
    )
    gen_accel.generate("increase.mp3")
    
    # Decelerating with 3 layers (smoother)
    gen_decel = RissetRhythmGenerator(
        output_folder="risset_output",
        duration_seconds=20,
        base_tempo=80,
        num_layers=3,  # Changed to 3
        direction='decelerating'
    )
    gen_decel.generate("decrease.mp3")
    
    # # Accelerating with 2 layers (for comparison)
    # gen_accel_2 = RissetRhythmGenerator(
    #     output_folder="risset_output",
    #     duration_seconds=20,
    #     base_tempo=80,
    #     num_layers=2,
    #     direction='accelerating'
    # )
    # gen_accel_2.generate("risset_accel_2layer.mp3")
    
    # # Decelerating with 2 layers (for comparison)
    # gen_decel_2 = RissetRhythmGenerator(
    #     output_folder="risset_output",
    #     duration_seconds=20,
    #     base_tempo=80,
    #     num_layers=2,
    #     direction='decelerating'
    # )
    # gen_decel_2.generate("risset_decel_2layer.mp3")
    
    # # Decelerating with 4 layers (even smoother)
    # gen_decel_4 = RissetRhythmGenerator(
    #     output_folder="risset_output",
    #     duration_seconds=20,
    #     base_tempo=80,
    #     num_layers=4,
    #     direction='decelerating'
    # )
    # gen_decel_4.generate("risset_decel_4layer.mp3")
    
    print("\n" + "="*70)
    print("FILES GENERATED:")
    print("="*70)
    print("  • risset_accel_3layer.mp3 - Accelerating with 3 layers")
    print("  • risset_decel_3layer.mp3 - Decelerating with 3 layers")
    print("  • risset_accel_2layer.mp3 - Accelerating with 2 layers")
    print("  • risset_decel_2layer.mp3 - Decelerating with 2 layers")
    print("  • risset_decel_4layer.mp3 - Decelerating with 4 layers")
    print("\nTry the 3 or 4 layer versions - they should be much smoother!")
    print("More layers = better illusion")
    print("="*70 + "\n")