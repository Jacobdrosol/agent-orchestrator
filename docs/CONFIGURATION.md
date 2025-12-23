# Configuration Guide

## Overview

The Agent Orchestrator uses YAML-based configuration to control all aspects of orchestration behavior. Configuration can be customized per project with local overrides.

## Configuration Files

### File Precedence

1. **Default Configuration**: Built-in defaults in code
2. **Main Configuration**: `config/orchestrator-config.yaml`
3. **Local Overrides**: `config/orchestrator-config.local.yaml` (optional, git-ignored)

Local overrides are merged with the main configuration, allowing you to customize settings without modifying the tracked config file.

## Configuration Structure

### Execution Settings

Controls how phases are executed and retried:

```yaml
execution:
  max_retries: 3                    # Maximum retry attempts per phase
  retry_delay: 5.0                  # Seconds between retry attempts
  copilot_mode: "direct"            # "direct" or "branch"
  branch_prefix: "orchestrator/"    # Prefix for auto-generated branches
```

**max_retries**: Number of times to retry a phase before requiring manual intervention. Must be >= 1.

**retry_delay**: Cooldown period between retries to avoid rapid failures. Useful for transient errors.

**copilot_mode**: 
- `direct`: Make changes directly on the current branch
- `branch`: Create a new branch for each phase (safer, allows parallel work)

**branch_prefix**: When in branch mode, branches are named `{prefix}phase-{number}`.

### Findings Thresholds

Defines acceptable levels of findings before blocking phase completion:

```yaml
findings_thresholds:
  major: 0      # Build failures, critical errors
  medium: 0     # Test failures, security issues
  minor: 5      # Style issues, warnings
```

A phase cannot complete if findings exceed these thresholds. Set to high values to allow more leniency, or 0 for strict enforcement.

**Categories by Severity**:
- **Major**: Build failures, compilation errors, critical security issues
- **Medium**: Test failures, moderate security issues, missing documentation
- **Minor**: Linting warnings, style issues, typos

### Verification Settings

Controls which verification checks run after each Copilot execution. See [VERIFICATION.md](VERIFICATION.md) for detailed documentation.

```yaml
verification:
  # Build verification
  build_enabled: true
  build_command: "python -m pytest --collect-only"
  build_timeout: 300
  
  # Test verification
  test_enabled: true
  test_command: "python -m pytest tests/"
  test_timeout: 600
  test_output_format: "text"
  
  # Lint verification
  lint_enabled: true
  lint_command: "python -m pylint orchestrator/"
  lint_timeout: 120
  
  # Security scanning
  security_scan_enabled: false
  security_command: "bandit -r orchestrator/"
  security_timeout: 180
  
  # LLM-based spec validation
  spec_validation_enabled: true
  spec_validation_temperature: 0.3
  
  # Findings thresholds
  findings_thresholds:
    major: 0      # No major findings allowed
    medium: 0     # No medium findings allowed
    minor: 5      # Allow up to 5 minor findings
  
  # Custom tests
  custom_tests:
    - name: "integration_tests"
      command: "pytest tests/integration/"
      enabled: false
      working_directory: "."
      timeout: 300
      severity_on_failure: "medium"
```

**Verification Layers:**
1. **Build Check**: Ensures code compiles/imports without errors
2. **Test Check**: Runs test suite and detects failures
3. **Lint Check**: Enforces code style and quality standards
4. **Security Scan**: Detects vulnerabilities in dependencies and code
5. **Spec Validation**: LLM validates implementation against specification
6. **Custom Tests**: Project-specific validation checks

**Command Configuration:**
- Each check type has its own command, timeout, and enable flag
- Commands are executed in the repository root unless `working_directory` is specified
- Set command to appropriate tool for your project (pytest, npm test, dotnet test, etc.)

**Custom Tests**: Define project-specific verification steps. Each test requires:
- `name`: Unique identifier
- `command`: Shell command to execute
- `enabled`: Whether to run this test
- `working_directory`: (Optional) Directory to run command in
- `timeout`: (Optional) Maximum execution time in seconds
- `severity_on_failure`: (Optional) Severity level for findings (major/medium/minor)

**Findings Thresholds**: Phase verification fails if findings exceed these counts:
- `major`: Build failures, critical security issues, spec deviations
- `medium`: Test failures, incomplete requirements, medium security issues
- `minor`: Style violations, warnings, optional improvements

**Common Configurations:**

*Python Project:*
```yaml
verification:
  build_command: "python -m pytest --collect-only"
  test_command: "python -m pytest tests/ -v"
  lint_command: "flake8 . && black --check ."
  security_command: "bandit -r . -ll"
```

*Node.js Project:*
```yaml
verification:
  build_command: "npm run build"
  test_command: "npm test"
  lint_command: "npm run lint"
  security_command: "npm audit --audit-level=moderate"
```

*.NET Project:*
```yaml
verification:
  build_command: "dotnet build"
  test_command: "dotnet test"
  lint_command: "dotnet format --verify-no-changes"
  security_command: "dotnet list package --vulnerable"
```

### RAG System Settings

Controls the Retrieval-Augmented Generation system for code understanding:

```yaml
rag:
  chunk_size: 1000                  # Characters per code chunk
  chunk_overlap: 200                # Overlap between chunks
  max_retrieved_chunks: 20          # Max chunks per query
  semantic_search_enabled: true     # Vector similarity search
  symbol_search_enabled: true       # Symbol-based search
  index_on_startup: false           # Re-index on every run
```

**chunk_size**: Larger chunks provide more context but reduce precision. Recommended: 500-2000.

**chunk_overlap**: Prevents context loss at chunk boundaries. Should be 10-20% of chunk_size.

**max_retrieved_chunks**: More chunks = better context but slower processing and higher token usage.

