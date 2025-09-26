#!/bin/bash

# MIDI to JSON Converter Controller Script
# ========================================
# Controller for converting MIDI files to JSON format

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/midi_to_json.py"

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
    echo "    MIDI to JSON Converter - Musical Data Exporter"
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

# Check if converter script exists
check_converter_script() {
    log_step "Checking converter script..."
    
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_error "Converter script not found: $PYTHON_SCRIPT"
        log_info "Please ensure midi_to_json.py is in the same directory as this script"
        exit 1
    fi
    
    log_success "Found converter script: $PYTHON_SCRIPT"
}

# Run converter with arguments
run_converter() {
    log_step "🚀 Running MIDI to JSON converter..."
    echo ""
    
    python "$PYTHON_SCRIPT" "$@"
}

# Show help information
show_help() {
    echo "MIDI to JSON Converter Controller Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "This script converts MIDI files to structured JSON format for:"
    echo "  • Analysis and sharing of musical data"
    echo "  • Examination of generated AI music"
    echo "  • Musical pattern analysis"
    echo "  • Educational purposes"
    echo ""
    echo "Features:"
    echo "  • Single file or batch directory processing"
    echo "  • Musical analysis (key detection, chord extraction, rhythm analysis)"
    echo "  • Detailed statistics and metadata"
    echo "  • Human-readable JSON output"
    echo ""
    echo "Options:"
    echo "  --help, -h              Show this help"
    echo "  --info                  Show system information"
    echo ""
    echo "The script will prompt you for:"
    echo "  • Input path (MIDI file or directory)"
    echo "  • Output filename (optional)"
    echo ""
    echo "Examples:"
    echo "  $0                      # Interactive mode"
    echo "  $0 --help              # Show this help"
    echo ""
    echo "Generated JSON contains:"
    echo "  • File information (duration, tempo, size)"
    echo "  • Musical analysis (key, chords, rhythm)"
    echo "  • Note sequences and instrument data"
    echo "  • Statistical summaries"
}

# Show system information
show_info() {
    print_banner
    log_info "System Information:"
    log_info "  Operating System: $(uname -s)"
    log_info "  Architecture: $(uname -m)"
    log_info "  Script Directory: $SCRIPT_DIR"
    log_info "  Python Version: $(python3 --version 2>/dev/null || echo 'Not found')"
    log_info "  Current Time: $(date)"
    
    if check_venv_exists; then
        log_info "  Virtual Environment: Available at $VENV_DIR"
    else
        log_warning "  Virtual Environment: Not found"
        log_info "    Run ./run-markov.sh first to create the environment"
    fi
    
    if [ -f "$PYTHON_SCRIPT" ]; then
        log_info "  Converter Script: Available"
    else
        log_warning "  Converter Script: Missing"
    fi
}

# Test conversion with example
test_conversion() {
    log_step "Testing MIDI to JSON conversion..."
    
    # Look for any MIDI file in current directory for testing
    test_file=""
    for ext in "*.mid" "*.midi" "*.MID" "*.MIDI"; do
        if ls $ext 1> /dev/null 2>&1; then
            test_file=$(ls $ext | head -1)
            break
        fi
    done
    
    if [ -z "$test_file" ]; then
        log_warning "No MIDI files found in current directory for testing"
        log_info "Generate a MIDI file first with: ./run_generator.sh --quick"
        return 1
    fi
    
    log_info "Testing with file: $test_file"
    
    # Run conversion
    echo "Testing conversion..." | python "$PYTHON_SCRIPT" <<< "$test_file"
    
    log_success "Test conversion completed"
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
        log_info "Please run ./run-markov.sh first to set up the environment"
        exit 1
    }
    
    activate_venv
    check_converter_script
    
    print_separator
    log_success "✅ All prerequisites met! Ready to convert MIDI files."
    log_info "💡 This tool converts MIDI files to JSON format for analysis and sharing."
    print_separator
    
    # Run converter
    run_converter
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
    --test)
        print_banner
        if check_venv_exists; then
            activate_venv
            check_converter_script
            test_conversion
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
        log_error "Unknown option: $1"
        log_info "Use --help for usage information"
        exit 1
        ;;
esac
