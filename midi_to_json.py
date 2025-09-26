#!/usr/bin/env python3
"""
MIDI to JSON Converter
Converts MIDI files to structured JSON format for analysis and sharing.
"""

import os
import json
import warnings
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
import pretty_midi
import numpy as np
from tqdm import tqdm
import time

# Suppress pretty_midi warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pretty_midi")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pretty_midi")


def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    return obj


class MIDIAnalyzer:
    """Analyze and convert MIDI files to structured JSON."""
    
    def __init__(self):
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def midi_note_to_name(self, midi_note: int) -> str:
        """Convert MIDI note number to note name with octave."""
        octave = (midi_note // 12) - 1
        note_name = self.note_names[midi_note % 12]
        return f"{note_name}{octave}"
    
    def detect_key_signature(self, notes: List[int]) -> Dict[str, Any]:
        """Simple key detection based on note frequency."""
        if not notes:
            return {"key": "Unknown", "confidence": 0.0}
        
        # Count note classes (mod 12)
        note_counts = Counter(note % 12 for note in notes)
        total_notes = sum(note_counts.values())
        
        # Major and minor scale templates
        major_template = [0, 2, 4, 5, 7, 9, 11]  # Major scale intervals
        minor_template = [0, 2, 3, 5, 7, 8, 10]  # Natural minor scale intervals
        
        best_key = "C major"
        best_score = 0
        
        # Test all 12 major and minor keys
        for root in range(12):
            # Test major
            major_notes = {(root + interval) % 12 for interval in major_template}
            major_score = sum(note_counts[note] for note in major_notes)
            
            if major_score > best_score:
                best_score = major_score
                best_key = f"{self.note_names[root]} major"
            
            # Test minor
            minor_notes = {(root + interval) % 12 for interval in minor_template}
            minor_score = sum(note_counts[note] for note in minor_notes)
            
            if minor_score > best_score:
                best_score = minor_score
                best_key = f"{self.note_names[root]} minor"
        
        confidence = best_score / total_notes if total_notes > 0 else 0
        
        return {
            "key": best_key,
            "confidence": round(float(confidence), 3),
            "note_distribution": {self.note_names[note]: int(count) 
                                for note, count in note_counts.most_common()}
        }
    
    def extract_chords(self, notes: List[Dict], time_window: float = 0.1) -> List[Dict]:
        """Extract chord events from notes."""
        if not notes:
            return []
        
        # Sort notes by start time
        sorted_notes = sorted(notes, key=lambda x: x['start'])
        
        chords = []
        current_chord = []
        current_time = None
        
        for note in sorted_notes:
            start_time = note['start']
            
            if current_time is None or abs(start_time - current_time) <= time_window:
                # Add to current chord
                current_chord.append(note)
                if current_time is None:
                    current_time = start_time
            else:
                # Save current chord and start new one
                if len(current_chord) >= 2:  # Only save actual chords (2+ notes)
                    chord_pitches = [n['pitch'] for n in current_chord]
                    chord_names = [n['note_name'] for n in current_chord]
                    
                    chords.append({
                        "start": round(float(current_time), 3),
                        "duration": round(float(max(n['end'] for n in current_chord) - current_time), 3),
                        "pitches": sorted([int(p) for p in chord_pitches]),
                        "note_names": sorted(chord_names),
                        "note_count": int(len(current_chord)),
                        "root_note": min(chord_names),
                        "intervals": [int(i) for i in self.get_chord_intervals(chord_pitches)]
                    })
                
                # Start new chord
                current_chord = [note]
                current_time = start_time
        
        # Don't forget the last chord
        if len(current_chord) >= 2:
            chord_pitches = [n['pitch'] for n in current_chord]
            chord_names = [n['note_name'] for n in current_chord]
            
            chords.append({
                "start": round(float(current_time), 3),
                "duration": round(float(max(n['end'] for n in current_chord) - current_time), 3),
                "pitches": sorted([int(p) for p in chord_pitches]),
                "note_names": sorted(chord_names),
                "note_count": int(len(current_chord)),
                "root_note": min(chord_names),
                "intervals": [int(i) for i in self.get_chord_intervals(chord_pitches)]
            })
        
        return chords
    
    def get_chord_intervals(self, pitches: List[int]) -> List[int]:
        """Get interval structure of a chord."""
        if not pitches:
            return []
        
        sorted_pitches = sorted(pitches)
        root = sorted_pitches[0]
        return [pitch - root for pitch in sorted_pitches]
    
    def analyze_rhythm(self, notes: List[Dict]) -> Dict[str, Any]:
        """Analyze rhythmic patterns."""
        if not notes:
            return {"note_durations": [], "most_common_durations": []}
        
        durations = [note['duration'] for note in notes]
        duration_counter = Counter(round(d, 3) for d in durations)
        
        # Convert to beats (assuming 120 BPM, 4/4 time)
        beat_duration = 0.5  # 120 BPM = 0.5 seconds per beat
        beat_durations = [d / beat_duration for d in durations]
        
        return {
            "average_duration": round(float(np.mean(durations)), 3),
            "duration_range": [round(float(min(durations)), 3), round(float(max(durations)), 3)],
            "most_common_durations": [
                {"duration": float(dur), "count": int(count), "beats": round(float(dur / beat_duration), 2)}
                for dur, count in duration_counter.most_common(5)
            ],
            "total_notes": int(len(notes)),
            "rhythm_density": round(float(len(notes) / max(n['end'] for n in notes)) if notes else 0, 2)
        }
    
    def convert_midi_to_json(self, midi_path: str) -> Dict[str, Any]:
        """Convert a single MIDI file to JSON structure."""
        try:
            # Load MIDI file
            midi_data = pretty_midi.PrettyMIDI(midi_path)
            
            # Basic file information
            file_info = {
                "filename": os.path.basename(midi_path),
                "file_path": midi_path,
                "file_size_mb": round(float(os.path.getsize(midi_path) / (1024 * 1024)), 3),
                "duration": round(float(midi_data.get_end_time()), 3),
                "tempo_changes": [
                    {"time": float(change[0]), "tempo": round(float(change[1]), 1)}
                    for change in zip(midi_data.get_tempo_changes()[0], midi_data.get_tempo_changes()[1])
                ] if len(midi_data.get_tempo_changes()[0]) > 0 else [{"time": 0.0, "tempo": 120.0}]
            }
            
            # Extract all notes from all instruments
            all_notes = []
            instruments_info = []
            
            for i, instrument in enumerate(midi_data.instruments):
                if instrument.is_drum:
                    continue  # Skip drum tracks for now
                
                instrument_notes = []
                for note in instrument.notes:
                    note_data = {
                        "pitch": int(note.pitch),
                        "note_name": self.midi_note_to_name(note.pitch),
                        "start": round(float(note.start), 3),
                        "end": round(float(note.end), 3),
                        "duration": round(float(note.end - note.start), 3),
                        "velocity": int(note.velocity)
                    }
                    instrument_notes.append(note_data)
                    all_notes.append(note_data)
                
                instruments_info.append({
                    "index": int(i),
                    "name": instrument.name or f"Instrument {i}",
                    "program": int(instrument.program),
                    "is_drum": bool(instrument.is_drum),
                    "note_count": int(len(instrument_notes)),
                    "pitch_range": [
                        int(min(n['pitch'] for n in instrument_notes)),
                        int(max(n['pitch'] for n in instrument_notes))
                    ] if instrument_notes else [0, 0],
                    "time_range": [
                        float(min(n['start'] for n in instrument_notes)),
                        float(max(n['end'] for n in instrument_notes))
                    ] if instrument_notes else [0.0, 0.0]
                })
            
            # Sort all notes by start time
            all_notes.sort(key=lambda x: x['start'])
            
            # Musical analysis
            all_pitches = [note['pitch'] for note in all_notes]
            key_analysis = self.detect_key_signature(all_pitches)
            rhythm_analysis = self.analyze_rhythm(all_notes)
            chord_analysis = self.extract_chords(all_notes)
            
            # Statistics
            statistics = {
                "total_notes": int(len(all_notes)),
                "total_instruments": int(len([i for i in midi_data.instruments if not i.is_drum])),
                "total_drum_tracks": int(len([i for i in midi_data.instruments if i.is_drum])),
                "pitch_range": [int(min(all_pitches)), int(max(all_pitches))] if all_pitches else [0, 0],
                "pitch_range_names": [
                    self.midi_note_to_name(min(all_pitches)),
                    self.midi_note_to_name(max(all_pitches))
                ] if all_pitches else ["", ""],
                "velocity_range": [
                    int(min(n['velocity'] for n in all_notes)),
                    int(max(n['velocity'] for n in all_notes))
                ] if all_notes else [0, 0],
                "polyphony_analysis": self.analyze_polyphony(all_notes),
                "chord_count": int(len(chord_analysis))
            }
            
            # Compile final JSON structure
            result = {
                "file_info": file_info,
                "statistics": statistics,
                "key_analysis": key_analysis,
                "rhythm_analysis": rhythm_analysis,
                "instruments": instruments_info,
                "chords": chord_analysis[:50],  # Limit to first 50 chords to avoid huge files
                "note_sequence": all_notes[:200],  # Limit to first 200 notes
                "analysis_metadata": {
                    "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "analyzer_version": "1.1",
                    "notes_truncated": bool(len(all_notes) > 200),
                    "chords_trucated": bool(len(chord_analysis) > 50),
                    "total_notes_in_file": int(len(all_notes)),
                    "total_chords_in_file": int(len(chord_analysis))
                }
            }
            
            return result
            
        except Exception as e:
            return {
                "error": True,
                "filename": os.path.basename(midi_path),
                "error_message": str(e),
                "file_path": midi_path
            }
    
    def analyze_polyphony(self, notes: List[Dict]) -> Dict[str, Any]:
        """Analyze how many notes are playing simultaneously."""
        if not notes:
            return {"max_polyphony": 0, "average_polyphony": 0.0}
        
        # Create time points for analysis
        time_points = []
        for note in notes:
            time_points.append((note['start'], 'start'))
            time_points.append((note['end'], 'end'))
        
        time_points.sort()
        
        current_polyphony = 0
        max_polyphony = 0
        polyphony_samples = []
        
        for time_point, event_type in time_points:
            if event_type == 'start':
                current_polyphony += 1
            else:
                current_polyphony -= 1
            
            max_polyphony = max(max_polyphony, current_polyphony)
            polyphony_samples.append(current_polyphony)
        
        avg_polyphony = float(np.mean(polyphony_samples)) if polyphony_samples else 0.0
        
        return {
            "max_polyphony": int(max_polyphony),
            "average_polyphony": round(avg_polyphony, 2)
        }


def find_midi_files(path: str) -> List[str]:
    """Find all MIDI files in a path (file or directory)."""
    midi_extensions = {'.mid', '.midi', '.MID', '.MIDI'}
    
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    
    if path_obj.is_file():
        if path_obj.suffix in midi_extensions:
            return [str(path_obj)]
        else:
            raise ValueError(f"File is not a MIDI file: {path}")
    
    # Directory - find all MIDI files
    midi_files = []
    for file_path in path_obj.rglob('*'):
        if file_path.suffix in midi_extensions:
            midi_files.append(str(file_path))
    
    if not midi_files:
        raise ValueError(f"No MIDI files found in directory: {path}")
    
    return sorted(midi_files)


def process_midi_files(input_path: str, output_path: str = None) -> str:
    """Process MIDI file(s) and save as JSON."""
    print(f"🎵 Searching for MIDI files in: {input_path}")
    
    # Find MIDI files
    midi_files = find_midi_files(input_path)
    
    print(f"📁 Found {len(midi_files)} MIDI file(s)")
    
    # Initialize analyzer
    analyzer = MIDIAnalyzer()
    
    # Process files
    results = []
    successful = 0
    failed = 0
    
    with tqdm(total=len(midi_files), desc="Converting MIDI files") as pbar:
        for midi_file in midi_files:
            result = analyzer.convert_midi_to_json(midi_file)
            results.append(result)
            
            if result.get('error'):
                failed += 1
                pbar.set_postfix_str(f"✅ {successful} ❌ {failed}")
            else:
                successful += 1
                pbar.set_postfix_str(f"✅ {successful} ❌ {failed}")
            
            pbar.update(1)
    
    # Determine output path
    if output_path is None:
        if len(midi_files) == 1:
            base_name = Path(midi_files[0]).stem
            output_path = f"{base_name}_analysis.json"
        else:
            output_path = "midi_batch_analysis.json"
    
    # Create final output structure and convert numpy types
    output_data = {
        "analysis_summary": {
            "total_files": int(len(midi_files)),
            "successful_conversions": int(successful),
            "failed_conversions": int(failed),
            "success_rate": round(float(successful / len(midi_files) * 100), 1) if midi_files else 0.0,
            "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_path": input_path,
            "is_batch": bool(len(midi_files) > 1)
        },
        "files": results
    }
    
    # Convert all numpy types to native Python types
    output_data = convert_numpy_types(output_data)
    
    # Save JSON file
    print(f"\n💾 Saving analysis to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n{'='*60}")
    print("🎼 MIDI TO JSON CONVERSION COMPLETE!")
    print(f"{'='*60}")
    print(f"✅ Files successfully converted: {successful}")
    print(f"❌ Files failed: {failed}")
    print(f"📈 Success rate: {output_data['analysis_summary']['success_rate']}%")
    print(f"📁 Output saved to: {output_path}")
    
    if successful > 0:
        # Calculate total file size
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)
        print(f"📊 JSON file size: {file_size_mb:.2f} MB")
        
        # Show some quick stats from first successful file
        first_success = next((r for r in results if not r.get('error')), None)
        if first_success:
            stats = first_success['statistics']
            print(f"\n🎵 Sample from first file:")
            print(f"   📝 Notes: {stats['total_notes']}")
            print(f"   🎼 Instruments: {stats['total_instruments']}")
            print(f"   🎹 Key: {first_success['key_analysis']['key']}")
            print(f"   ⏱️  Duration: {first_success['file_info']['duration']} seconds")
    
    print(f"\n🎉 Analysis complete! You can now share '{output_path}' for musical analysis.")
    
    return output_path


