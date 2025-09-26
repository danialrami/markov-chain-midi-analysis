#!/usr/bin/env python3
"""
MIDI Generator using Polyphonic Markov Chain Models
Generates full-length songs with intelligent rhythm, structure, and optional key quantization.
"""

import pickle
import random
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set
from collections import Counter, defaultdict
import pretty_midi
import argparse
from dataclasses import dataclass


@dataclass
class GenerationConfig:
    """Configuration for MIDI generation."""
    target_duration_minutes: float = 5.5  # 5-6 minutes
    bpm: int = 120
    time_signature: Tuple[int, int] = (4, 4)
    
    # Musical structure
    intro_bars: int = 8
    verse_bars: int = 16
    chorus_bars: int = 16
    bridge_bars: int = 8
    outro_bars: int = 8
    
    # Rhythm parameters
    min_chord_duration: float = 0.25  # 16th note minimum
    max_chord_duration: float = 4.0   # Whole note maximum
    rest_probability: float = 0.1     # 10% chance of rest
    
    # Key quantization
    use_key_quantization: bool = False
    force_key: Optional[str] = None  # e.g., "C major", "A minor"
    
    # Generation parameters
    max_polyphony: int = 6  # Maximum notes per chord
    velocity_range: Tuple[int, int] = (60, 100)


class KeyDetector:
    """Detect and quantize to musical keys."""
    
    MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
    MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
    
    KEY_SIGNATURES = {
        # Major keys
        'C major': (0, MAJOR_SCALE),
        'G major': (7, MAJOR_SCALE),
        'D major': (2, MAJOR_SCALE),
        'A major': (9, MAJOR_SCALE),
        'E major': (4, MAJOR_SCALE),
        'B major': (11, MAJOR_SCALE),
        'F# major': (6, MAJOR_SCALE),
        'C# major': (1, MAJOR_SCALE),
        'F major': (5, MAJOR_SCALE),
        'Bb major': (10, MAJOR_SCALE),
        'Eb major': (3, MAJOR_SCALE),
        'Ab major': (8, MAJOR_SCALE),
        
        # Minor keys
        'A minor': (9, MINOR_SCALE),
        'E minor': (4, MINOR_SCALE),
        'B minor': (11, MINOR_SCALE),
        'F# minor': (6, MINOR_SCALE),
        'C# minor': (1, MINOR_SCALE),
        'G# minor': (8, MINOR_SCALE),
        'D# minor': (3, MINOR_SCALE),
        'A# minor': (10, MINOR_SCALE),
        'D minor': (2, MINOR_SCALE),
        'G minor': (7, MINOR_SCALE),
        'C minor': (0, MINOR_SCALE),
        'F minor': (5, MINOR_SCALE),
    }
    
    @classmethod
    def detect_key_from_chords(cls, chord_signatures: List[Tuple[int, ...]]) -> str:
        """Detect most likely key from chord progressions."""
        # Count all notes used
        note_counts = Counter()
        for chord in chord_signatures:
            for interval in chord:
                # Convert intervals back to note classes (mod 12)
                note_counts[interval % 12] += 1
        
        # Find best matching key
        best_key = "C major"
        best_score = 0
        
        for key_name, (root, scale) in cls.KEY_SIGNATURES.items():
            key_notes = {(root + interval) % 12 for interval in scale}
            
            # Score based on how many used notes are in this key
            score = sum(count for note, count in note_counts.items() 
                       if note in key_notes)
            
            if score > best_score:
                best_score = score
                best_key = key_name
        
        return best_key
    
    @classmethod
    def quantize_to_key(cls, notes: List[int], key: str) -> List[int]:
        """Quantize notes to the nearest notes in the specified key."""
        if key not in cls.KEY_SIGNATURES:
            return notes  # Return unchanged if key not recognized
        
        root, scale = cls.KEY_SIGNATURES[key]
        key_notes = {(root + interval) % 12 for interval in scale}
        
        quantized = []
        for note in notes:
            note_class = note % 12
            octave = note // 12
            
            if note_class in key_notes:
                quantized.append(note)  # Already in key
            else:
                # Find nearest note in key
                distances = [(abs(note_class - key_note) % 12, key_note) 
                           for key_note in key_notes]
                distances.extend([(12 - (abs(note_class - key_note) % 12), key_note) 
                                for key_note in key_notes])
                
                _, nearest_note = min(distances)
                quantized.append(octave * 12 + nearest_note)
        
        return quantized


