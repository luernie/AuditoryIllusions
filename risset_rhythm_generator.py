"""
Classic Risset Rhythm Generator
Based on Dan Stowell's implementation and standard examples

This version is SIMPLE and WORKS LIKE THE POPULAR EXAMPLES:
- Uses a simple drum loop/pattern that repeats
- 2-3 voices with proper 2:1 speed ratio
- Linear fades (not cosine - simpler and cleaner)
- Actually sounds good!
"""

import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment
from pydub.generators import Square, Sine
import os

class ClassicRissetRhythm:
    def __init__(self,
                 output_folder="risset_output",
                 duration_seconds=20,
                 base_tempo=80,
                 num_layers=2,
                 sample_rate=44100):
        """
        Classic Risset Rhythm - Simple and Effective
        
        Parameters:
        -----------
        output_folder : str
            Where to save MP3 files
        duration_seconds : int
            Length of the audio
        base_tempo : float
            Starting tempo in BPM (typical: 60-120)
        num_layers : int
            Number of voices (2 or 3 recommended, 2 is classic)
        """
        self.output_folder = output_folder
        self.duration_seconds = duration_seconds
        self.base_tempo = base_tempo
        self.num_layers = num_layers
        self.sample_rate = sample_rate
        
        os.makedirs(output_folder, exist_ok=True)
    
    def create_simple_beat_pattern(self):
        """
        Create a simple 4-beat drum pattern
        This is the loop that will be sped up
        """
        # Create a basic kick-snare-kick-snare pattern
        pattern_duration_ms = 400  # Short pattern that will loop
        pattern = AudioSegment.silent(duration=pattern_duration_ms)
        
        # Kick drum (synthesized)
        kick = self.make_kick()
        # Snare drum (synthesized)
        snare = self.make_snare()
        
        # Pattern: Kick at 0ms, Snare at 200ms
        pattern = pattern.overlay(kick, position=0)
        pattern = pattern.overlay(snare, position=200)
        
        return pattern
    
    def make_kick(self, duration_ms=150):
        """Simple synthesized kick drum"""
        duration_samples = int((duration_ms / 1000) * self.sample_rate)
        t = np.linspace(0, duration_ms / 1000, duration_samples)
        
        # Frequency sweep from 150Hz to 40Hz
        freq = 150 * np.exp(-t * 10)
        phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
        
        # Quick decay envelope
        envelope = np.exp(-t * 7)
        
        # Generate kick
        kick = np.sin(phase) * envelope
        
        # Normalize and convert
        kick = kick / np.max(np.abs(kick)) * 0.8
        kick_int16 = np.int16(kick * 32767)
        
        # Save temp WAV and load as AudioSegment
        temp_path = os.path.join(self.output_folder, "temp_kick.wav")
        wavfile.write(temp_path, self.sample_rate, kick_int16)
        kick_audio = AudioSegment.from_wav(temp_path)
        os.remove(temp_path)
        
        return kick_audio
    
    def make_snare(self, duration_ms=120):
        """Simple synthesized snare drum"""
        duration_samples = int((duration_ms / 1000) * self.sample_rate)
        t = np.linspace(0, duration_ms / 1000, duration_samples)
        
        # Mix of tone and noise
        tone = 200 * np.sin(2 * np.pi * 200 * t)
        noise = np.random.normal(0, 1, duration_samples) * 5000
        
        # Quick envelope
        envelope = np.exp(-t * 12)
        
        # Mix tone and noise
        snare = (tone * 0.3 + noise * 0.7) * envelope
        
        # Normalize and convert
        snare = snare / np.max(np.abs(snare)) * 0.6
        snare_int16 = np.int16(snare * 32767)
        
        # Save temp WAV and load as AudioSegment
        temp_path = os.path.join(self.output_folder, "temp_snare.wav")
        wavfile.write(temp_path, self.sample_rate, snare_int16)
        snare_audio = AudioSegment.from_wav(temp_path)
        os.remove(temp_path)
        
        return snare_audio
    
    def generate_voice(self, voice_index, base_pattern):
        """
        Generate one voice/layer of the Risset Rhythm
        
        The voice:
        - Plays the pattern at increasing speed
        - Starts at base_tempo * (2^voice_index)
        - Ends at base_tempo * (2^(voice_index+1))
        - Uses LINEAR fade in/out (not cosine - simpler!)
        """
        duration_ms = self.duration_seconds * 1000
        
        # Calculate tempo range for this voice
        start_tempo = self.base_tempo * (2 ** voice_index)
        end_tempo = self.base_tempo * (2 ** (voice_index + 1))
        
        print(f"  Layer {voice_index + 1}: {start_tempo:.0f} → {end_tempo:.0f} BPM")
        
        # Create empty track
        voice = AudioSegment.silent(duration=duration_ms)
        
        # Calculate base pattern duration in ms at base tempo
        # At 80 BPM, one beat = 750ms, our pattern is 2 beats
        pattern_duration_at_base = (60000 / self.base_tempo) * 2
        
        current_time = 0
        while current_time < duration_ms:
            # Calculate progress (0 to 1)
            progress = current_time / duration_ms
            
            # Current tempo (linear acceleration)
            current_tempo = start_tempo + (end_tempo - start_tempo) * progress
            
            # Speed factor relative to base
            speed_factor = current_tempo / self.base_tempo
            
            # Speed up the pattern
            sped_up_pattern = base_pattern.speedup(playback_speed=speed_factor)
            
            # Calculate LINEAR fade volume
            if progress < 0.25:
                # Fade in during first 25%
                volume = progress / 0.25
            elif progress > 0.75:
                # Fade out during last 25%
                volume = (1 - progress) / 0.25
            else:
                # Full volume in the middle
                volume = 1.0
            
            # Apply volume (pydub uses dB)
            volume_db = 20 * np.log10(volume) if volume > 0 else -100
            pattern_with_volume = sped_up_pattern + volume_db
            
            # Overlay pattern
            voice = voice.overlay(pattern_with_volume, position=int(current_time))
            
            # Move to next pattern
            current_time += len(sped_up_pattern)
        
        return voice
    
    def generate(self, filename="risset_classic.mp3"):
        """
        Generate the complete Risset Rhythm
        """
        print(f"\n{'='*60}")
        print(f"Generating Classic Risset Rhythm")
        print(f"{'='*60}")
        print(f"Duration: {self.duration_seconds}s")
        print(f"Base tempo: {self.base_tempo} BPM")
        print(f"Tempo range: {self.base_tempo} → {self.base_tempo * 2} BPM")
        print(f"Layers: {self.num_layers}")
        print()
        
        # Create the base pattern
        print("Creating drum pattern...")
        base_pattern = self.create_simple_beat_pattern()
        
        # Create final mix
        duration_ms = self.duration_seconds * 1000
        final = AudioSegment.silent(duration=duration_ms)
        
        # Generate each voice
        print("Generating layers:")
        for i in range(self.num_layers):
            voice = self.generate_voice(i, base_pattern)
            final = final.overlay(voice)
        
        # Normalize
        final = final.normalize()
        
        # Export
        output_path = os.path.join(self.output_folder, filename)
        print(f"\nExporting to {output_path}...")
        final.export(output_path, format="mp3", bitrate="320k")
        
        print(f"✓ Done!")
        print(f"\nThis should sound like a continuously accelerating beat")
        print(f"that loops seamlessly without reaching infinite speed.\n")
        
        return output_path


