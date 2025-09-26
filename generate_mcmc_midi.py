#!/usr/bin/env python3
"""
MCMC MIDI Generator using Polyphonic Markov Chain Models
Enhanced with Markov Chain Monte Carlo for global optimization and quality control.
Fixed to include sophisticated rhythm generation from the original version.
"""

import pickle
import random
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set, Callable
from collections import Counter, defaultdict
import pretty_midi
import argparse
from dataclasses import dataclass
import math


@dataclass
class MCMCConfig:
    """Configuration for MCMC-enhanced MIDI generation."""
    # Basic generation parameters
    target_duration_minutes: float = 5.5
    bpm: int = 120
    time_signature: Tuple[int, int] = (4, 4)
    
    # Musical structure
    intro_bars: int = 8
    verse_bars: int = 16
    chorus_bars: int = 16
    bridge_bars: int = 8
    outro_bars: int = 8
    
    # Rhythm parameters (restored from original)
    min_chord_duration: float = 0.25  # 16th note minimum
    max_chord_duration: float = 4.0   # Whole note maximum
    rest_probability: float = 0.1     # 10% chance of rest
    
    # MCMC-specific parameters
    mcmc_iterations: int = 1000  # Number of MCMC steps per chord position
    burn_in_period: int = 100    # Burn-in iterations before sampling
    temperature: float = 1.0     # Temperature parameter for acceptance
    quality_weight: float = 0.7  # Weight of quality vs. transition probability
    
    # Quality function weights
    harmonic_weight: float = 0.3
    melodic_weight: float = 0.2
    rhythmic_weight: float = 0.2
    coherence_weight: float = 0.3
    
    # Constraints
    enforce_key: bool = True
    maintain_voice_leading: bool = True
    rhythmic_consistency: float = 0.8  # 0-1, higher = more consistent rhythm
    
    # Generation parameters
    max_polyphony: int = 6
    velocity_range: Tuple[int, int] = (60, 100)
    use_key_quantization: bool = False
    force_key: Optional[str] = None


class RhythmGenerator:
    """Generate realistic rhythmic patterns - restored from original."""
    
    def __init__(self, config: MCMCConfig):
        self.config = config
        self.beat_duration = 60.0 / config.bpm  # Duration of one beat in seconds
        
        # Common rhythm patterns (in beats) - same as original
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


class MusicalQualityEvaluator:
    """Evaluates musical quality for MCMC acceptance decisions."""
    
    def __init__(self, config: MCMCConfig):
        self.config = config
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        # Scale templates for key analysis
        self.major_scale = [0, 2, 4, 5, 7, 9, 11]
        self.minor_scale = [0, 2, 3, 5, 7, 8, 10]
        
    def evaluate_sequence_quality(self, chord_sequence: List[Tuple[int, ...]], 
                                target_key: str = None) -> float:
        """Evaluate overall quality of a chord sequence (0-1 scale)."""
        if len(chord_sequence) < 2:
            return 0.5  # Neutral for short sequences
        
        scores = {
            'harmonic': self.evaluate_harmonic_consistency(chord_sequence, target_key),
            'melodic': self.evaluate_melodic_smoothness(chord_sequence),
            'rhythmic': self.evaluate_rhythmic_interest(chord_sequence),
            'coherence': self.evaluate_overall_coherence(chord_sequence)
        }
        
        weighted_score = (
            scores['harmonic'] * self.config.harmonic_weight +
            scores['melodic'] * self.config.melodic_weight +
            scores['rhythmic'] * self.config.rhythmic_weight +
            scores['coherence'] * self.config.coherence_weight
        )
        
        return max(0.0, min(1.0, weighted_score))
    
    def evaluate_harmonic_consistency(self, chord_sequence: List[Tuple[int, ...]], 
                                    target_key: str = None) -> float:
        """Evaluate harmonic consistency and key adherence."""
        if not chord_sequence:
            return 0.5
        
        # Extract all notes from chords
        all_notes = []
        for chord in chord_sequence:
            all_notes.extend([note % 12 for note in chord])
        
        if not all_notes:
            return 0.5
        
        # If target key specified, check adherence
        if target_key and self.config.enforce_key:
            key_score = self.calculate_key_adherence(all_notes, target_key)
        else:
            # Find best-fitting key and calculate adherence
            key_score = self.calculate_best_key_fit(all_notes)
        
        # Penalize extreme dissonance
        dissonance_penalty = self.calculate_dissonance_penalty(chord_sequence)
        
        return max(0.0, key_score - dissonance_penalty)
    
    def calculate_key_adherence(self, notes: List[int], target_key: str) -> float:
        """Calculate how well notes fit a target key."""
        if not notes:
            return 0.5
        
        # Parse key
        if 'major' in target_key.lower():
            root_name = target_key.split()[0]
            scale_template = self.major_scale
        elif 'minor' in target_key.lower():
            root_name = target_key.split()[0]
            scale_template = self.minor_scale
        else:
            return 0.5  # Unknown key format
        
        try:
            root = self.note_names.index(root_name)
        except ValueError:
            return 0.5  # Invalid root note
        
        # Create scale notes
        scale_notes = {(root + interval) % 12 for interval in scale_template}
        
        # Calculate adherence
        in_key_count = sum(1 for note in notes if note in scale_notes)
        return in_key_count / len(notes)
    
    def calculate_best_key_fit(self, notes: List[int]) -> float:
        """Find best key fit and return adherence score."""
        if not notes:
            return 0.5
        
        note_counts = Counter(notes)
        best_score = 0
        
        # Test all 24 keys (12 major + 12 minor)
        for root in range(12):
            # Test major
            major_notes = {(root + interval) % 12 for interval in self.major_scale}
            major_score = sum(count for note, count in note_counts.items() if note in major_notes)
            
            # Test minor
            minor_notes = {(root + interval) % 12 for interval in self.minor_scale}
            minor_score = sum(count for note, count in note_counts.items() if note in minor_notes)
            
            best_score = max(best_score, major_score, minor_score)
        
        return best_score / sum(note_counts.values())
    
    def calculate_dissonance_penalty(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Calculate penalty for excessive dissonance."""
        total_dissonance = 0
        chord_count = 0
        
        for chord in chord_sequence:
            if len(chord) < 2:
                continue
            
            chord_count += 1
            sorted_chord = sorted(chord)
            
            # Check for harsh intervals (minor 2nd, major 7th in same octave)
            for i in range(len(sorted_chord)):
                for j in range(i + 1, len(sorted_chord)):
                    interval = (sorted_chord[j] - sorted_chord[i]) % 12
                    if interval in [1, 11]:  # Minor 2nd or major 7th
                        total_dissonance += 0.1
        
        return (total_dissonance / max(1, chord_count)) if chord_count > 0 else 0
    
    def evaluate_melodic_smoothness(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Evaluate melodic voice leading between chords."""
        if len(chord_sequence) < 2:
            return 0.5
        
        smoothness_scores = []
        
        for i in range(len(chord_sequence) - 1):
            current_chord = sorted(chord_sequence[i])
            next_chord = sorted(chord_sequence[i + 1])
            
            if not current_chord or not next_chord:
                continue
            
            # Calculate voice leading distance
            if self.config.maintain_voice_leading:
                smoothness = self.calculate_voice_leading_smoothness(current_chord, next_chord)
            else:
                # Simple approach: average interval distance
                smoothness = self.calculate_average_interval_distance(current_chord, next_chord)
            
            smoothness_scores.append(smoothness)
        
        return np.mean(smoothness_scores) if smoothness_scores else 0.5
    
    def calculate_voice_leading_smoothness(self, chord1: List[int], chord2: List[int]) -> float:
        """Calculate optimal voice leading smoothness."""
        if not chord1 or not chord2:
            return 0.5
        
        # For simplicity, use nearest-neighbor voice leading
        total_distance = 0
        max_voices = max(len(chord1), len(chord2))
        
        # Pad shorter chord with repetitions
        padded_chord1 = (chord1 * (max_voices // len(chord1) + 1))[:max_voices]
        padded_chord2 = (chord2 * (max_voices // len(chord2) + 1))[:max_voices]
        
        for note1, note2 in zip(padded_chord1, padded_chord2):
            distance = abs(note1 - note2)
            # Penalize large jumps
            if distance > 12:  # More than an octave
                total_distance += distance * 1.5
            else:
                total_distance += distance
        
        # Convert to smoothness score (lower distance = higher smoothness)
        avg_distance = total_distance / max_voices
        smoothness = max(0, 1 - (avg_distance / 24))  # Normalize to 0-1
        
        return smoothness
    
    def calculate_average_interval_distance(self, chord1: List[int], chord2: List[int]) -> float:
        """Simple interval distance calculation."""
        if not chord1 or not chord2:
            return 0.5
        
        # Use root notes for simple comparison
        root1 = min(chord1)
        root2 = min(chord2)
        distance = abs(root1 - root2)
        
        # Normalize to 0-1 (closer = better)
        return max(0, 1 - (distance / 24))
    
    def evaluate_rhythmic_interest(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Evaluate rhythmic interest and variety."""
        # For chord sequences, we evaluate variety in chord complexity
        if not chord_sequence:
            return 0.5
        
        chord_sizes = [len(chord) for chord in chord_sequence]
        
        # Reward variety in chord sizes
        size_variety = len(set(chord_sizes)) / max(1, len(chord_sizes))
        
        # Reward moderate complexity (not too simple, not too complex)
        avg_size = np.mean(chord_sizes)
        complexity_score = 1 - abs(avg_size - 4) / 4  # Optimal around 4 notes
        complexity_score = max(0, complexity_score)
        
        return (size_variety + complexity_score) / 2
    
    def evaluate_overall_coherence(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Evaluate overall structural coherence."""
        if len(chord_sequence) < 4:
            return 0.5
        
        # Check for repetitive patterns (good for structure)
        pattern_score = self.evaluate_pattern_coherence(chord_sequence)
        
        # Check for balanced complexity throughout
        balance_score = self.evaluate_complexity_balance(chord_sequence)
        
        return (pattern_score + balance_score) / 2
    
    def evaluate_pattern_coherence(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Evaluate presence of coherent patterns."""
        if len(chord_sequence) < 4:
            return 0.5
        
        # Look for repeated subsequences
        pattern_matches = 0
        total_comparisons = 0
        
        for length in [2, 3, 4]:  # Check 2-4 chord patterns
            for i in range(len(chord_sequence) - length):
                pattern = chord_sequence[i:i+length]
                
                # Look for this pattern elsewhere
                for j in range(i + length, len(chord_sequence) - length + 1):
                    comparison = chord_sequence[j:j+length]
                    if pattern == comparison:
                        pattern_matches += 1
                    total_comparisons += 1
        
        if total_comparisons == 0:
            return 0.5
        
        # Moderate repetition is good (not too little, not too much)
        repetition_rate = pattern_matches / total_comparisons
        optimal_rate = 0.2  # 20% repetition is good
        
        return 1 - abs(repetition_rate - optimal_rate) / optimal_rate
    
    def evaluate_complexity_balance(self, chord_sequence: List[Tuple[int, ...]]) -> float:
        """Evaluate balance of complexity throughout the sequence."""
        if not chord_sequence:
            return 0.5
        
        # Calculate complexity for each chord (based on size and intervals)
        complexities = []
        for chord in chord_sequence:
            if not chord:
                complexities.append(0)
                continue
            
            # Base complexity on chord size and interval spread
            size_complexity = len(chord) / 8  # Normalize by max expected size
            
            if len(chord) > 1:
                interval_spread = (max(chord) - min(chord)) / 48  # Normalize by 4 octaves
                interval_complexity = interval_spread
            else:
                interval_complexity = 0
            
            total_complexity = (size_complexity + interval_complexity) / 2
            complexities.append(total_complexity)
        
        # Check for gradual changes (avoid sudden jumps in complexity)
        if len(complexities) < 2:
            return 0.5
        
        complexity_changes = []
        for i in range(len(complexities) - 1):
            change = abs(complexities[i+1] - complexities[i])
            complexity_changes.append(change)
        
        avg_change = np.mean(complexity_changes)
        # Penalize sudden large changes
        balance_score = max(0, 1 - (avg_change * 2))  # Normalize
        
        return balance_score


class MCMCMIDIGenerator:
    """MCMC-enhanced MIDI generator with global optimization and proper rhythm."""
    
    def __init__(self, chord_model_path: str, note_model_path: str, 
                 config: MCMCConfig = None):
        self.config = config or MCMCConfig()
        
        # Load models
        print("Loading chord transition model...")
        with open(chord_model_path, 'rb') as f:
            self.chord_model = pickle.load(f)
        
        print("Loading note transition model...")
        with open(note_model_path, 'rb') as f:
            self.note_model = pickle.load(f)
        
        # Initialize quality evaluator and rhythm generator
        self.quality_evaluator = MusicalQualityEvaluator(self.config)
        self.rhythm_generator = RhythmGenerator(self.config)  # Added back!
        
        print(f"Loaded models with {len(self.chord_model)} chord types and "
              f"{len(self.note_model)} note contexts")
        print(f"MCMC Configuration: {self.config.mcmc_iterations} iterations, "
              f"burn-in: {self.config.burn_in_period}, temperature: {self.config.temperature}")
    
    def propose_chord_transition(self, current_chord: Tuple[int, ...]) -> Tuple[int, ...]:
        """Propose next chord based on transition model."""
        if current_chord in self.chord_model:
            next_chords = list(self.chord_model[current_chord].keys())
            probabilities = list(self.chord_model[current_chord].values())
            
            # Add small random noise to avoid getting stuck
            probabilities = np.array(probabilities)
            probabilities += np.random.normal(0, 0.01, len(probabilities))
            probabilities = np.maximum(probabilities, 0.001)  # Ensure positive
            probabilities /= probabilities.sum()
            
            chosen_index = np.random.choice(len(next_chords), p=probabilities)
            return next_chords[chosen_index]
        else:
            # Fallback: choose random chord from model
            return random.choice(list(self.chord_model.keys()))
    
    def mcmc_optimize_sequence(self, initial_sequence: List[Tuple[int, ...]], 
                             target_key: str = None) -> List[Tuple[int, ...]]:
        """Optimize chord sequence using MCMC."""
        print(f"🎯 Optimizing sequence with MCMC ({self.config.mcmc_iterations} iterations)...")
        
        current_sequence = initial_sequence.copy()
        current_quality = self.quality_evaluator.evaluate_sequence_quality(current_sequence, target_key)
        
        best_sequence = current_sequence.copy()
        best_quality = current_quality
        
        accepted_proposals = 0
        quality_history = []
        
        for iteration in range(self.config.mcmc_iterations):
            # Propose modification (modify a random chord)
            if len(current_sequence) > 1:
                # Choose random position to modify (avoid first chord to maintain structure)
                modify_pos = random.randint(1, len(current_sequence) - 1)
                
                # Propose new chord based on previous chord
                prev_chord = current_sequence[modify_pos - 1]
                proposed_chord = self.propose_chord_transition(prev_chord)
                
                # Create proposed sequence
                proposed_sequence = current_sequence.copy()
                proposed_sequence[modify_pos] = proposed_chord
                
                # Evaluate proposed sequence
                proposed_quality = self.quality_evaluator.evaluate_sequence_quality(
                    proposed_sequence, target_key
                )
                
                # Calculate acceptance probability
                delta_quality = proposed_quality - current_quality
                
                # Combined score: quality + transition probability
                transition_prob = self.get_transition_probability(prev_chord, proposed_chord)
                combined_score = (self.config.quality_weight * proposed_quality + 
                                (1 - self.config.quality_weight) * transition_prob)
                
                current_combined = (self.config.quality_weight * current_quality + 
                                  (1 - self.config.quality_weight) * 
                                  self.get_transition_probability(prev_chord, current_sequence[modify_pos]))
                
                delta_combined = combined_score - current_combined
                
                # Metropolis-Hastings acceptance criterion
                acceptance_prob = min(1.0, math.exp(delta_combined / self.config.temperature))
                
                if random.random() < acceptance_prob:
                    current_sequence = proposed_sequence
                    current_quality = proposed_quality
                    accepted_proposals += 1
                    
                    # Track best sequence
                    if current_quality > best_quality:
                        best_sequence = current_sequence.copy()
                        best_quality = current_quality
            
            # Record quality history (after burn-in)
            if iteration >= self.config.burn_in_period:
                quality_history.append(current_quality)
            
            # Progress update
            if (iteration + 1) % 100 == 0:
                avg_quality = np.mean(quality_history) if quality_history else current_quality
                print(f"   Iteration {iteration + 1}/{self.config.mcmc_iterations}: "
                      f"Quality={current_quality:.3f}, Best={best_quality:.3f}, "
                      f"Acceptance={accepted_proposals/(iteration+1):.2%}")
        
        final_avg_quality = np.mean(quality_history) if quality_history else best_quality
        print(f"✅ MCMC optimization complete!")
        print(f"   Final quality: {final_avg_quality:.3f}")
        print(f"   Best quality: {best_quality:.3f}")
        print(f"   Acceptance rate: {accepted_proposals/self.config.mcmc_iterations:.2%}")
        
        return best_sequence
    
    def get_transition_probability(self, from_chord: Tuple[int, ...], 
                                 to_chord: Tuple[int, ...]) -> float:
        """Get transition probability between chords."""
        if from_chord in self.chord_model and to_chord in self.chord_model[from_chord]:
            return self.chord_model[from_chord][to_chord]
        return 0.001  # Small probability for unseen transitions
    
    def generate_initial_sequence(self, length: int) -> List[Tuple[int, ...]]:
        """Generate initial chord sequence using basic model."""
        # Choose starting chord
        chord_popularity = {}
        for chord, transitions in self.chord_model.items():
            chord_popularity[chord] = sum(transitions.values())
        
        sorted_chords = sorted(chord_popularity.items(), key=lambda x: x[1], reverse=True)
        top_chords = sorted_chords[:max(1, len(sorted_chords) // 5)]
        
        chords = [chord for chord, weight in top_chords]
        weights = [weight for chord, weight in top_chords]
        total_weight = sum(weights)
        probabilities = [w / total_weight for w in weights]
        
        start_chord = chords[np.random.choice(len(chords), p=probabilities)]
        
        # Generate sequence
        sequence = [start_chord]
        current_chord = start_chord
        
        for _ in range(length - 1):
            next_chord = self.propose_chord_transition(current_chord)
            sequence.append(next_chord)
            current_chord = next_chord
        
        return sequence
    
    def create_midi_file(self, output_path: str = "mcmc_generated_song.mid"):
        """Generate and save MIDI file using MCMC optimization with proper rhythm."""
        print(f"🎼 Generating MIDI file with MCMC: {output_path}")
        
        # Calculate song structure
        total_duration = self.config.target_duration_minutes * 60
        bar_duration = (self.config.time_signature[0] * 60) / self.config.bpm
        total_bars = int(total_duration / bar_duration)
        
        print(f"📊 Song structure: {total_bars} bars, {total_duration/60:.1f} minutes")
        
        # Generate initial chord progression
        initial_sequence = self.generate_initial_sequence(total_bars)
        
        # Determine target key
        target_key = None
        if self.config.force_key:
            target_key = self.config.force_key
        elif self.config.use_key_quantization:
            # Auto-detect key from initial sequence
            all_notes = []
            for chord in initial_sequence:
                all_notes.extend([note % 12 for note in chord])
            target_key = self.detect_key_from_notes(all_notes)
            print(f"🎹 Auto-detected key: {target_key}")
        
        # MCMC optimization
        optimized_sequence = self.mcmc_optimize_sequence(initial_sequence, target_key)
        
        # Generate sophisticated rhythm (restored from original!)
        print("🥁 Generating sophisticated rhythm patterns...")
        rhythm_events = self.rhythm_generator.generate_rhythm_for_bars(total_bars)
        print(f"Generated {len(rhythm_events)} rhythmic events with varied durations")
        
        # Create MIDI file
        midi = pretty_midi.PrettyMIDI(initial_tempo=self.config.bpm)
        piano = pretty_midi.Instrument(program=0, name="MCMC Generated Piano")
        
        # Map rhythm events to optimized chords
        for i, (start_time, duration) in enumerate(rhythm_events):
            # Use chord from optimized sequence (cycle if needed)
            chord_index = i % len(optimized_sequence)
            chord_signature = optimized_sequence[chord_index]
            
            # Convert chord to notes
            chord_notes = self.intervals_to_notes(chord_signature)
            
            # Generate additional melody notes using note model
            melody_notes = self.generate_melody_notes(chord_notes, chord_signature)
            all_notes = list(set(chord_notes + melody_notes))[:self.config.max_polyphony]
            
            # Apply key quantization if enabled
            if target_key:
                all_notes = self.quantize_to_key(all_notes, target_key)
            
            # Create MIDI notes with the varied rhythm durations
            for note_pitch in all_notes:
                note_pitch = max(21, min(108, note_pitch))
                velocity = random.randint(*self.config.velocity_range)
                
                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=note_pitch,
                    start=start_time,
                    end=start_time + duration * 0.95  # Use actual rhythm duration!
                )
                piano.notes.append(note)
        
        midi.instruments.append(piano)
        midi.write(output_path)
        
        # Calculate actual duration and rhythm stats
        actual_duration = rhythm_events[-1][0] + rhythm_events[-1][1] if rhythm_events else 0
        durations = [duration for _, duration in rhythm_events]
        unique_durations = len(set([round(d, 2) for d in durations]))
        
        # Print generation summary
        print(f"\n🎵 Generated MCMC MIDI file: {output_path}")
        print(f"📊 Statistics:")
        print(f"   ⏱️  Duration: {actual_duration/60:.2f} minutes")
        print(f"   🎼 Total notes: {len(piano.notes)}")
        print(f"   🎭 Optimized chord progressions: {len(optimized_sequence)}")
        print(f"   🥁 Rhythmic events: {len(rhythm_events)}")
        print(f"   🎵 Unique note durations: {unique_durations}")
        print(f"   🎯 Target key: {target_key or 'Free (no quantization)'}")
        print(f"   🎚️  MCMC iterations: {self.config.mcmc_iterations}")
        print(f"   🌡️  Temperature: {self.config.temperature}")
        print(f"   💡 Rhythm complexity: FULL (patterns, rests, varied durations)")
        
        return output_path
    
    def detect_key_from_notes(self, notes: List[int]) -> str:
        """Auto-detect key from note list."""
        if not notes:
            return "C major"
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note_counts = Counter(notes)
        
        best_key = "C major"
        best_score = 0
        
        major_template = [0, 2, 4, 5, 7, 9, 11]
        minor_template = [0, 2, 3, 5, 7, 8, 10]
        
        for root in range(12):
            # Test major
            major_notes = {(root + interval) % 12 for interval in major_template}
            major_score = sum(count for note, count in note_counts.items() if note in major_notes)
            
            if major_score > best_score:
                best_score = major_score
                best_key = f"{note_names[root]} major"
            
            # Test minor
            minor_notes = {(root + interval) % 12 for interval in minor_template}
            minor_score = sum(count for note, count in note_counts.items() if note in minor_notes)
            
            if minor_score > best_score:
                best_score = minor_score
                best_key = f"{note_names[root]} minor"
        
        return best_key
    
    def intervals_to_notes(self, chord_signature: Tuple[int, ...], base_octave: int = 4) -> List[int]:
        """Convert chord intervals to MIDI notes."""
        base_note = base_octave * 12 + 60  # Middle C area
        root_variation = random.randint(-12, 12)
        root_note = base_note + root_variation
        
        notes = []
        for interval in chord_signature:
            note = root_note + interval
            while note < 21:
                note += 12
            while note > 108:
                note -= 12
            notes.append(note)
        
        return notes
    
    def generate_melody_notes(self, chord_notes: List[int], 
                            chord_signature: Tuple[int, ...]) -> List[int]:
        """Generate melody notes using note model."""
        melody_notes = []
        
        for chord_note in chord_notes:
            context = (chord_note, chord_signature)
            
            if context in self.note_model:
                possible_notes = list(self.note_model[context].keys())
                probabilities = list(self.note_model[context].values())
                
                probabilities = np.array(probabilities)
                probabilities /= probabilities.sum()
                
                num_additional = min(random.randint(0, 2), 
                                   self.config.max_polyphony - len(chord_notes))
                
                for _ in range(num_additional):
                    if possible_notes:
                        chosen_index = np.random.choice(len(possible_notes), p=probabilities)
                        additional_note = possible_notes[chosen_index]
                        if additional_note not in chord_notes + melody_notes:
                            melody_notes.append(additional_note)
        
        return melody_notes
    
    def quantize_to_key(self, notes: List[int], key: str) -> List[int]:
        """Quantize notes to specified key."""
        # Simple key quantization implementation
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        if 'major' in key.lower():
            root_name = key.split()[0]
            scale_template = [0, 2, 4, 5, 7, 9, 11]
        elif 'minor' in key.lower():
            root_name = key.split()[0]
            scale_template = [0, 2, 3, 5, 7, 8, 10]
        else:
            return notes  # Unknown key format
        
        try:
            root = note_names.index(root_name)
        except ValueError:
            return notes  # Invalid root note
        
        scale_notes = {(root + interval) % 12 for interval in scale_template}
        
        quantized = []
        for note in notes:
            note_class = note % 12
            octave = note // 12
            
            if note_class in scale_notes:
                quantized.append(note)
            else:
                # Find nearest scale note
                distances = [(abs(note_class - scale_note) % 12, scale_note) 
                           for scale_note in scale_notes]
                distances.extend([(12 - (abs(note_class - scale_note) % 12), scale_note) 
                                for scale_note in scale_notes])
                
                _, nearest_note = min(distances)
                quantized.append(octave * 12 + nearest_note)
        
        return quantized


def main():
    """Main function with enhanced MCMC command line interface."""
    parser = argparse.ArgumentParser(
        description="Generate MIDI using MCMC-enhanced Markov chain models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MCMC Parameters:
  The MCMC generator uses advanced sampling techniques to create higher-quality
  compositions by optimizing for musical coherence, harmonic consistency, and
  structural balance. Now includes full rhythm complexity from the original.

Examples:
  %(prog)s --quick                                    # Fast MCMC generation
  %(prog)s --output song.mid --key "D minor"         # Specific key
  %(prog)s --mcmc_iterations 2000 --temperature 1.5  # Custom MCMC settings
  %(prog)s --quality_weight 0.9 --enforce_key        # High quality mode
        """
    )
    
    # Basic parameters
    parser.add_argument("--models_dir", default="markov_analysis_output", 
                       help="Directory containing model files")
    parser.add_argument("--output", default="mcmc_generated_song.mid", 
                       help="Output MIDI filename")
    parser.add_argument("--duration", type=float, default=5.5, 
                       help="Song duration in minutes")
    parser.add_argument("--bpm", type=int, default=120, 
                       help="Beats per minute")
    
    # Key and musical parameters
    parser.add_argument("--key", type=str, 
                       help="Force specific key (e.g., 'C major', 'A minor')")
    parser.add_argument("--quantize_key", action="store_true", 
                       help="Auto-detect and quantize to key")
    parser.add_argument("--max_polyphony", type=int, default=6, 
                       help="Maximum simultaneous notes")
    
    # MCMC-specific parameters
    parser.add_argument("--mcmc_iterations", type=int, default=1000, 
                       help="Number of MCMC iterations (default: 1000)")
    parser.add_argument("--burn_in", type=int, default=100, 
                       help="MCMC burn-in period (default: 100)")
    parser.add_argument("--temperature", type=float, default=1.0, 
                       help="MCMC temperature parameter (default: 1.0)")
    parser.add_argument("--quality_weight", type=float, default=0.7, 
                       help="Weight of quality vs. transitions (0-1, default: 0.7)")
    
    # Quality function weights
    parser.add_argument("--harmonic_weight", type=float, default=0.3, 
                       help="Weight of harmonic consistency (default: 0.3)")
    parser.add_argument("--melodic_weight", type=float, default=0.2, 
                       help="Weight of melodic smoothness (default: 0.2)")
    parser.add_argument("--rhythmic_weight", type=float, default=0.2, 
                       help="Weight of rhythmic interest (default: 0.2)")
    parser.add_argument("--coherence_weight", type=float, default=0.3, 
                       help="Weight of overall coherence (default: 0.3)")
    
    # Constraint parameters
    parser.add_argument("--enforce_key", action="store_true", 
                       help="Enforce strict key adherence")
    parser.add_argument("--maintain_voice_leading", action="store_true", 
                       help="Maintain smooth voice leading")
    parser.add_argument("--quick", action="store_true", 
                       help="Quick generation with reduced MCMC iterations")
    
    args = parser.parse_args()
    
    # Setup paths
    models_dir = Path(args.models_dir)
    chord_model_path = models_dir / "chord_transitions.pkl"
    note_model_path = models_dir / "note_transitions.pkl"
    
    # Check model files
    if not chord_model_path.exists():
        print(f"❌ Chord model not found: {chord_model_path}")
        print("Make sure you've run the analysis first!")
        return
    
    if not note_model_path.exists():
        print(f"❌ Note model not found: {note_model_path}")
        print("Make sure you've run the analysis first!")
        return
    
    # Create MCMC configuration
    config = MCMCConfig(
        target_duration_minutes=args.duration,
        bpm=args.bpm,
        mcmc_iterations=500 if args.quick else args.mcmc_iterations,
        burn_in_period=50 if args.quick else args.burn_in,
        temperature=args.temperature,
        quality_weight=args.quality_weight,
        harmonic_weight=args.harmonic_weight,
        melodic_weight=args.melodic_weight,
        rhythmic_weight=args.rhythmic_weight,
        coherence_weight=args.coherence_weight,
        enforce_key=args.enforce_key or args.key is not None,
        maintain_voice_leading=args.maintain_voice_leading,
        use_key_quantization=args.quantize_key,
        force_key=args.key,
        max_polyphony=args.max_polyphony
    )
    
    print("🎼 Starting MCMC MIDI generation...")
    print(f"Configuration: {args.duration} minutes at {args.bpm} BPM")
    print(f"MCMC Settings: {config.mcmc_iterations} iterations, temperature={config.temperature}")
    print("🥁 Rhythm: FULL complexity (patterns, rests, varied durations)")
    if args.key:
        print(f"Forced key: {args.key}")
    elif args.quantize_key:
        print("Key quantization: Auto-detect")
    else:
        print("Key quantization: Disabled")
    
    try:
        generator = MCMCMIDIGenerator(
            str(chord_model_path), 
            str(note_model_path), 
            config
        )
        
        output_path = generator.create_midi_file(args.output)
        print(f"\n✅ Success! Generated MCMC-enhanced MIDI: {output_path}")
        print(f"🎧 This file combines MCMC harmonic optimization with full rhythm complexity!")
        print(f"💡 Quality weight: {config.quality_weight:.1%} (higher = more optimization)")
        
    except Exception as e:
        print(f"❌ Error during MCMC generation: {e}")
        raise


if __name__ == "__main__":
    main()
