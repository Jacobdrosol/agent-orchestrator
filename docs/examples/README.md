# Configuration Examples

This directory contains example configurations and sample documentation for the Agent Orchestrator.

## Configuration Files

### development-config.yaml

Development configuration optimized for local development and testing:

- **Relaxed thresholds**: Allows more issues during development
- **Verbose logging**: DEBUG level for detailed troubleshooting
- **Fast execution**: Smaller models and less strict verification
- **Manual git control**: No auto-commits or auto-pulls

**Usage:**
```bash
python main.py --config docs/examples/development-config.yaml "Your task"
```

**Key Features:**
- `max_retries: 2` - Faster feedback during development
- `logging.level: DEBUG` - Maximum verbosity
- `findings_thresholds.max_major: 1` - Relaxed for iteration
- `git.auto_commit: false` - Manual commit control
- `performance.enable_profiling: true` - Performance tracking

### production-config.yaml

Production configuration optimized for reliability and quality:

- **Strict thresholds**: No major issues allowed
- **Comprehensive verification**: All checks enabled
- **Security checks**: Always enabled in production
- **Monitoring and alerts**: Health checks and notifications

**Usage:**
```bash
python main.py --config docs/examples/production-config.yaml "Your task"
```

**Key Features:**
- `max_retries: 3` - Better resilience
- `findings_thresholds.max_major: 0` - Zero tolerance for major issues
- `verification.run_security_checks: true` - Security scanning
- `monitoring.enable_health_checks: true` - Health monitoring
- `database.backup_enabled: true` - Frequent backups

## Sample Issue Documentation

### sample-issue-doc.md

Markdown format issue documentation demonstrating comprehensive issue tracking:

**Contents:**
- Issue summary and metadata
- Detailed description and impact analysis
- Environment and reproduction steps
- Root cause analysis
- Proposed solutions with trade-offs
- Implementation plan with phases
- Testing strategy
- Validation criteria and timeline

**Use Cases:**
- Template for documenting issues
- Reference for issue analysis structure
- Example for AI agents to follow
- Training data for issue classification

### sample-issue-doc.json

JSON format of the same issue documentation for programmatic access:

**Structure:**
```json
{
  "issue_id": "#1234",
  "title": "...",
  "severity": "high",
  "root_cause": {...},
  "proposed_solutions": [...],
  "implementation_plan": {...}
}
```

**Use Cases:**
- Feeding issues to AI agents
- Integration with issue tracking systems
- Automated analysis and reporting
- API responses and data exchange

## Using These Examples

### Starting a New Project

1. **Choose your configuration base:**
   ```bash
   # For development
   cp docs/examples/development-config.yaml config/orchestrator-config.local.yaml
   
   # For production
   cp docs/examples/production-config.yaml config/orchestrator-config.local.yaml
   ```

2. **Customize for your needs:**
   - Edit model names for your Ollama setup
   - Adjust thresholds based on your quality requirements
   - Configure paths for your environment
   - Enable/disable features as needed

3. **Test your configuration:**
   ```bash
   python -c "from orchestrator import ConfigLoader; config = ConfigLoader.load_config('config/orchestrator-config.local.yaml'); print('Valid!')"
   ```

### Issue Documentation Workflow

1. **Create issue document from template:**
   ```bash
   cp docs/examples/sample-issue-doc.md docs/issues/issue-1234.md
   ```

2. **Fill in details:**
   - Update issue metadata
   - Add reproduction steps
   - Document investigation findings
   - Propose solutions

3. **Use in orchestration:**
   ```bash
   python main.py "Fix issue #1234 documented in docs/issues/issue-1234.md"
   ```

4. **Export as JSON if needed:**
   - Convert to JSON for API integration
   - Use for automated processing
   - Archive in issue tracking system

## Configuration Best Practices

### Development

1. **Use verbose logging** to understand behavior
2. **Enable profiling** to identify bottlenecks
3. **Relax thresholds** to iterate faster
4. **Disable auto-commits** to review changes
5. **Use smaller models** for faster feedback

### Production

1. **Enable all verification checks** for quality
2. **Set strict thresholds** to maintain standards
3. **Enable monitoring and alerts** for visibility
4. **Configure backups** for data safety
5. **Use production-grade models** for best results
6. **Enable security scanning** to prevent vulnerabilities
7. **Set up health checks** for reliability