class RhythmGenerator:
    """Generate realistic rhythmic patterns."""
    
    def __init__(self, config: GenerationConfig):
        self.config = config
        self.beat_duration = 60.0 / config.bpm  # Duration of one beat in seconds
        
        # Common rhythm patterns (in beats)
        self.rhythm_patterns = [
            [1.0],           # Quarter notes
            [0.5, 0.5],      # Two eighth notes
            [1.0, 1.0],      # Two quarter notes
            [2.0],           # Half note
            [1.5, 0.5],      # Dotted quarter + eighth
            [0.5, 1.0, 0.5], # Eighth, quarter, eighth
            [4.0],           # Whole note
            [0.25, 0.25, 0.5], # Two sixteenths + eighth
        ]
        
        # Weight patterns by musical preference
        self.pattern_weights = [0.3, 0.2, 0.15, 0.1, 0.1, 0.05, 0.05, 0.05]
    
    def generate_rhythm_for_bars(self, num_bars: int) -> List[Tuple[float, float]]:
        """Generate rhythm pattern for specified number of bars.
        Returns list of (start_time, duration) tuples in seconds.
        """
        rhythm_events = []
        current_time = 0.0
        beats_per_bar = self.config.time_signature[0]
        bar_duration = beats_per_bar * self.beat_duration
        
        for bar in range(num_bars):
            bar_start = bar * bar_duration
            bar_time = 0.0
            
            # Fill each bar with rhythm patterns
            while bar_time < beats_per_bar:
                # Choose rhythm pattern
                pattern = np.random.choice(
                    len(self.rhythm_patterns),
                    p=self.pattern_weights
                )
                
                rhythm_pattern = self.rhythm_patterns[pattern]
                
                for beat_duration in rhythm_pattern:
                    if bar_time + beat_duration > beats_per_bar:
                        # Truncate if pattern would exceed bar
                        beat_duration = beats_per_bar - bar_time
                    
                    if beat_duration > 0:
                        # Decide if this should be a rest
                        if random.random() < self.config.rest_probability:
                            # Skip this beat (rest)
                            pass
                        else:
                            start_time = bar_start + (bar_time * self.beat_duration)
                            duration = beat_duration * self.beat_duration
                            rhythm_events.append((start_time, duration))
                        
                        bar_time += beat_duration
                    
                    if bar_time >= beats_per_bar:
                        break
        
        return rhythm_events


