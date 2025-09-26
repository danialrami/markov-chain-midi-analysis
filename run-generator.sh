#!/bin/bash

# MIDI Generator Controller Script
# ===============================
# Controller for the MIDI generation script using trained Markov models

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/generate_midi.py"
MODELS_DIR="$SCRIPT_DIR/markov_analysis_output"
CHORD_MODEL="$MODELS_DIR/chord_transitions.pkl"
NOTE_MODEL="$MODELS_DIR/note_transitions.pkl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

print_banner() {
    echo -e "${CYAN}"
    echo "=================================================================="
    echo "    MIDI Generator - Markov Chain Music Composer"
    echo "=================================================================="
    echo -e "${NC}"
}

print_separator() {
    echo -e "${CYAN}------------------------------------------------------------------${NC}"
}

# Check if virtual environment exists
check_venv_exists() {
    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        return 0
    else
        return 1
    fi
}

# Activate virtual environment
activate_venv() {
    log_step "Activating virtual environment..."
    
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run the main analysis first: ./run-markov.sh"
        exit 1
    fi
    
    # Source the activation script
    source "$VENV_DIR/bin/activate"
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        log_success "Virtual environment activated"
    else
        log_error "Failed to activate virtual environment"
        exit 1
    fi
}

# Check if model files exist
check_model_files() {
    log_step "Checking for trained models..."
    
    if [ ! -d "$MODELS_DIR" ]; then
        log_error "Models directory not found: $MODELS_DIR"
        log_info "Please run the analysis first: ./run-markov.sh"
        exit 1
    fi
    
    if [ ! -f "$CHORD_MODEL" ]; then
        log_error "Chord model not found: $CHORD_MODEL"
        log_info "Please run the analysis first: ./run-markov.sh"
        exit 1
    fi
    
    if [ ! -f "$NOTE_MODEL" ]; then
        log_error "Note model not found: $NOTE_MODEL"
        log_info "Please run the analysis first: ./run-markov.sh"
        exit 1
    fi
    
    # Get model file sizes for info
    chord_size=$(du -h "$CHORD_MODEL" | cut -f1)
    note_size=$(du -h "$NOTE_MODEL" | cut -f1)
    
    log_success "Found trained models:"
    log_info "  🎼 Chord model: $chord_size"
    log_info "  🎵 Note model: $note_size"
}

# Check if generator script exists
check_generator_script() {
    log_step "Checking generator script..."
    
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_error "Generator script not found: $PYTHON_SCRIPT"
        log_info "Please ensure generate_midi.py is in the same directory as this script"
        exit 1
    fi
    
    log_success "Found generator script: $PYTHON_SCRIPT"
}

