#!/bin/bash

# MIDI Polyphonic Markov Chain Analyzer - Controller Script
# ==========================================================
# This script handles environment setup and execution of the MIDI analyzer

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
MIN_PYTHON_VERSION="3.7"

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
    echo "    MIDI Polyphonic Markov Chain Analyzer - Setup & Runner"
    echo "=================================================================="
    echo -e "${NC}"
}

print_separator() {
    echo -e "${CYAN}------------------------------------------------------------------${NC}"
}

# Check if Python is available and meets minimum version
check_python() {
    log_step "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        log_info "Please install Python 3.7 or higher and try again"
        exit 1
    fi
    
    # Get Python version
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_info "Found Python $PYTHON_VERSION"
    
    # Check minimum version
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
        log_success "Python version meets requirements (>= $MIN_PYTHON_VERSION)"
    else
        log_error "Python version $PYTHON_VERSION is too old (minimum: $MIN_PYTHON_VERSION)"
        exit 1
    fi
    
    # Special handling for Python 3.13+
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 13) else 1)"; then
        log_info "Detected Python 3.13+: Will ensure setuptools is installed for pkg_resources compatibility"
    fi
}

# Check if virtual environment exists
check_venv_exists() {
    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        return 0
    else
        return 1
    fi
}

# Create virtual environment
create_venv() {
    log_step "Creating Python virtual environment..."
    
    if check_venv_exists; then
        log_info "Virtual environment already exists at: $VENV_DIR"
        return 0
    fi
    
    log_info "Creating new virtual environment at: $VENV_DIR"
    
    if python3 -m venv "$VENV_DIR"; then
        log_success "Virtual environment created successfully"
    else
        log_error "Failed to create virtual environment"
        log_info "You may need to install python3-venv:"
        log_info "  Ubuntu/Debian: sudo apt install python3-venv"
        log_info "  macOS: Should be included with Python"
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    log_step "Activating virtual environment..."
    
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        log_error "Virtual environment activation script not found"
        exit 1
    fi
    
    # Source the activation script
    source "$VENV_DIR/bin/activate"
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        log_success "Virtual environment activated: $VIRTUAL_ENV"
    else
        log_error "Failed to activate virtual environment"
        exit 1
    fi
}

# Check if requirements file exists
check_requirements_file() {
    log_step "Checking requirements file..."
    
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        log_error "Requirements file not found: $REQUIREMENTS_FILE"
        log_info "Please ensure requirements.txt is in the same directory as this script"
        exit 1
    fi
    
    log_success "Found requirements file: $REQUIREMENTS_FILE"
}

# Install or update dependencies
install_dependencies() {
    log_step "Installing/updating dependencies..."
    
    # Upgrade pip first
    log_info "Upgrading pip..."
    if python -m pip install --upgrade pip; then
        log_success "Pip upgraded successfully"
    else
        log_warning "Failed to upgrade pip, continuing anyway..."
    fi
    
    # Install requirements
    log_info "Installing packages from requirements.txt..."
    if python -m pip install -r "$REQUIREMENTS_FILE"; then
        log_success "All dependencies installed successfully"
    else
        log_error "Failed to install dependencies"
        log_info "Try running manually: pip install -r requirements.txt"
        exit 1
    fi
}

