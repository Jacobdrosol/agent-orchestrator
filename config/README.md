# Configuration Files

This directory contains YAML configuration files for the orchestrator.

## Files

- `orchestrator-config.yaml` - Main configuration file controlling all orchestration behavior
- `orchestrator-config.local.yaml` - Local overrides (optional, git-ignored)
- `models.yaml` - LLM model settings for different orchestration tasks

## Configuration Precedence

Configuration is loaded in the following order, with later files overriding earlier ones:

1. **Default Configuration** - Built-in defaults in code
2. **Main Configuration** - `orchestrator-config.yaml` (version controlled)
3. **Local Overrides** - `orchestrator-config.local.yaml` (git-ignored)

This allows you to:
- Share base configuration with your team via version control
- Customize settings for your local environment without conflicts
- Test different configurations without modifying tracked files

## Creating Local Overrides

To customize configuration for your environment:

1. Create `orchestrator-config.local.yaml` in this directory
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

## Documentation

For complete configuration reference, see:
- [Configuration Guide](../docs/CONFIGURATION.md) - Detailed documentation of all settings
- [State Management](../docs/STATE_MANAGEMENT.md) - How configuration affects state tracking

## Example Local Override

```yaml
# orchestrator-config.local.yaml
# Personal settings for development

execution:
  max_retries: 10                   # More lenient during testing
  copilot_mode: "branch"            # Use branches for safety

findings_thresholds:
  major: 2                          # Allow some failures
  medium: 5
  minor: 20

logging:
  level: "DEBUG"                    # Verbose output
  
verification:
  test_enabled: false               # Skip slow tests
  lint_enabled: false               # Skip linting
```
