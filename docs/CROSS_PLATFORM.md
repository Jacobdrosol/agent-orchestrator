# Cross-Platform Support Guide

## Overview

This guide provides instructions for adapting the Agent Orchestrator to run on Linux and macOS systems. The system is primarily developed for Windows but designed with cross-platform compatibility in mind.

## Platform Differences

### Path Separators

**Windows:** Uses backslashes (`\`)
**Linux/macOS:** Uses forward slashes (`/`)

**Solution:** Use `pathlib.Path` throughout the codebase:

```python
from pathlib import Path

# Cross-platform path construction
config_path = Path("config") / "orchestrator-config.yaml"
data_dir = Path("data") / "artifacts"
```

### Line Endings

**Windows:** CRLF (`\r\n`)
**Linux/macOS:** LF (`\n`)

**Solution:** Configure Git to handle line endings automatically:

```bash
# Set global git config
git config --global core.autocrlf input  # Linux/macOS
git config --global core.autocrlf true   # Windows

# Add to .gitattributes
* text=auto
*.py text eol=lf
*.yaml text eol=lf
*.sh text eol=lf
```

### Process Management

**Windows:** Different process spawning and signal handling
**Linux/macOS:** POSIX-compliant signals and process management

**Solution:** Use cross-platform libraries:

```python
import psutil
import signal
import sys

def terminate_process(pid: int):
    """Terminate process cross-platform"""
    try:
        process = psutil.Process(pid)
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
    except psutil.NoSuchProcess:
        pass
```

## Installation on Linux

### Prerequisites

1. **Python 3.10+**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.10 python3.10-venv python3-pip
   
   # Fedora/RHEL
   sudo dnf install python3.10
   
   # Arch Linux
   sudo pacman -S python310
   ```

2. **Git**
   ```bash
   # Ubuntu/Debian
   sudo apt install git
   
   # Fedora/RHEL
   sudo dnf install git
   
   # Arch Linux
   sudo pacman -S git
   ```

3. **Ollama**
   ```bash
   # Download and install
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Verify installation
   ollama --version
   
   # Start Ollama service
   sudo systemctl start ollama
   sudo systemctl enable ollama
   ```

### Setup Steps

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd "Agent Orchestrator"
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Ollama**
   ```bash
   # Pull required models
   ollama pull qwen2.5-coder:7b
   ollama pull deepseek-r1:8b
   
   # Test connection
   ollama list
   ```

5. **Setup configuration**
   ```bash
   cp config/orchestrator-config.yaml config/orchestrator-config.local.yaml
   nano config/orchestrator-config.local.yaml
   ```

6. **Run verification**
   ```bash
   python verify_patch_implementation.py
   ```

### System Service (Optional)

Create a systemd service for the orchestrator:

```bash
# Create service file
sudo nano /etc/systemd/system/orchestrator.service
```

```ini
[Unit]
Description=Agent Orchestrator Service
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/Agent Orchestrator
Environment="PATH=/path/to/Agent Orchestrator/venv/bin"
ExecStart=/path/to/Agent Orchestrator/venv/bin/python main.py --daemon
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable orchestrator.service
sudo systemctl start orchestrator.service

# Check status
sudo systemctl status orchestrator.service
```

## Installation on macOS

### Prerequisites

1. **Homebrew**
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Python 3.10+**
   ```bash
   brew install python@3.10
   ```

3. **Git** (usually pre-installed)
   ```bash
   git --version
   # If not installed:
   brew install git
   ```

4. **Ollama**
   ```bash
   # Download from https://ollama.com/download
   # Or use Homebrew
   brew install ollama
   
   # Start Ollama
   ollama serve &
   ```

### Setup Steps

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd "Agent Orchestrator"
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Ollama**
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama pull deepseek-r1:8b
   ollama list
   ```

5. **Setup configuration**
   ```bash
   cp config/orchestrator-config.yaml config/orchestrator-config.local.yaml
   nano config/orchestrator-config.local.yaml
   ```

6. **Run verification**
   ```bash
   python verify_patch_implementation.py
   ```

### LaunchAgent (Optional)

Create a LaunchAgent to start orchestrator on login:

```bash
# Create plist file
nano ~/Library/LaunchAgents/com.orchestrator.agent.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.orchestrator.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/Agent Orchestrator/venv/bin/python</string>
        <string>/path/to/Agent Orchestrator/main.py</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/Agent Orchestrator</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/orchestrator.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/orchestrator.error.log</string>
</dict>
</plist>
```

```bash
# Load the agent
launchctl load ~/Library/LaunchAgents/com.orchestrator.agent.plist

# Check status
launchctl list | grep orchestrator
```

## Cross-Platform Launcher Script

### Shell Script for Linux/macOS

**File:** `scripts/orchestrator.sh`

```bash
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
```

### Making the Script Executable

```bash
# Make executable
chmod +x scripts/orchestrator.sh

# Create symlink for easy access (optional)
sudo ln -s /path/to/Agent\ Orchestrator/scripts/orchestrator.sh /usr/local/bin/orchestrator

# Now you can run from anywhere:
orchestrator "Implement feature X"
```

## Code Adaptations

### 1. Path Handling

**Before:**
```python
config_path = "config\\orchestrator-config.yaml"
data_dir = "data\\artifacts"
```

**After:**
```python
from pathlib import Path

config_path = Path("config") / "orchestrator-config.yaml"
data_dir = Path("data") / "artifacts"
```

### 2. Environment Variables

```python
import os
from pathlib import Path

def get_data_dir() -> Path:
    """Get data directory, respecting XDG on Linux"""
    if os.name == 'nt':  # Windows
        return Path("data")
    else:  # Linux/macOS
        xdg_data_home = os.getenv('XDG_DATA_HOME')
        if xdg_data_home:
            return Path(xdg_data_home) / "orchestrator"
        else:
            return Path.home() / ".local" / "share" / "orchestrator"
```

### 3. Process Execution

```python
import subprocess
import sys

def run_command(cmd: str, shell: bool = False) -> subprocess.CompletedProcess:
    """Run command cross-platform"""
    if sys.platform == "win32":
        # Windows
        return subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
    else:
        # Linux/macOS
        return subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            executable="/bin/bash"
        )
