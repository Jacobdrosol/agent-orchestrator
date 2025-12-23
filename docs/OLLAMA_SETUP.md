# Ollama Setup Guide

This guide will walk you through setting up Ollama locally for development with GPU acceleration on Windows.

## Prerequisites

- **Operating System**: Windows 10 22H2+ or Windows 11
- **GPU**: NVIDIA GPU with 12GB+ VRAM (RTX 4070 or higher recommended)
- **Disk Space**: 50GB+ free disk space for models
- **Access**: Administrator access for CUDA installation

## CUDA Toolkit Installation

1. **Download CUDA Toolkit**
   - Visit the NVIDIA developer site: https://developer.nvidia.com/cuda-downloads
   - Download CUDA Toolkit 12.3 or later for Windows

2. **Install CUDA**
   - Run the installer as administrator
   - Select "Express Installation" option
   - Wait for installation to complete (may take 10-15 minutes)

3. **Verify Installation**
   - Open PowerShell and run:
     ```powershell
     nvidia-smi
     ```
   - You should see GPU information and CUDA version displayed

4. **Set Environment Variable**
   - Open System Properties > Advanced > Environment Variables
   - Add new system variable:
     - Name: `OLLAMA_CUDA`
     - Value: `1`

5. **Restart Computer**
   - Restart your computer to ensure all changes take effect

## Ollama Installation

1. **Download Ollama**
   - Visit: https://ollama.com/download/windows
   - Download `OllamaSetup.exe`

2. **Install Ollama**
   - Run the installer (installs in user account, no admin required)
   - Follow the installation wizard
   - Installation typically takes 1-2 minutes

3. **Verify Installation**
   - Open PowerShell and run:
     ```powershell
     ollama --version
     ```
   - You should see the Ollama version number

4. **Confirm Service is Running**
   - Open Task Manager (Ctrl+Shift+Esc)
   - Check for "Ollama" service in the Processes tab

## Model Downloads

1. **Pull Qwen2.5-Coder 14B**
   ```powershell
   ollama pull qwen2.5-coder:14b-instruct-q4_K_M
   ```
   - Expected size: ~8GB
   - Download time: 10-30 minutes depending on connection speed

2. **Pull nomic-embed-text**
   ```powershell
   ollama pull nomic-embed-text
   ```
   - Expected size: ~274MB
   - Download time: 1-5 minutes

3. **Verify Models**
   ```powershell
   ollama list
   ```
   - You should see both models listed:
     - `qwen2.5-coder:14b-instruct-q4_K_M`
     - `nomic-embed-text`

## GPU Verification

1. **Test GPU Usage**
   ```powershell
   ollama run qwen2.5-coder:14b-instruct-q4_K_M --verbose "Hello"
   ```
   - Look for "Loading model using CUDA" in the output
   - The model should respond to your prompt

2. **Monitor GPU Usage**
   - In another PowerShell window, run:
     ```powershell
     nvidia-smi
     ```
   - Expected VRAM usage during model execution: 8-10GB for Qwen2.5-Coder
   - GPU utilization should show high percentage during generation

3. **Performance Check**
   - First token should appear within 1-3 seconds
   - Subsequent tokens should generate at 20-40 tokens/second on RTX 4070

## Memory Configuration

Configure Ollama to optimize memory usage for your setup:

1. **Set Environment Variables**
   - Open System Properties > Advanced > Environment Variables
   - Add these system variables:
     - `OLLAMA_MAX_LOADED_MODELS=2` (keeps both models in memory)
     - `OLLAMA_NUM_PARALLEL=1` (prevents concurrent requests overloading VRAM)

2. **Keep Models Loaded**
   - To keep models in memory indefinitely:
     - Variable: `OLLAMA_KEEP_ALIVE`
     - Value: `-1`
   - This reduces latency by avoiding model reload times

3. **Restart Ollama Service**
   - After setting environment variables, restart the Ollama service:
     ```powershell
     Stop-Process -Name ollama -Force
     ```
   - Ollama will restart automatically