# Interactive mode - prompt user for parameters
interactive_mode() {
    log_step "🎼 Interactive MIDI Generation Setup"
    echo ""
    
    # Output filename
    echo "📁 Output Settings:"
    read -p "Enter output filename [generated_song.mid]: " output_file
    output_file=${output_file:-"generated_song.mid"}
    
    # Duration
    echo ""
    echo "⏱️  Song Duration:"
    echo "   1. Short (3-4 minutes)"
    echo "   2. Medium (5-6 minutes) [default]"
    echo "   3. Long (7-8 minutes)"
    echo "   4. Custom"
    read -p "Choose duration (1-4) [2]: " duration_choice
    duration_choice=${duration_choice:-2}
    
    case $duration_choice in
        1) duration=3.5 ;;
        2) duration=5.5 ;;
        3) duration=7.5 ;;
        4) 
            read -p "Enter custom duration in minutes: " duration
            duration=${duration:-5.5}
            ;;
        *) duration=5.5 ;;
    esac
    
    # Tempo
    echo ""
    echo "🥁 Tempo (BPM):"
    echo "   1. Slow (80-100 BPM)"
    echo "   2. Medium (110-130 BPM) [default]"
    echo "   3. Fast (140-160 BPM)"
    echo "   4. Custom"
    read -p "Choose tempo (1-4) [2]: " tempo_choice
    tempo_choice=${tempo_choice:-2}
    
    case $tempo_choice in
        1) bpm=90 ;;
        2) bpm=120 ;;
        3) bpm=150 ;;
        4)
            read -p "Enter custom BPM: " bpm
            bpm=${bpm:-120}
            ;;
        *) bpm=120 ;;
    esac
    
    # Key signature
    echo ""
    echo "🎹 Key Signature:"
    echo "   1. Free (no key restrictions) [default]"
    echo "   2. Auto-detect and quantize to key"
    echo "   3. Force specific key"
    read -p "Choose key handling (1-3) [1]: " key_choice
    key_choice=${key_choice:-1}
    
    key_args=""
    case $key_choice in
        2) key_args="--quantize_key" ;;
        3) 
            echo ""
            echo "Available keys:"
            echo "   Major: C major, G major, D major, A major, E major, F major, etc."
            echo "   Minor: A minor, E minor, B minor, D minor, G minor, C minor, etc."
            read -p "Enter key name (e.g., 'C major', 'A minor'): " key_name
            if [ ! -z "$key_name" ]; then
                key_args="--key \"$key_name\""
            fi
            ;;
    esac
    
    # Polyphony
    echo ""
    echo "🎼 Musical Complexity:"
    echo "   1. Simple (2-3 notes per chord)"
    echo "   2. Medium (4-6 notes per chord) [default]"
    echo "   3. Complex (6-8 notes per chord)"
    read -p "Choose complexity (1-3) [2]: " poly_choice
    poly_choice=${poly_choice:-2}
    
    case $poly_choice in
        1) max_poly=3 ;;
        2) max_poly=6 ;;
        3) max_poly=8 ;;
        *) max_poly=6 ;;
    esac
    
    # Build command
    cmd_args=(
        "--output" "$output_file"
        "--duration" "$duration"
        "--bpm" "$bpm"
        "--max_polyphony" "$max_poly"
    )
    
    if [ ! -z "$key_args" ]; then
        eval "cmd_args+=($key_args)"
    fi
    
    # Show summary
    echo ""
    print_separator
    log_info "🎵 Generation Summary:"
    log_info "   📁 Output file: $output_file"
    log_info "   ⏱️  Duration: $duration minutes"
    log_info "   🥁 Tempo: $bpm BPM"
    log_info "   🎹 Key: $([ ! -z "$key_name" ] && echo "$key_name" || ([ "$key_choice" == "2" ] && echo "Auto-detect" || echo "Free"))"
    log_info "   🎼 Max notes per chord: $max_poly"
    print_separator
    
    # Confirm
    read -p "Generate MIDI with these settings? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Generation cancelled."
        exit 0
    fi
    
    # Run generator
    log_step "🚀 Starting MIDI generation..."
    echo ""
    
    python "$PYTHON_SCRIPT" "${cmd_args[@]}"
}

# Run generator with passed arguments
run_with_args() {
    log_step "🚀 Running MIDI generator with provided arguments..."
    echo ""
    
    python "$PYTHON_SCRIPT" "$@"
}

# Show available options
show_help() {
    echo "MIDI Generator Controller Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Modes:"
    echo "  (no args)               Interactive mode - guided setup"
    echo "  --help, -h              Show this help"
    echo "  --info                  Show model information"
    echo "  --quick                 Quick generation with defaults"
    echo "  [python args]           Pass arguments directly to generator"
    echo ""
    echo "Python Generator Arguments:"
    echo "  --output FILE           Output MIDI filename (default: generated_song.mid)"
    echo "  --duration MINUTES      Song duration in minutes (default: 5.5)"
    echo "  --bpm BPM              Beats per minute (default: 120)"
    echo "  --key KEY              Force specific key (e.g., 'C major', 'A minor')"
    echo "  --quantize_key         Auto-detect and quantize to most likely key"
    echo "  --max_polyphony N      Maximum simultaneous notes (default: 6)"
    echo "  --models_dir DIR       Directory containing model files"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Interactive mode"
    echo "  $0 --quick                           # Quick generation"
    echo "  $0 --output my_song.mid --bpm 140   # Custom tempo"
    echo "  $0 --key \"D minor\" --duration 4.0   # Specific key and length"
    echo "  $0 --quantize_key --max_polyphony 3  # Auto-key with simple chords"
}