class MIDIGenerator:
    """Main MIDI generation class."""
    
    def __init__(self, chord_model_path: str, note_model_path: str, 
                 config: GenerationConfig = None):
        self.config = config or GenerationConfig()
        
        # Load models
        print("Loading chord transition model...")
        with open(chord_model_path, 'rb') as f:
            self.chord_model = pickle.load(f)
        
        print("Loading note transition model...")
        with open(note_model_path, 'rb') as f:
            self.note_model = pickle.load(f)
        
        self.rhythm_generator = RhythmGenerator(self.config)
        
        print(f"Loaded models with {len(self.chord_model)} chord types and "
              f"{len(self.note_model)} note contexts")
    
    def choose_starting_chord(self) -> Tuple[int, ...]:
        """Choose a good starting chord based on model frequency."""
        # Count total occurrences of each chord
        chord_popularity = {}
        for chord, transitions in self.chord_model.items():
            chord_popularity[chord] = sum(transitions.values())
        
        # Choose from top 20% most popular chords
        sorted_chords = sorted(chord_popularity.items(), key=lambda x: x[1], reverse=True)
        top_chords = sorted_chords[:max(1, len(sorted_chords) // 5)]
        
        # Extract chords and weights separately
        chords = [chord for chord, weight in top_chords]
        weights = [weight for chord, weight in top_chords]
        
        # Normalize weights
        total_weight = sum(weights)
        probabilities = [w / total_weight for w in weights]
        
        # Use indices for np.random.choice to avoid array shape issues
        chosen_index = np.random.choice(len(chords), p=probabilities)
        return chords[chosen_index]
    
    def generate_chord_progression(self, num_chords: int, 
                                 start_chord: Tuple[int, ...] = None) -> List[Tuple[int, ...]]:
        """Generate a chord progression using the chord model."""
        if start_chord is None:
            start_chord = self.choose_starting_chord()
        
        progression = [start_chord]
        current_chord = start_chord
        
        for _ in range(num_chords - 1):
            if current_chord in self.chord_model:
                next_chords = list(self.chord_model[current_chord].keys())
                probabilities = list(self.chord_model[current_chord].values())
                
                # Add some randomness to avoid repetitive patterns
                probabilities = np.array(probabilities)
                probabilities = probabilities ** 0.8  # Flatten distribution slightly
                probabilities /= probabilities.sum()
                
                # Use indices to avoid array shape issues
                chosen_index = np.random.choice(len(next_chords), p=probabilities)
                next_chord = next_chords[chosen_index]
                progression.append(next_chord)
                current_chord = next_chord
            else:
                # Fallback: choose random chord
                current_chord = self.choose_starting_chord()
                progression.append(current_chord)
        
        return progression
    
    def intervals_to_notes(self, chord_signature: Tuple[int, ...], 
                          base_octave: int = 4) -> List[int]:
        """Convert chord intervals to actual MIDI note numbers."""
        base_note = base_octave * 12 + 60  # Middle C area
        
        # Add some variation in root note
        root_variation = random.randint(-12, 12)  # Up to one octave variation
        root_note = base_note + root_variation
        
        notes = []
        for interval in chord_signature:
            note = root_note + interval
            # Keep notes in reasonable MIDI range
            while note < 21:  # Below piano range
                note += 12
            while note > 108:  # Above piano range
                note -= 12
            notes.append(note)
        
        return notes
    
    def generate_melody_notes(self, chord_notes: List[int], 
                            chord_signature: Tuple[int, ...]) -> List[int]:
        """Generate additional melody notes using the note model."""
        melody_notes = []
        
        for chord_note in chord_notes:
            context = (chord_note, chord_signature)
            
            if context in self.note_model:
                possible_notes = list(self.note_model[context].keys())
                probabilities = list(self.note_model[context].values())
                
                # Normalize probabilities
                probabilities = np.array(probabilities)
                probabilities /= probabilities.sum()
                
                # Limit to reasonable polyphony
                num_additional = min(
                    random.randint(0, 2),  # 0-2 additional notes per chord note
                    self.config.max_polyphony - len(chord_notes)
                )
                
                for _ in range(num_additional):
                    if possible_notes:
                        chosen_index = np.random.choice(len(possible_notes), p=probabilities)
                        additional_note = possible_notes[chosen_index]
                        # Avoid exact duplicates
                        if additional_note not in chord_notes + melody_notes:
                            melody_notes.append(additional_note)
        
        return melody_notes
    
    def generate_song_structure(self) -> Dict[str, List[Tuple[int, ...]]]:
        """Generate chord progressions for different song sections."""
        print("Generating song structure...")
        
        # Calculate total bars needed
        total_duration = self.config.target_duration_minutes * 60
        bar_duration = (self.config.time_signature[0] * 60) / self.config.bpm
        total_bars = int(total_duration / bar_duration)
        
        # Adjust section lengths to fit total duration
        base_sections = (self.config.intro_bars + self.config.verse_bars + 
                        self.config.chorus_bars + self.config.bridge_bars + 
                        self.config.outro_bars)
        
        repetitions = max(1, total_bars // base_sections)
        
        sections = {}
        
        # Generate chord progressions for each section type
        sections['intro'] = self.generate_chord_progression(self.config.intro_bars)
        sections['verse'] = self.generate_chord_progression(self.config.verse_bars)
        sections['chorus'] = self.generate_chord_progression(self.config.chorus_bars)
        sections['bridge'] = self.generate_chord_progression(self.config.bridge_bars)
        sections['outro'] = self.generate_chord_progression(self.config.outro_bars)
        
        return sections
    
    def create_midi_file(self, output_path: str = "generated_song.mid"):
        """Generate and save a complete MIDI file."""
        print(f"Generating MIDI file: {output_path}")
        
        # Create MIDI object
        midi = pretty_midi.PrettyMIDI(initial_tempo=self.config.bpm)
        
        # Create instrument (piano)
        piano = pretty_midi.Instrument(program=0, name="Generated Piano")
        
        # Generate song structure
        sections = self.generate_song_structure()
        
        # Create full song arrangement
        arrangement = [
            ('intro', sections['intro']),
            ('verse', sections['verse']),
            ('chorus', sections['chorus']),
            ('verse', sections['verse']),  # Repeat verse
            ('chorus', sections['chorus']),  # Repeat chorus
            ('bridge', sections['bridge']),
            ('chorus', sections['chorus']),  # Final chorus
            ('outro', sections['outro'])
        ]
        
        # Flatten arrangement into single chord progression
        full_progression = []
        for section_name, chords in arrangement:
            full_progression.extend(chords)
        
        print(f"Total song length: {len(full_progression)} chords")
        
        # Generate rhythm for entire song
        total_bars = len(full_progression)
        rhythm_events = self.rhythm_generator.generate_rhythm_for_bars(total_bars)
        
        print(f"Generated {len(rhythm_events)} rhythmic events")
        
        # Optional key detection and quantization
        detected_key = None
        if self.config.use_key_quantization or self.config.force_key:
            if self.config.force_key:
                detected_key = self.config.force_key
                print(f"Using forced key: {detected_key}")
            else:
                detected_key = KeyDetector.detect_key_from_chords(full_progression)
                print(f"Detected key: {detected_key}")
        
        # Generate MIDI notes
        for i, (start_time, duration) in enumerate(rhythm_events):
            if i >= len(full_progression):
                break
                
            chord_signature = full_progression[i]
            
            # Convert chord to notes
            chord_notes = self.intervals_to_notes(chord_signature)
            
            # Generate additional melody notes
            melody_notes = self.generate_melody_notes(chord_notes, chord_signature)
            
            # Combine all notes
            all_notes = chord_notes + melody_notes
            
            # Apply key quantization if enabled
            if detected_key:
                all_notes = KeyDetector.quantize_to_key(all_notes, detected_key)
            
            # Remove duplicates and limit polyphony
            all_notes = list(set(all_notes))[:self.config.max_polyphony]
            
            # Create MIDI notes
            for note_pitch in all_notes:
                # Ensure note is in valid MIDI range
                note_pitch = max(21, min(108, note_pitch))
                
                # Random velocity within range
                velocity = random.randint(*self.config.velocity_range)
                
                # Create note
                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=note_pitch,
                    start=start_time,
                    end=start_time + duration * 0.95  # Slight gap between notes
                )
                piano.notes.append(note)
        
        # Add instrument to MIDI file
        midi.instruments.append(piano)
        
        # Save MIDI file
        midi.write(output_path)
        
        # Print generation summary
        total_duration = rhythm_events[-1][0] + rhythm_events[-1][1] if rhythm_events else 0
        print(f"\n🎵 Generated MIDI file: {output_path}")
        print(f"📊 Statistics:")
        print(f"   ⏱️  Duration: {total_duration/60:.2f} minutes")
        print(f"   🎼 Total notes: {len(piano.notes)}")
        print(f"   🎭 Chord progressions: {len(full_progression)}")
        print(f"   🎯 Key: {detected_key or 'Free (no quantization)'}")
        print(f"   🎤 Average polyphony: {len(piano.notes)/len(rhythm_events):.1f} notes/chord")
        
        return output_path


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="Generate MIDI from Markov chain models")
    parser.add_argument("--models_dir", default="markov_analysis_output", 
                       help="Directory containing the model files")
    parser.add_argument("--output", default="generated_song.mid", 
                       help="Output MIDI file name")
    parser.add_argument("--duration", type=float, default=5.5, 
                       help="Song duration in minutes (default: 5.5)")
    parser.add_argument("--bpm", type=int, default=120, 
                       help="Beats per minute (default: 120)")
    parser.add_argument("--key", type=str, 
                       help="Force specific key (e.g., 'C major', 'A minor')")
    parser.add_argument("--quantize_key", action="store_true", 
                       help="Auto-detect and quantize to most likely key")
    parser.add_argument("--max_polyphony", type=int, default=6, 
                       help="Maximum simultaneous notes (default: 6)")
    
    args = parser.parse_args()
    
    # Setup paths
    models_dir = Path(args.models_dir)
    chord_model_path = models_dir / "chord_transitions.pkl"
    note_model_path = models_dir / "note_transitions.pkl"
    
    # Check if model files exist
    if not chord_model_path.exists():
        print(f"❌ Chord model not found: {chord_model_path}")
        print("Make sure you've run the analysis first!")
        return
    
    if not note_model_path.exists():
        print(f"❌ Note model not found: {note_model_path}")
        print("Make sure you've run the analysis first!")
        return
    
    # Create configuration
    config = GenerationConfig(
        target_duration_minutes=args.duration,
        bpm=args.bpm,
        use_key_quantization=args.quantize_key,
        force_key=args.key,
        max_polyphony=args.max_polyphony
    )
    
    print("🎼 Starting MIDI generation...")
    print(f"Configuration: {args.duration} minutes at {args.bpm} BPM")
    if args.key:
        print(f"Forced key: {args.key}")
    elif args.quantize_key:
        print("Key quantization: Auto-detect")
    else:
        print("Key quantization: Disabled")
    
    # Generate MIDI
    try:
        generator = MIDIGenerator(
            str(chord_model_path), 
            str(note_model_path), 
            config
        )
        
        output_path = generator.create_midi_file(args.output)
        print(f"\n✅ Success! Generated: {output_path}")
        print(f"🎧 You can now play this MIDI file in any MIDI player or DAW!")
        
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        raise


if __name__ == "__main__":
    main()