def main():
    """Main function with user interaction."""
    print("🎼 MIDI to JSON Converter")
    print("=" * 50)
    print("Convert MIDI files to structured JSON for analysis and sharing")
    
    # Get input path from user
    while True:
        input_path = input("\n📁 Enter path to MIDI file or directory: ").strip()
        # Remove quotes if present
        input_path = input_path.strip("'\"")
        
        if os.path.exists(input_path):
            break
        else:
            print(f"❌ Path not found: {input_path}")
            print("Please enter a valid file or directory path.")
    
    # Optional: Ask for output filename
    print(f"\n📤 Output options:")
    print("   1. Auto-generate filename (recommended)")
    print("   2. Specify custom filename")
    
    output_choice = input("Choose output option (1/2) [1]: ").strip()
    
    output_path = None
    if output_choice == "2":
        output_path = input("Enter output JSON filename: ").strip()
        if not output_path.endswith('.json'):
            output_path += '.json'
    
    try:
        # Process the files
        print(f"\n🚀 Starting conversion of: {input_path}")
        result_path = process_midi_files(input_path, output_path)
        
        # Ask if user wants to see a preview
        preview = input(f"\n👀 Would you like to see a preview of the JSON structure? (y/N): ").strip().lower()
        if preview in ['y', 'yes']:
            print("\n📋 JSON Structure Preview:")
            print("-" * 40)
            
            with open(result_path, 'r') as f:
                data = json.load(f)
            
            # Show summary
            summary = data['analysis_summary']
            print(f"Analysis Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            
            # Show first file structure (if exists)
            if data['files'] and not data['files'][0].get('error'):
                first_file = data['files'][0]
                print(f"\nFirst File Structure:")
                print(f"  Filename: {first_file['file_info']['filename']}")
                print(f"  Duration: {first_file['file_info']['duration']} seconds")
                print(f"  Key: {first_file['key_analysis']['key']}")
                print(f"  Total Notes: {first_file['statistics']['total_notes']}")
                print(f"  Chord Count: {first_file['statistics']['chord_count']}")
                
                if first_file.get('chords'):
                    print(f"  First Chord: {first_file['chords'][0]['note_names']} (intervals: {first_file['chords'][0]['intervals']})")
        
    except Exception as e:
        print(f"\n❌ Error during conversion: {str(e)}")
        raise


if __name__ == "__main__":
    main()