### Configuration Management

1. **Never commit secrets** to version control
2. **Use local overrides** for sensitive settings
3. **Document configuration changes** in commits
4. **Test configuration** before deploying
5. **Version control** base configurations
6. **Keep production and development configs separate**

## Example Scenarios

### Scenario 1: Quick Development Iteration

```bash
# Use development config with minimal checks
python main.py \
  --config docs/examples/development-config.yaml \
  "Add new feature to user module"
```

**Result:** Fast execution with relaxed verification for rapid iteration.

### Scenario 2: Pre-Production Validation

```bash
# Use production config for thorough validation
python main.py \
  --config docs/examples/production-config.yaml \
  --dry-run \
  "Deploy authentication system"
```

**Result:** Full validation without execution to verify production readiness.

### Scenario 3: Issue Resolution

```bash
# Document issue then fix it
cat > docs/issues/memory-leak.md << 'EOF'
# Memory Leak Issue
[... issue details ...]
EOF

python main.py \
  --config docs/examples/development-config.yaml \
  "Fix memory leak documented in docs/issues/memory-leak.md"
```

**Result:** Context-aware fix based on detailed issue documentation.

### Scenario 4: Production Deployment

```bash
# Production deployment with all safeguards
python main.py \
  --config docs/examples/production-config.yaml \
  --verbose \
  "Deploy v2.0 features to production"
```

**Result:** Careful execution with full verification and logging.

## File Organization

```
docs/examples/
├── README.md                      # This file
├── development-config.yaml        # Development configuration
├── production-config.yaml         # Production configuration
├── sample-issue-doc.md           # Markdown issue template
└── sample-issue-doc.json         # JSON issue template
```

## Configuration Validation

Validate configurations before using them:

```python
from orchestrator import ConfigLoader

try:
    config = ConfigLoader.load_config("docs/examples/development-config.yaml")
    print("✓ Configuration is valid")
except Exception as e:
    print(f"✗ Configuration error: {e}")
```

## Customization Guide

### Adding Custom Verification

```yaml
verification:
  custom_tests:
    - name: "Your Custom Check"
      command: "your-tool --check"
      required: true  # Fail if this fails
```

### Adjusting Model Selection

```yaml
model_overrides:
  planner_model: "your-preferred-model"
  executor_model: "your-preferred-model"
  verifier_model: "your-preferred-model"
```

### Configuring Logging

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file_path: "your/log/path.log"
  enable_console: true
  console_level: "WARNING"
```

### Setting Thresholds

```yaml
findings_thresholds:
  max_major: 0     # Adjust based on project standards
  max_medium: 5    # Adjust based on project standards
  max_minor: 20    # Adjust based on project standards
```

## Troubleshooting

### Configuration Not Loading

**Problem:** Configuration file not found or invalid

**Solutions:**
- Check file path is correct
- Verify YAML syntax (no tabs, proper indentation)
- Validate with Python:
  ```python
  import yaml
  with open("config.yaml") as f:
      yaml.safe_load(f)
  ```

### Model Not Found

**Problem:** Specified model not available in Ollama

**Solutions:**
- Check available models: `ollama list`
- Pull required model: `ollama pull model-name`
- Use a different model in configuration

### Threshold Too Strict

**Problem:** Runs failing due to finding thresholds

**Solutions:**
- Review findings to understand issues
- Adjust thresholds if appropriate
- Fix underlying issues to meet standards

## Additional Resources

- [Main README](../../README.md) - Project overview
- [User Guide](../USER_GUIDE.md) - Complete usage guide
- [Configuration Reference](../CONFIGURATION.md) - All settings explained
- [Architecture Guide](../ARCHITECTURE.md) - System design
- [Contributing Guide](../CONTRIBUTING.md) - Development guidelines

## Questions?

If you have questions about these examples:
1. Check the [User Guide](../USER_GUIDE.md)
2. Review the [Configuration Reference](../CONFIGURATION.md)
3. Open a GitHub Discussion
4. Review existing issues

## Contributing Examples

Have a useful configuration or example? Please contribute!

1. Create your example file
2. Add documentation to this README
3. Submit a pull request
4. See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines
