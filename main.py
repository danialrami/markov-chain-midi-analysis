#!/usr/bin/env python3
"""
MIDI Polyphonic Markov Chain Analyzer
Implements Approach 1: Chord-Context Transitions

Analyzes MIDI files to create:
1. Chord-to-chord transition probabilities
2. Note-in-context transition probabilities
"""

import os
import gc
import json
import pickle
import warnings
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Set, Optional
import time

# Suppress deprecation warnings from pkg_resources in pretty_midi
warnings.filterwarnings("ignore", category=UserWarning, module="pretty_midi")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pretty_midi")

import pretty_midi
from tqdm import tqdm


class ErrorTracker:
    """Track and categorize MIDI processing errors."""
    
    def __init__(self):
        self.error_categories = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.total_errors = 0
        
    def add_error(self, file_path: str, error_msg: str):
        """Categorize and track errors."""
        self.total_errors += 1
        
        # Categorize common error types
        if "MThd not found" in error_msg:
            category = "not_midi_file"
        elif "data byte must be in range" in error_msg:
            category = "corrupt_data_bytes"
        elif "Could not decode key" in error_msg:
            category = "invalid_key_signature"
        elif "largest tick" in error_msg and "corrupt" in error_msg:
            category = "corrupt_timing"
        elif "list index out of range" in error_msg:
            category = "parsing_error"
        elif not error_msg.strip():
            category = "general_parsing_failure"
        else:
            category = "other"
            
        self.error_counts[category] += 1
        
        # Only store first few examples of each error type to save memory
        if len(self.error_categories[category]) < 3:
            self.error_categories[category].append({
                'file': os.path.basename(file_path),
                'error': error_msg.strip() or "Unknown error"
            })
    
    def get_summary(self):
        """Get a summary of all errors encountered."""
        return {
            'total_errors': self.total_errors,
            'error_counts': dict(self.error_counts),
            'examples': {k: v for k, v in self.error_categories.items()}
        }


class PolyphonicMarkovAnalyzer:
    def __init__(self, chord_time_window=0.1, min_chord_size=1, velocity_threshold=30, strict_mode=False):
        """
        Initialize the analyzer with configurable parameters.
        
        Args:
            chord_time_window: Max time gap between notes to be considered part of same chord (seconds)
            min_chord_size: Minimum number of notes to constitute a chord
            velocity_threshold: Minimum velocity to include a note
            strict_mode: If True, fail on any parsing errors. If False, skip bad files silently.
        """
        self.chord_time_window = chord_time_window
        self.min_chord_size = min_chord_size
        self.velocity_threshold = velocity_threshold
        self.strict_mode = strict_mode
        
        # Transition matrices
        self.chord_transitions = defaultdict(lambda: defaultdict(int))
        self.note_transitions = defaultdict(lambda: defaultdict(int))
        
        # Statistics tracking
        self.stats = {
            'files_processed': 0,
            'files_failed': 0,
            'files_skipped': 0,
            'total_chord_events': 0,
            'total_note_transitions': 0,
            'unique_chord_signatures': set(),
            'processing_start_time': None
        }
        
        # Error tracking
        self.error_tracker = ErrorTracker()
        
    def is_likely_midi_file(self, file_path: str) -> bool:
        """Quick validation to check if file is likely a valid MIDI file."""
        try:
            # Check file size (skip empty files and suspiciously large files)
            file_size = os.path.getsize(file_path)
            if file_size < 100 or file_size > 50_000_000:  # 50MB limit
                return False
                
            # Check if file starts with MIDI header
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header != b'MThd':
                    return False
                    
            return True
            
        except (OSError, IOError):
            return False
        
    def extract_chord_signature(self, notes: List[int]) -> Optional[Tuple[int, ...]]:
        """Convert absolute MIDI notes to interval structure (chord signature)."""
        if not notes or len(notes) < self.min_chord_size:
            return None
        
        # Sort notes and convert to intervals from root
        sorted_notes = sorted(set(notes))  # Remove duplicates and sort
        root = sorted_notes[0]
        intervals = tuple(note - root for note in sorted_notes)
        
        return intervals
    
    def extract_chords_from_midi(self, file_path: str) -> List[Tuple[float, List[int]]]:
        """Extract chord sequence from MIDI file with robust error handling."""
        try:
            # Quick validation first
            if not self.is_likely_midi_file(file_path):
                self.error_tracker.add_error(file_path, "Not a valid MIDI file (pre-validation)")
                self.stats['files_skipped'] += 1
                return []
            
            # Attempt to parse MIDI file
            midi_data = pretty_midi.PrettyMIDI(file_path)
            
            # Quick sanity checks
            if not midi_data.instruments:
                self.error_tracker.add_error(file_path, "No instruments found")
                self.stats['files_skipped'] += 1
                return []
            
            # Combine all notes from all non-drum instruments
            all_notes = []
            for instrument in midi_data.instruments:
                if not instrument.is_drum:  # Skip drum tracks
                    for note in instrument.notes:
                        # Validate note data
                        if (0 <= note.pitch <= 127 and 
                            note.velocity >= self.velocity_threshold and
                            note.start >= 0 and note.end > note.start):
                            all_notes.append((note.start, note.end, note.pitch, note.velocity))
            
            if not all_notes:
                # Don't count this as an error - just an empty file
                self.stats['files_skipped'] += 1
                return []
            
            # Sort by start time
            all_notes.sort(key=lambda x: x[0])
            
            # Group notes into chords based on time windows
            chords = []
            current_chord_notes = []
            current_chord_time = None
            
            for start_time, end_time, pitch, velocity in all_notes:
                # If this is the first note or it's within the time window of current chord
                if (current_chord_time is None or 
                    abs(start_time - current_chord_time) <= self.chord_time_window):
                    
                    current_chord_notes.append(pitch)
                    if current_chord_time is None:
                        current_chord_time = start_time
                else:
                    # Save previous chord if it meets minimum size
                    if len(current_chord_notes) >= self.min_chord_size:
                        chords.append((current_chord_time, current_chord_notes))
                    
                    # Start new chord
                    current_chord_notes = [pitch]
                    current_chord_time = start_time
            
            # Don't forget the last chord
            if len(current_chord_notes) >= self.min_chord_size:
                chords.append((current_chord_time, current_chord_notes))
            
            return chords
            
        except Exception as e:
            error_msg = str(e)
            self.error_tracker.add_error(file_path, error_msg)
            self.stats['files_failed'] += 1
            
            # In strict mode, print individual errors
            if self.strict_mode:
                print(f"Error processing {os.path.basename(file_path)}: {error_msg}")
            
            return []
    
    def add_chord_sequence(self, chord_sequence: List[Tuple[float, List[int]]]):
        """Add a chord sequence to the analysis."""
        if len(chord_sequence) < 2:
            return
        
        self.stats['total_chord_events'] += len(chord_sequence)
        
        for i in range(len(chord_sequence) - 1):
            _, curr_notes = chord_sequence[i]
            _, next_notes = chord_sequence[i + 1]
            
            curr_sig = self.extract_chord_signature(curr_notes)
            next_sig = self.extract_chord_signature(next_notes)
            
            if curr_sig is None or next_sig is None:
                continue
            
            # Track unique chord signatures
            self.stats['unique_chord_signatures'].add(curr_sig)
            self.stats['unique_chord_signatures'].add(next_sig)
            
            # Update chord-to-chord transitions
            self.chord_transitions[curr_sig][next_sig] += 1
            
            # Update note-in-context transitions
            for curr_note in curr_notes:
                for next_note in next_notes:
                    context = (curr_note, curr_sig)
                    self.note_transitions[context][next_note] += 1
                    self.stats['total_note_transitions'] += 1
    
    def calculate_probabilities(self):
        """Convert counts to probabilities."""
        print("Calculating probabilities...")
        
        # Convert chord transitions to probabilities
        chord_probs = {}
        for curr_chord, transitions in self.chord_transitions.items():
            total = sum(transitions.values())
            if total > 0:
                chord_probs[curr_chord] = {
                    next_chord: count / total 
                    for next_chord, count in transitions.items()
                }
        
        # Convert note transitions to probabilities  
        note_probs = {}
        for context, transitions in self.note_transitions.items():
            total = sum(transitions.values())
            if total > 0:
                note_probs[context] = {
                    next_note: count / total
                    for next_note, count in transitions.items()
                }
        
        return chord_probs, note_probs
    
    def get_statistics(self):
        """Get comprehensive statistics about the analysis."""
        processing_time = time.time() - self.stats['processing_start_time'] if self.stats['processing_start_time'] else 0
        
        stats = {
            'files_processed': self.stats['files_processed'],
            'files_failed': self.stats['files_failed'],
            'files_skipped': self.stats['files_skipped'],
            'total_chord_events': self.stats['total_chord_events'],
            'total_note_transitions': self.stats['total_note_transitions'],
            'unique_chord_signatures_count': len(self.stats['unique_chord_signatures']),
            'processing_time_seconds': processing_time,
            'chord_transition_types': len(self.chord_transitions),
            'note_transition_contexts': len(self.note_transitions),
            'error_summary': self.error_tracker.get_summary(),
            'parameters': {
                'chord_time_window': self.chord_time_window,
                'min_chord_size': self.min_chord_size,
                'velocity_threshold': self.velocity_threshold,
                'strict_mode': self.strict_mode
            }
        }
        
        return stats


def find_midi_files(directory_path: str) -> List[str]:
    """Recursively find all MIDI files in a directory."""
    midi_extensions = {'.mid', '.midi', '.MID', '.MIDI'}
    midi_files = []
    
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    if directory.is_file() and directory.suffix in midi_extensions:
        return [str(directory)]
    
    for file_path in directory.rglob('*'):
        if file_path.suffix in midi_extensions:
            midi_files.append(str(file_path))
    
    return midi_files


def process_dataset(midi_path: str, batch_size: int = 100, strict_mode: bool = False) -> Dict:
    """Process entire MIDI dataset with batch processing for memory efficiency."""
    print(f"Searching for MIDI files in: {midi_path}")
    
    # Find all MIDI files
    midi_files = find_midi_files(midi_path)
    
    if not midi_files:
        raise ValueError(f"No MIDI files found in: {midi_path}")
    
    print(f"Found {len(midi_files):,} MIDI files")
    print(f"Processing mode: {'Strict (show all errors)' if strict_mode else 'Lenient (suppress error details)'}")
    
    # Initialize analyzer
    analyzer = PolyphonicMarkovAnalyzer(strict_mode=strict_mode)
    analyzer.stats['processing_start_time'] = time.time()
    
    # Process files in batches
    successful_files = 0
    
    with tqdm(total=len(midi_files), desc="Processing MIDI files", 
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] Success: {postfix}') as pbar:
        
        for batch_start in range(0, len(midi_files), batch_size):
            batch_files = midi_files[batch_start:batch_start + batch_size]
            
            for file_path in batch_files:
                chord_sequence = analyzer.extract_chords_from_midi(file_path)
                if chord_sequence:
                    analyzer.add_chord_sequence(chord_sequence)
                    analyzer.stats['files_processed'] += 1
                    successful_files += 1
                
                # Update progress bar with success rate
                pbar.set_postfix_str(f"{successful_files}")
                pbar.update(1)
            
            # Garbage collection every batch to manage memory
            if batch_start % (batch_size * 5) == 0:
                gc.collect()
    
    print(f"\n🎵 Processing complete! Successfully analyzed {successful_files:,} files")
    print("📊 Calculating probabilities...")
    
    # Calculate final probabilities
    chord_probs, note_probs = analyzer.calculate_probabilities()
    
    # Get statistics
    stats = analyzer.get_statistics()
    
    return {
        'chord_transitions': chord_probs,
        'note_transitions': note_probs,
        'statistics': stats,
        'analyzer': analyzer  # Keep for potential further analysis
    }