```

### 4. File Permissions

```python
import os
import stat
from pathlib import Path

def make_executable(file_path: Path):
    """Make file executable (no-op on Windows)"""
    if os.name != 'nt':
        current_permissions = file_path.stat().st_mode
        file_path.chmod(current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

### 5. Database Path

```python
from pathlib import Path
import sys

def get_db_path() -> Path:
    """Get database path cross-platform"""
    if sys.platform == "win32":
        return Path("data") / "orchestrator.db"
    else:
        # Follow XDG Base Directory Specification
        data_dir = Path.home() / ".local" / "share" / "orchestrator"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "orchestrator.db"
```

## Testing Cross-Platform

### Using Docker

Test Linux compatibility without a Linux machine:

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install -r requirements.txt

# Run tests
CMD ["python", "verify_patch_implementation.py"]
```

```bash
# Build and run
docker build -t orchestrator-test .
docker run orchestrator-test
```

### Using Virtual Machines

1. **VirtualBox/VMware**: Install Ubuntu or macOS VM
2. **WSL2**: For Linux testing on Windows
3. **GitHub Actions**: Automated testing on all platforms

### Continuous Integration

**GitHub Actions workflow:**

```yaml
# .github/workflows/cross-platform-test.yml
name: Cross-Platform Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python verify_patch_implementation.py
```

## Troubleshooting

### Common Issues

#### 1. Permission Denied (Linux/macOS)

**Error:** `Permission denied: './orchestrator.sh'`

**Solution:**
```bash
chmod +x scripts/orchestrator.sh
```

#### 2. Python Not Found

**Error:** `python: command not found`

**Solution:**
```bash
# Use python3 explicitly
python3 main.py

# Or create alias
echo "alias python=python3" >> ~/.bashrc
source ~/.bashrc
```

#### 3. Ollama Connection Failed

**Error:** `Cannot connect to Ollama server`

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve &

# Or on systemd Linux
sudo systemctl start ollama
```

#### 4. Module Not Found

**Error:** `ModuleNotFoundError: No module named 'orchestrator'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### 5. Database Locked

**Error:** `database is locked`

**Solution:**
```bash
# Check for stale connections
lsof data/orchestrator.db  # Linux/macOS

# Remove lock files
rm data/orchestrator.db-wal
rm data/orchestrator.db-shm
```

## Platform-Specific Optimizations

### Linux

- Use `systemd` for service management
- Follow XDG Base Directory Specification
- Leverage inotify for file watching
- Use native package managers for dependencies

### macOS

- Use LaunchAgents for auto-start
- Follow macOS app bundle structure for GUI
- Leverage FSEvents for file watching
- Code signing for distribution

### Windows

- Use Task Scheduler for auto-start
- Follow Windows Registry conventions
- Leverage File System Watchers
- Use Windows Installer for distribution

## Best Practices

1. **Always use `pathlib.Path`** for file paths
2. **Test on all target platforms** before release
3. **Use CI/CD** for automated cross-platform testing
4. **Document platform-specific behavior** clearly
5. **Provide platform-specific installers** when possible
6. **Use cross-platform libraries** (pathlib, psutil, etc.)
7. **Handle line endings** properly in Git
8. **Test with different Python versions** (3.10, 3.11, 3.12)

## Migration Checklist

- [ ] Replace all hardcoded paths with `pathlib.Path`
- [ ] Update `.gitattributes` for line endings
- [ ] Test launcher script on Linux and macOS
- [ ] Update documentation with platform-specific instructions
- [ ] Create installers for each platform
- [ ] Setup CI/CD for cross-platform testing
- [ ] Verify Ollama integration on all platforms
- [ ] Test database operations on all platforms
- [ ] Validate file permissions on Unix systems
- [ ] Test process management on all platforms

## References

- [Python pathlib Documentation](https://docs.python.org/3/library/pathlib.html)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [Ollama Installation Guide](https://github.com/ollama/ollama)
- [Cross-Platform Python Guide](https://docs.python.org/3/library/os.html#os.name)
- [User Guide](USER_GUIDE.md)
- [Architecture](ARCHITECTURE.md)