# Verify critical dependencies
verify_dependencies() {
    log_step "Verifying critical dependencies..."
    
    critical_packages=(
        "setuptools"
        "pretty_midi"
        "numpy"
        "tqdm"
    )
    
    verification_failed=false
    
    for package in "${critical_packages[@]}"; do
        log_info "Checking $package..."
        if python -c "
import sys
try:
    import $package
    if hasattr($package, '__version__'):
        print(f'✓ $package version: {$package.__version__}')
    else:
        print(f'✓ $package imported successfully')
except ImportError as e:
    print(f'✗ Import failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
            log_success "$package is available"
        else
            log_error "$package is not available after installation"
            verification_failed=true
        fi
    done
    
    if [ "$verification_failed" = true ]; then
        log_error "Some dependencies failed verification"
        log_info "This might indicate compatibility issues with Python 3.13+"
        log_info "Try cleaning and reinstalling:"
        log_info "  ./run-markov.sh --clean"
        log_info "  ./run-markov.sh"
        exit 1
    fi
    
    log_success "All critical dependencies verified successfully"
}

# Check if main Python script exists
check_python_script() {
    log_step "Checking main Python script..."
    
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_error "Main Python script not found: $PYTHON_SCRIPT"
        log_info "Please ensure main.py is in the same directory as this script"
        exit 1
    fi
    
    log_success "Found main script: $PYTHON_SCRIPT"
}

# Run the Python analyzer
run_analyzer() {
    log_step "Starting MIDI Polyphonic Markov Chain Analyzer..."
    print_separator
    
    # Execute the Python script
    if python "$PYTHON_SCRIPT"; then
        print_separator
        log_success "Analysis completed successfully!"
    else
        exit_code=$?
        print_separator
        log_error "Analysis failed with exit code: $exit_code"
        
        if [ $exit_code -eq 1 ]; then
            log_info "This might be due to missing MIDI files or other input issues"
            log_info "Check that your MIDI file path is correct and accessible"
        fi
        
        exit $exit_code
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    # Deactivate virtual environment if active
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Setup trap for cleanup on exit
trap cleanup EXIT

# Display system information
show_system_info() {
    log_step "System Information:"
    log_info "Operating System: $(uname -s)"
    log_info "Architecture: $(uname -m)"
    log_info "Script Directory: $SCRIPT_DIR"
    log_info "Python Version: $(python3 --version 2>/dev/null || echo 'Not found')"
    log_info "Current Time: $(date)"
}

# Main execution function
main() {
    print_banner
    
    log_info "Initializing MIDI Analyzer environment setup..."
    show_system_info
    print_separator
    
    # Step 1: Check Python
    check_python
    
    # Step 2: Check required files
    check_requirements_file
    check_python_script
    
    # Step 3: Setup virtual environment
    create_venv
    activate_venv
    
    # Step 4: Install dependencies
    install_dependencies
    verify_dependencies
    
    # Step 5: Final environment check
    print_separator
    log_success "Environment setup complete!"
    log_info "Virtual Environment: $VIRTUAL_ENV"
    log_info "Python Executable: $(which python)"
    log_info "Python Version: $(python --version)"
    
    # Step 6: Run the analyzer
    print_separator
    log_step "Environment ready! Launching MIDI analyzer..."
    echo ""
    
    run_analyzer
    
    # Final success message
    print_separator
    log_success "MIDI analysis pipeline completed successfully!"
    log_info "Check the 'markov_analysis_output' directory for results"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "MIDI Polyphonic Markov Chain Analyzer - Controller Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --setup-only        Only setup environment, don't run analyzer"
        echo "  --clean             Remove virtual environment and exit"
        echo "  --info              Show system and environment information"
        echo "  --test-deps         Test dependency imports without running analyzer"
        echo ""
        echo "This script will:"
        echo "  1. Check Python installation"
        echo "  2. Create virtual environment if needed"
        echo "  3. Install required dependencies"
        echo "  4. Verify installation"
        echo "  5. Run the MIDI analyzer"
        echo ""
        exit 0
        ;;
    --setup-only)
        print_banner
        log_info "Setup-only mode: Will prepare environment but not run analyzer"
        print_separator
        
        check_python
        check_requirements_file
        check_python_script
        create_venv
        activate_venv
        install_dependencies
        verify_dependencies
        
        print_separator
        log_success "Environment setup complete!"
        log_info "To run the analyzer manually:"
        log_info "  source $VENV_DIR/bin/activate"
        log_info "  python $PYTHON_SCRIPT"
        exit 0
        ;;
    --clean)
        log_info "Cleaning up virtual environment..."
        if [ -d "$VENV_DIR" ]; then
            rm -rf "$VENV_DIR"
            log_success "Virtual environment removed: $VENV_DIR"
        else
            log_info "No virtual environment found to clean"
        fi
        exit 0
        ;;
    --test-deps)
        print_banner
        log_info "Testing dependency imports..."
        
        if check_venv_exists; then
            activate_venv
            verify_dependencies
            log_success "All dependencies working correctly!"
        else
            log_error "No virtual environment found. Run setup first."
            exit 1
        fi
        exit 0
        ;;
    --info)
        print_banner
        show_system_info
        
        if check_venv_exists; then
            log_info "Virtual Environment: Present at $VENV_DIR"
        else
            log_info "Virtual Environment: Not found"
        fi
        
        if [ -f "$REQUIREMENTS_FILE" ]; then
            log_info "Requirements File: Found"
        else
            log_info "Requirements File: Missing"
        fi
        
        if [ -f "$PYTHON_SCRIPT" ]; then
            log_info "Main Script: Found"
        else
            log_info "Main Script: Missing"
        fi
        
        exit 0
        ;;
    "")
        # Default: run full setup and analysis
        main
        ;;
    *)
        log_error "Unknown option: $1"
        log_info "Use --help for usage information"
        exit 1
        ;;
esac