## Troubleshooting

### GPU Not Detected
- **Symptoms**: Model runs slowly, no GPU usage shown
- **Solutions**:
  - Verify CUDA installation with `nvidia-smi`
  - Check `OLLAMA_CUDA=1` environment variable is set
  - Ensure NVIDIA drivers are up to date
  - Restart computer after setting environment variables

### Out of Memory Errors
- **Symptoms**: "Out of memory" or model fails to load
- **Solutions**:
  - Close other GPU-intensive applications
  - Reduce context length in generation parameters
  - Use smaller quantization (e.g., q4_0 instead of q4_K_M)
  - Consider using the 7B model instead of 14B

### Slow Performance
- **Symptoms**: Generation slower than 10 tokens/second
- **Solutions**:
  - Check GPU utilization with `nvidia-smi`
  - Ensure no other processes are using GPU heavily
  - Verify model is loaded on GPU (check verbose output)
  - Monitor GPU temperature for thermal throttling
  - Consider upgrading GPU drivers

### Model Download Failures
- **Symptoms**: Download stops or fails with network error
- **Solutions**:
  - Check available disk space (need 50GB+ free)
  - Verify network connectivity
  - Try downloading again (Ollama resumes partial downloads)
  - Check firewall settings aren't blocking Ollama

### Service Not Starting
- **Symptoms**: Ollama commands fail with connection error
- **Solutions**:
  - Check Windows Event Viewer for Ollama service errors
  - Verify no other service is using port 11434
  - Try manually starting Ollama from Start Menu
  - Reinstall Ollama if service is corrupted

## Performance Optimization

### Keep Models Loaded
- Set `OLLAMA_KEEP_ALIVE=-1` to keep frequently used models in memory
- Eliminates 5-10 second model loading time on each request
- Trade-off: Uses VRAM continuously

### Quantization Selection
- **Q4_K_M** (recommended): Best balance of quality and VRAM usage
- **Q4_0**: Slightly lower VRAM, minimal quality loss
- **Q5_K_M**: Higher quality, +2GB VRAM usage
- **Q8_0**: Highest quality, +4GB VRAM usage

### Temperature Monitoring
- Monitor GPU temperature with GPU-Z or MSI Afterburner
- Keep temperature below 85°C to avoid throttling
- Improve case airflow if consistently hitting thermal limits
- Consider custom fan curves for sustained workloads

### System RAM Considerations
- Windows may use virtual memory if system RAM is limited
- Minimum 16GB system RAM recommended
- 32GB+ ideal for running multiple models
- Increase virtual memory size if system RAM is < 32GB

## Alternative Model Options

### Smaller Models (Lower VRAM Requirements)

**Qwen2.5-Coder 7B**
```powershell
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```
- VRAM: ~4GB
- Performance: Faster responses (30-50 tokens/sec)
- Trade-off: Lower code quality, less context understanding

**DeepSeek-Coder 6.7B**
```powershell
ollama pull deepseek-coder:6.7b-instruct-q4_K_M
```
- VRAM: ~4GB
- Performance: Alternative architecture, fast generation
- Trade-off: Different strengths, may excel at specific tasks

### Model Selection Guidelines

- **Qwen2.5-Coder 14B**: Best for complex code generation, architecture planning
- **Qwen2.5-Coder 7B**: Good for quick tasks, code completion, simple refactoring
- **DeepSeek-Coder 6.7B**: Alternative when Qwen models unavailable
- **nomic-embed-text**: Standard for embeddings, keep loaded alongside coder model

### Testing Model Performance

Test each model with representative tasks:
```powershell
# Test code generation quality
ollama run qwen2.5-coder:14b-instruct-q4_K_M "Write a Python function to parse JSON"

# Compare with 7B model
ollama run qwen2.5-coder:7b-instruct-q4_K_M "Write a Python function to parse JSON"
```

Choose based on your quality vs. speed requirements.