# Show model information
show_info() {
    print_banner
    log_info "Checking model information..."
    
    if check_venv_exists; then
        activate_venv
    else
        log_error "Virtual environment not found"
        log_info "Run ./run-markov.sh first to create the environment and models"
        exit 1
    fi
    
    check_model_files
    
    # Try to load and show model stats
    python -c "
import pickle
import sys
import os

try:
    print('\\n📊 Model Statistics:')
    
    # Load chord model
    with open('$CHORD_MODEL', 'rb') as f:
        chord_model = pickle.load(f)
    print(f'   🎼 Chord types: {len(chord_model):,}')
    
    # Calculate total chord transitions
    total_chord_transitions = sum(sum(transitions.values()) for transitions in chord_model.values())
    print(f'   🔄 Chord transitions: {total_chord_transitions:,}')
    
    # Load note model
    with open('$NOTE_MODEL', 'rb') as f:
        note_model = pickle.load(f)
    print(f'   🎵 Note contexts: {len(note_model):,}')
    
    # Calculate total note transitions
    total_note_transitions = sum(sum(transitions.values()) for transitions in note_model.values())
    print(f'   🎹 Note transitions: {total_note_transitions:,}')
    
    # Most common chords
    chord_popularity = {}
    for chord, transitions in chord_model.items():
        chord_popularity[chord] = sum(transitions.values())
    
    top_chords = sorted(chord_popularity.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f'\\n🎭 Top 5 Most Common Chords:')
    for i, (chord, count) in enumerate(top_chords, 1):
        chord_name = ' + '.join(str(interval) for interval in chord)
        print(f'   {i}. [{chord_name}] - {count:,} occurrences')
        
except Exception as e:
    print(f'Error reading models: {e}')
    sys.exit(1)
"
}

# Quick generation with defaults
quick_generation() {
    log_step "🚀 Quick MIDI generation with default settings..."
    
    # Generate unique filename with timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    output_file="quick_song_${timestamp}.mid"
    
    log_info "Generating: $output_file (5.5 minutes, 120 BPM, auto-key)"
    echo ""
    
    python "$PYTHON_SCRIPT" --output "$output_file" --quantize_key
}

# Cleanup function
cleanup() {
    # Deactivate virtual environment if active
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Setup trap for cleanup on exit
trap cleanup EXIT

# Main execution
main() {
    print_banner
    
    # Check prerequisites
    check_venv_exists || {
        log_error "Virtual environment not found"
        log_info "Please run ./run-markov.sh first to set up the environment and train models"
        exit 1
    }
    
    activate_venv
    check_model_files
    check_generator_script
    
    print_separator
    log_success "✅ All prerequisites met! Ready to generate MIDI."
    print_separator
    
    # Run interactive mode
    interactive_mode
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --info)
        show_info
        exit 0
        ;;
    --quick)
        print_banner
        if check_venv_exists; then
            activate_venv
            check_model_files
            check_generator_script
            quick_generation
        else
            log_error "Environment not ready. Run ./run-markov.sh first."
            exit 1
        fi
        exit 0
        ;;
    "")
        # No arguments - run interactive mode
        main
        ;;
    *)
        # Arguments provided - pass them through to Python script
        print_banner
        if check_venv_exists; then
            activate_venv
            check_model_files
            check_generator_script
            print_separator
            run_with_args "$@"
        else
            log_error "Environment not ready. Run ./run-markov.sh first."
            exit 1
        fi
        ;;
esac