def save_results(results: Dict, output_dir: str = "markov_analysis_output"):
    """Save analysis results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"\n💾 Saving results to: {output_path.absolute()}")
    
    # Save chord transitions
    with open(output_path / 'chord_transitions.pkl', 'wb') as f:
        pickle.dump(results['chord_transitions'], f)
    
    # Save note transitions (might be large)
    with open(output_path / 'note_transitions.pkl', 'wb') as f:
        pickle.dump(results['note_transitions'], f)
    
    # Save statistics as JSON
    stats = results['statistics'].copy()
    # Convert set to list for JSON serialization
    with open(output_path / 'analysis_statistics.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Save some example analyses
    chord_analysis = analyze_chord_patterns(results['chord_transitions'])
    with open(output_path / 'chord_analysis.json', 'w') as f:
        json.dump(chord_analysis, f, indent=2)
    
    # Save detailed error report
    with open(output_path / 'error_report.json', 'w') as f:
        json.dump(results['statistics']['error_summary'], f, indent=2)
    
    print("✅ Results saved successfully!")
    return output_path


def analyze_chord_patterns(chord_transitions: Dict) -> Dict:
    """Analyze patterns in chord transitions for insights."""
    if not chord_transitions:
        return {}
    
    # Find most common chords (by total outgoing transitions)
    chord_popularity = {}
    for chord, transitions in chord_transitions.items():
        chord_popularity[chord] = sum(transitions.values())
    
    most_common_chords = sorted(chord_popularity.items(), key=lambda x: x[1], reverse=True)[:20]
    
    # Find most stable chords (highest self-transition probability)
    stable_chords = []
    for chord, transitions in chord_transitions.items():
        if chord in transitions:
            self_prob = transitions[chord]
            stable_chords.append((chord, self_prob))
    
    stable_chords = sorted(stable_chords, key=lambda x: x[1], reverse=True)[:10]
    
    # Find most common transitions
    all_transitions = []
    for from_chord, transitions in chord_transitions.items():
        for to_chord, prob in transitions.items():
            all_transitions.append(((from_chord, to_chord), prob))
    
    most_common_transitions = sorted(all_transitions, key=lambda x: x[1], reverse=True)[:20]
    
    return {
        'most_common_chords': [{'chord': list(chord), 'count': count} for chord, count in most_common_chords],
        'most_stable_chords': [{'chord': list(chord), 'self_transition_prob': prob} for chord, prob in stable_chords],
        'most_common_transitions': [
            {'from_chord': list(from_chord), 'to_chord': list(to_chord), 'probability': prob}
            for (from_chord, to_chord), prob in most_common_transitions
        ]
    }


def print_error_summary(error_summary: Dict):
    """Print a nice summary of errors encountered."""
    if error_summary['total_errors'] == 0:
        print("🎉 No errors encountered!")
        return
    
    print(f"\n⚠️  Error Summary ({error_summary['total_errors']:,} total errors):")
    print("=" * 60)
    
    error_descriptions = {
        'not_midi_file': 'Files that are not valid MIDI format',
        'corrupt_data_bytes': 'Files with invalid MIDI data bytes',
        'invalid_key_signature': 'Files with malformed key signatures',
        'corrupt_timing': 'Files with corrupted timing information',
        'parsing_error': 'General parsing failures',
        'general_parsing_failure': 'Unknown parsing errors',
        'other': 'Other miscellaneous errors'
    }
    
    for error_type, count in error_summary['error_counts'].items():
        description = error_descriptions.get(error_type, error_type.replace('_', ' ').title())
        print(f"  📁 {description}: {count:,} files")
        
        # Show examples if available
        if error_type in error_summary['examples']:
            for example in error_summary['examples'][error_type][:2]:  # Show max 2 examples
                print(f"     └─ {example['file']}: {example['error'][:80]}{'...' if len(example['error']) > 80 else ''}")
    
    print("\n💡 This is normal for large MIDI collections - many files are corrupted or mislabeled.")


def main():
    """Main execution function."""
    print("🎼 MIDI Polyphonic Markov Chain Analyzer")
    print("=" * 50)
    
    # Ask user about processing mode
    print("\nProcessing mode options:")
    print("1. Lenient (default) - Skip bad files silently, faster processing")
    print("2. Strict - Show all error details, slower but more verbose")
    
    mode_choice = input("\nChoose mode (1/2) [default: 1]: ").strip()
    strict_mode = mode_choice == "2"
    
    # Get file path from user
    while True:
        filepath = input("\n📁 Enter the path to your MIDI file or directory: ").strip()
        # Remove quotes if present
        filepath = filepath.strip("'\"")
        
        if os.path.exists(filepath):
            break
        else:
            print(f"❌ Path not found: {filepath}")
            print("Please enter a valid file or directory path.")
    
    try:
        # Process the dataset
        print(f"\n🚀 Starting analysis of: {filepath}")
        results = process_dataset(filepath, strict_mode=strict_mode)
        
        # Print summary statistics
        stats = results['statistics']
        print(f"\n{'='*60}")
        print("📊 ANALYSIS COMPLETE!")
        print(f"{'='*60}")
        print(f"✅ Files successfully processed: {stats['files_processed']:,}")
        print(f"❌ Files failed/skipped: {stats['files_failed'] + stats['files_skipped']:,}")
        print(f"   ├─ Failed (errors): {stats['files_failed']:,}")
        print(f"   └─ Skipped (empty/invalid): {stats['files_skipped']:,}")
        
        success_rate = (stats['files_processed'] / (stats['files_processed'] + stats['files_failed'] + stats['files_skipped'])) * 100
        print(f"📈 Success rate: {success_rate:.1f}%")
        
        if stats['files_processed'] > 0:
            print(f"\n🎵 Musical Analysis Results:")
            print(f"   🎼 Total chord events: {stats['total_chord_events']:,}")
            print(f"   🔄 Total note transitions: {stats['total_note_transitions']:,}")
            print(f"   🎭 Unique chord types: {stats['unique_chord_signatures_count']:,}")
            print(f"   ⏱️  Processing time: {stats['processing_time_seconds']:.1f} seconds")
            print(f"   📊 Chord transition types: {stats['chord_transition_types']:,}")
            print(f"   🎯 Note context types: {stats['note_transition_contexts']:,}")
            
            # Print error summary
            print_error_summary(stats['error_summary'])
            
            # Save results
            output_path = save_results(results)
            
            print(f"\n{'='*60}")
            print("📁 FILES SAVED:")
            print(f"{'='*60}")
            print(f"🎼 Chord transitions: {output_path}/chord_transitions.pkl")
            print(f"🎵 Note transitions: {output_path}/note_transitions.pkl") 
            print(f"📊 Statistics: {output_path}/analysis_statistics.json")
            print(f"🎭 Pattern analysis: {output_path}/chord_analysis.json")
            print(f"⚠️  Error report: {output_path}/error_report.json")
            
            print(f"\n🎉 Analysis complete! Check the '{output_path.name}' directory for results.")
        else:
            print(f"\n❌ No valid MIDI files could be processed.")
            print("This could mean:")
            print("  • All files in the directory are corrupted or not MIDI files")
            print("  • The files use MIDI formats not supported by pretty_midi")  
            print("  • There's a systematic issue with file paths or permissions")
        
    except Exception as e:
        print(f"\n💥 Error during analysis: {str(e)}")
        raise


if __name__ == "__main__":
    main()