# Example usage
if __name__ == "__main__":
    print("\n" + "="*60)
    print("CLASSIC RISSET RHYTHM GENERATOR")
    print("Based on standard/popular implementations")
    print("="*60)
    
    # Classic 2-layer version (like most examples)
    generator = ClassicRissetRhythm(
        output_folder="risset_classic",
        duration_seconds=20,
        base_tempo=80,
        num_layers=2  # Classic uses just 2 layers!
    )
    generator.generate("risset_classic_2layer.mp3")
    
    # 3-layer version (smoother)
    generator3 = ClassicRissetRhythm(
        output_folder="risset_classic",
        duration_seconds=20,
        base_tempo=80,
        num_layers=3
    )
    generator3.generate("risset_classic_3layer.mp3")
    
    # Slower version
    generator_slow = ClassicRissetRhythm(
        output_folder="risset_classic",
        duration_seconds=30,
        base_tempo=60,
        num_layers=2
    )
    generator_slow.generate("risset_slow.mp3")
    
    # Faster version
    generator_fast = ClassicRissetRhythm(
        output_folder="risset_classic",
        duration_seconds=15,
        base_tempo=100,
        num_layers=2
    )
    generator_fast.generate("risset_fast.mp3")
    
    print("\n" + "="*60)
    print("ALL VERSIONS GENERATED!")
    print("="*60)
    print("\nFiles created:")
    print("  • risset_classic_2layer.mp3 - Standard version (like popular examples)")
    print("  • risset_classic_3layer.mp3 - Smoother 3-layer version")
    print("  • risset_slow.mp3 - Slower tempo")
    print("  • risset_fast.mp3 - Faster tempo")
    print("\nKey differences from previous version:")
    print("  ✓ Uses simple drum loop pattern (not individual kicks)")
    print("  ✓ Linear fades (simpler, cleaner)")
    print("  ✓ Just 2 layers (classic standard)")
    print("  ✓ Simpler overall - ACTUALLY SOUNDS GOOD!")
    print()