**index_on_startup**: Set to `true` for maximum accuracy, but increases startup time significantly for large repos.

### Git Integration

Controls automatic git operations:

```yaml
git:
  auto_pull: true                   # Pull before starting
  auto_commit: false                # Commit after each phase
  commit_message_template: "Phase {phase_number}: {phase_title}\n\n{phase_intent}"
```

**auto_pull**: Recommended to avoid conflicts. Ensure working directory is clean before starting.

**auto_commit**: Useful for creating checkpoints. Disable if you prefer manual commits.

**commit_message_template**: Supports placeholders:
- `{phase_number}`: Phase number (1, 2, 3...)
- `{phase_title}`: Phase title
- `{phase_intent}`: Phase intent/description

### Artifact Management

Controls artifact storage and cleanup:

```yaml
artifacts:
  retention_days: 30                # Days to keep artifacts
  base_path: "data/artifacts"       # Base directory
  compress_old_artifacts: true      # Compress after 7 days
```

**retention_days**: Artifacts older than this are cleaned up. Set to 0 to keep forever.

**compress_old_artifacts**: Automatically compress old artifacts to save disk space.

### Logging Configuration

Controls logging behavior:

```yaml
logging:
  level: "INFO"                     # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file_path: "data/orchestrator.log"
  console_enabled: true             # Print to console
  max_file_size_mb: 50              # Rotate at this size
  backup_count: 5                   # Keep this many rotated logs
```

**level**: 
- `DEBUG`: Verbose, useful for troubleshooting
- `INFO`: Normal operation (recommended)
- `WARNING`: Only warnings and errors
- `ERROR`: Only errors

### Model Configuration

Models are defined in `models.yaml`, but you can override specific settings:

```yaml
models_path: "config/models.yaml"

model_overrides:
  planner_temperature: 0.3          # Lower = more deterministic
  spec_generator_temperature: 0.5
```

## Creating Local Overrides

To customize configuration without modifying tracked files:

1. Create `config/orchestrator-config.local.yaml`
2. Add only the settings you want to override:

```yaml
# Local overrides - not tracked in git
execution:
  max_retries: 5                    # More retries for testing

logging:
  level: "DEBUG"                    # Verbose logging for debugging

verification:
  build_enabled: false              # Skip builds during development
```

3. The local file is automatically merged with the main config

## Loading Configuration

### From Python Code

```python
from orchestrator import ConfigLoader, get_default_config

# Load from files
config = ConfigLoader.load_config(
    "config/orchestrator-config.yaml",
    "config/orchestrator-config.local.yaml"  # Optional
)

# Or use defaults
config = get_default_config()

# Access settings
print(f"Max retries: {config.execution.max_retries}")
print(f"Copilot mode: {config.execution.copilot_mode}")
```

### Saving Configuration

```python
ConfigLoader.save_config(config, "config/output.yaml")
```

## Validation

Configuration is automatically validated using Pydantic. Common validation errors:

**Invalid max_retries**:
```
ValueError: max_retries must be at least 1
```
Solution: Set `max_retries >= 1`

**Invalid copilot_mode**:
```
ValueError: copilot_mode must be one of {'direct', 'branch'}
```
Solution: Use only `"direct"` or `"branch"`

**Invalid log level**:
```
ValueError: Log level must be one of {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
```
Solution: Use valid log level names (case-insensitive)

**Negative threshold**:
```
ValueError: Threshold must be non-negative
```
Solution: Set threshold >= 0

## Examples

### Strict Quality Mode

For production environments with zero tolerance for issues:

```yaml
execution:
  max_retries: 1

findings_thresholds:
  major: 0
  medium: 0
  minor: 0

verification:
  build_enabled: true
  test_enabled: true
  lint_enabled: true
  security_scan_enabled: true
  spec_validation_enabled: true
```

### Development Mode

For rapid iteration during development:

```yaml
execution:
  max_retries: 5

findings_thresholds:
  major: 2
  medium: 5
  minor: 20

verification:
  build_enabled: true
  test_enabled: false              # Skip slow tests
  lint_enabled: false              # Skip linting
  security_scan_enabled: false
  spec_validation_enabled: true

logging:
  level: "DEBUG"
```

### Branch-Per-Phase Mode

For safer parallel development:

```yaml
execution:
  copilot_mode: "branch"
  branch_prefix: "feature/orchestrator-"

git:
  auto_commit: true
  commit_message_template: |
    Phase {phase_number}: {phase_title}
    
    {phase_intent}
    
    [Orchestrator Auto-commit]
```

## Troubleshooting

### Configuration Not Loading

**Issue**: Config file not found
```
ConfigError: Config file not found: config/orchestrator-config.yaml
```
**Solution**: Ensure file exists at the specified path

**Issue**: Invalid YAML syntax
```
ConfigError: Invalid YAML in config/orchestrator-config.yaml
```
**Solution**: Validate YAML syntax (indentation, quotes, colons)

### Validation Errors

**Issue**: Settings not taking effect
**Solution**: Check for typos in key names, ensure proper nesting

**Issue**: Override not working
**Solution**: Ensure local config file is in correct location and has proper structure

### Path Issues

**Issue**: Artifacts not being created
**Solution**: Check `artifacts.base_path` is writable

**Issue**: Log file not created
**Solution**: Check `logging.file_path` directory exists and is writable

## Best Practices

1. **Use local overrides**: Keep environment-specific settings in `.local.yaml` files
2. **Start conservative**: Begin with strict thresholds and relax as needed
3. **Enable all verification**: Use all verification checks in production
4. **Version control**: Track main config file, ignore local overrides
5. **Document changes**: Add comments explaining non-standard settings
6. **Test configuration**: Validate config loads correctly before running
7. **Review retention**: Adjust `retention_days` based on available disk space
