#!/usr/bin/env bash

# Agent Orchestrator Launcher Script for Linux/macOS
# This script handles environment setup and launches the orchestrator

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if Python 3 is available
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1)
        if [ "$PYTHON_VERSION" == "3" ]; then
            PYTHON_CMD="python"
        else
            print_message "$RED" "Error: Python 3 is required but not found"
            exit 1
        fi
    else
        print_message "$RED" "Error: Python is not installed"
        exit 1
    fi
    
    print_message "$GREEN" "✓ Found Python: $($PYTHON_CMD --version)"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        print_message "$YELLOW" "Virtual environment not found. Creating..."
        $PYTHON_CMD -m venv venv
        print_message "$GREEN" "✓ Virtual environment created"
    fi
}

# Activate virtual environment
activate_venv() {
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        print_message "$GREEN" "✓ Virtual environment activated"
    else
        print_message "$RED" "Error: Could not activate virtual environment"
        exit 1
    fi
}

# Install dependencies if needed
check_dependencies() {
    if [ ! -f "venv/.dependencies_installed" ]; then
        print_message "$YELLOW" "Installing dependencies..."
        pip install -q -r requirements.txt
        touch venv/.dependencies_installed
        print_message "$GREEN" "✓ Dependencies installed"
    fi
}

# Check if Ollama is running (optional)
check_ollama() {
    if command -v ollama &> /dev/null; then
        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            print_message "$GREEN" "✓ Ollama is running"
        else
            print_message "$YELLOW" "⚠ Ollama is installed but not running"
            print_message "$YELLOW" "  Start it with: ollama serve"
        fi
    else
        print_message "$YELLOW" "⚠ Ollama is not installed"
        print_message "$YELLOW" "  Install from: https://ollama.com/download"
    fi
}

# Main execution
main() {
    print_message "$GREEN" "=== Agent Orchestrator Launcher ==="
    
    # Perform checks
    check_python
    check_venv
    activate_venv
    check_dependencies
    check_ollama
    
    print_message "$GREEN" "\n=== Starting Orchestrator ===\n"
    
    # Run main.py with all passed arguments
    $PYTHON_CMD main.py "$@"
}

# Run main function with all script arguments
main "$@"
