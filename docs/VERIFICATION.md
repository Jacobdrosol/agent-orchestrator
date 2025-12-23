# Verification System

The Agent Orchestrator includes a comprehensive verification engine that validates Copilot execution results through multiple layers of automated checks and LLM-based spec validation.

## Overview

After each Copilot execution, the verification system automatically runs to ensure:
- Code builds successfully
- Tests pass
- Linting standards are met
- No security vulnerabilities are introduced
- Implementation matches the original specification
- All acceptance criteria are completed

If verification fails, the system generates detailed findings and a feedback specification for automatic retry.

## Verification Layers

### 1. Build Check

**Purpose:** Verify the code compiles/imports without errors

**Configuration:**
```yaml
verification:
  build_enabled: true
  build_command: "python -m pytest --collect-only"
  build_timeout: 300
```

**Findings Generated:**
- **Major:** Build failures, compilation errors, import errors

**Example Use Cases:**
- Python: `python -m pytest --collect-only`, `python -m py_compile`
- Node.js: `npm run build`, `tsc --noEmit`
- .NET: `dotnet build`
- Go: `go build ./...`

### 2. Test Check

**Purpose:** Run test suite and detect failures

**Configuration:**
```yaml
verification:
  test_enabled: true
  test_command: "python -m pytest tests/"
  test_timeout: 600
  test_output_format: "text"  # or "junit", "json"
```

**Findings Generated:**
- **Medium:** Test failures, assertion errors
- **Minor:** Skipped tests (if configured)

**Supported Test Frameworks:**
- Python: pytest, unittest, nose
- Node.js: Jest, Mocha, Jasmine
- .NET: xUnit, NUnit, MSTest
- Go: go test

### 3. Lint Check

**Purpose:** Enforce code style and quality standards

**Configuration:**
```yaml
verification:
  lint_enabled: true
  lint_command: "python -m pylint orchestrator/"
  lint_timeout: 120
```

**Findings Generated:**
- **Minor:** Style violations, formatting issues
- **Medium:** Code quality issues, complexity warnings

**Supported Linters:**
- Python: pylint, flake8, black, ruff
- Node.js: eslint, prettier
- .NET: dotnet format
- Go: golint, gofmt

### 4. Security Scan

**Purpose:** Detect security vulnerabilities in dependencies and code

**Configuration:**
```yaml
verification:
  security_scan_enabled: true
  security_command: "bandit -r orchestrator/"
  security_timeout: 180
```

**Findings Generated:**
- **Major:** Critical/high-severity vulnerabilities
- **Medium:** Medium-severity vulnerabilities
- **Minor:** Low-severity issues

**Supported Scanners:**
- Python: bandit, safety
- Node.js: npm audit, snyk
- .NET: dotnet list package --vulnerable
- Go: gosec

### 5. Spec Validation (LLM-Based)

**Purpose:** Validate implementation against specification requirements

**Configuration:**
```yaml
verification:
  spec_validation_enabled: true
  spec_validation_temperature: 0.3
```

**Process:**
1. Extracts acceptance criteria checklist from spec
2. Gets git diff of changes
3. Sends to LLM with validation prompt
4. LLM analyzes compliance and checklist completion
5. Returns structured validation results

**Findings Generated:**
- **Major:** Significant deviations from spec
- **Medium:** Incomplete requirements, missing implementations
- **Minor:** Minor discrepancies

**LLM Response Format:**
```json
{
  "checklist_results": [
    {
      "item": "Implement user authentication",
      "completed": true,
      "evidence": "Added auth middleware and JWT tokens",
      "suggested_fix": null
    }
  ],
  "spec_compliance": {
    "compliant": true,
    "deviations": [],
    "missing_implementations": []
  },
  "overall_assessment": "All requirements met"
}
```

### 6. Custom Tests

**Purpose:** Run project-specific validation checks

**Configuration:**
```yaml
verification:
  custom_tests:
    - name: "database_migrations"
      command: "python manage.py makemigrations --check --dry-run"
      enabled: true
      working_directory: "."
      timeout: 60
      severity_on_failure: "medium"
    
    - name: "api_contract_validation"
      command: "npm run validate-openapi"
      enabled: true
      timeout: 30
      severity_on_failure: "major"
```

**Use Cases:**
- Database migration checks
- API contract validation
- Documentation generation
- Performance benchmarks
- Integration tests

## Findings System

### Severity Levels

**Major** (🔴)
- Build failures
- Critical security vulnerabilities
- Spec deviations
- Blocks phase completion

**Medium** (🟡)
- Test failures
- Incomplete requirements
- Medium security issues
- Should be fixed before proceeding

**Minor** (🔵)
- Style violations
- Warnings
- Nice-to-have improvements
- Doesn't block completion

### Findings Thresholds

Configure acceptable finding counts:

```yaml
verification:
  findings_thresholds:
    major: 0      # No major findings allowed
    medium: 0     # No medium findings allowed
    minor: 5      # Allow up to 5 minor findings
```

Phase verification fails if findings exceed thresholds.

### Finding Structure

Each finding includes:
- `id`: Unique identifier
- `execution_id`: Associated execution
- `severity`: major/medium/minor
- `category`: build/test/lint/security/spec_validation/custom
- `title`: Short description
- `description`: Detailed explanation
- `evidence`: Command output, error messages, file paths
- `suggested_fix`: Remediation steps
- `timestamp`: When detected

## Retry Loop

When verification fails:

1. **Generate Feedback Spec**
   - Includes original specification
   - Lists all findings with evidence
   - Provides suggested fixes
   - Identifies failed acceptance criteria

2. **Increment Retry Count**
   - Tracks number of attempts
   - Compares against `max_retries` config

3. **Re-execute with Feedback**
   - Copilot receives feedback spec instead of original
   - Can see what went wrong and how to fix it
   - Maintains context across retries

4. **Max Retries Handling**
   - If retries exhausted: trigger manual intervention
   - Phase paused for human review
   - Findings report available for debugging

## Findings Report

Generated after each verification in both Markdown and JSON formats:

### Markdown Report (`findings_report.md`)

```markdown
# Verification Findings Report

**Phase:** 3 - Implement Authentication
**Pass:** 1
**Status:** ❌ FAILED

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Major | 2 |
| 🟡 Medium | 3 |
| 🔵 Minor | 1 |

## Major Findings

| Category | Title | Evidence | Suggested Fix |
|----------|-------|----------|---------------|
| build | Import Error | ModuleNotFoundError: auth | Install auth package |
| test | Test Failures | 5 tests failed | Fix assertion errors |

## Recommendations

⚠️ Phase must be retried to address 2 critical issues.
```

### JSON Report (`Findings.json`)

Structured data for programmatic parsing, CI integration, and feedback specs:

```json
{
  "phase_number": 3,
  "phase_title": "Implement Authentication",
  "pass_number": 1,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "passed": false,
  "findings": [
    {
      "finding_id": "exec_001_build_1234567890",
      "execution_id": "exec_001",
      "severity": "major",
      "category": "build",
      "title": "Import Error",
      "description": "Build command failed with errors",
      "evidence": "ModuleNotFoundError: No module named 'auth'",
      "suggested_fix": "Install auth package using pip install auth",
      "resolved": false,
      "created_at": "2024-01-15T10:29:45.000Z"
    },
    {
      "finding_id": "exec_001_test_1234567891",
      "execution_id": "exec_001",
      "severity": "medium",
      "category": "test",
      "title": "Test Failures Detected",
      "description": "Found 5 test failure(s)",
      "evidence": "FAILED tests/test_auth.py::test_login - AssertionError",
      "suggested_fix": "Fix failing tests to ensure changes work correctly",
      "resolved": false,
      "created_at": "2024-01-15T10:29:50.000Z"
    }
  ],
  "findings_summary": {
    "major": 2,
    "medium": 3,
    "minor": 1
  },
  "failed_checklist_items": [
    "Implement user login endpoint",
    "Add JWT token generation"
  ],
  "spec_compliance": {
    "compliant": false,
    "deviations": [
      "Missing error handling for authentication failures"
    ],
    "missing_implementations": [
      "Token refresh endpoint not implemented"
    ],
    "overall_assessment": "Core authentication implemented but missing error handling and token refresh"
  },
  "checks_run": [
    "build",
    "test",
    "spec_validation"
  ],
  "execution_time": 45.2
}
```

**JSON Schema Fields:**
- `phase_number`, `phase_title`, `pass_number`: Phase identification
- `timestamp`: When verification completed (ISO 8601)
- `passed`: Boolean - overall verification result
- `findings`: Array of finding objects with full details
- `findings_summary`: Count by severity level
- `failed_checklist_items`: Acceptance criteria not met
- `spec_compliance`: LLM validation results (null if disabled)
- `checks_run`: List of verification checks executed
- `execution_time`: Total verification duration in seconds

**Use Cases:**
- **Feedback Specs**: Automatically incorporated into retry specifications
- **CI/CD**: Parse JSON to fail builds or generate reports
- **Metrics**: Track findings over time for quality trends
- **Dashboards**: Visualize verification results
- **Automation**: Trigger actions based on severity counts

## Configuration Best Practices

### Start Strict, Relax Later

```yaml
# Development phase - strict validation
verification:
  build_enabled: true
  test_enabled: true
  lint_enabled: true
  security_scan_enabled: true
  spec_validation_enabled: true
  findings_thresholds:
    major: 0
    medium: 0
    minor: 3

# Maintenance phase - more lenient
verification:
  build_enabled: true
  test_enabled: true
  lint_enabled: false  # Disable for quick fixes
  security_scan_enabled: true
  spec_validation_enabled: true
  findings_thresholds:
    major: 0
    medium: 2
    minor: 10
```

### Project-Specific Commands

**Python Django Project:**
```yaml
verification:
  build_command: "python manage.py check"
  test_command: "python manage.py test"
  lint_command: "flake8 . && black --check ."
  security_command: "bandit -r . -ll"
  custom_tests:
    - name: "migrations_check"
      command: "python manage.py makemigrations --check --dry-run"
      enabled: true
```

**Node.js Express API:**
```yaml
verification:
  build_command: "npm run build"
  test_command: "npm test"
  lint_command: "npm run lint"
  security_command: "npm audit --audit-level=moderate"
  custom_tests:
    - name: "openapi_validation"
      command: "npm run validate-schema"
      enabled: true
```

**.NET Core Application:**
```yaml
verification:
  build_command: "dotnet build"
  test_command: "dotnet test"
  lint_command: "dotnet format --verify-no-changes"
  security_command: "dotnet list package --vulnerable"
```

## Troubleshooting

### Verification Check Fails to Run

**Problem:** Check times out or command not found

**Solutions:**
- Verify command is in PATH
- Check working directory
- Increase timeout value
- Test command manually first

### False Positives

**Problem:** Checks fail but code is correct

**Solutions:**
- Adjust findings thresholds
- Disable specific checks temporarily
- Update check commands to be less strict
- Add custom tests with proper filtering

### LLM Validation Errors

**Problem:** Spec validation fails or produces errors

**Solutions:**
- Check LLM connectivity
- Verify prompts.yaml configuration
- Reduce spec complexity
- Ensure git diff is reasonable size

### Too Many Retries

**Problem:** Phase keeps retrying without progress

**Solutions:**
- Review feedback specs - are they clear?
- Check if fixes are being applied
- Manually review findings
- Adjust thresholds to be more lenient
- Increase max_retries if fixes are progressive

## Integration with CI/CD

The verification system can be used standalone:

```python
from orchestrator.verifier import PhaseVerifier, VerificationConfig

# In your CI pipeline
config = VerificationConfig({
    "build_enabled": True,
    "test_enabled": True,
    "lint_enabled": True,
})

verifier = PhaseVerifier(state_manager, llm_client, config, repo_path, prompts)
result = await verifier.verify_phase_execution(...)

if not result.passed:
    print(f"Verification failed: {result.findings_summary}")
    sys.exit(1)
```

## Disabling Verification

To skip verification (not recommended):

```yaml
verification:
  build_enabled: false
  test_enabled: false
  lint_enabled: false
  security_scan_enabled: false
  spec_validation_enabled: false
  findings_thresholds:
    major: 999
    medium: 999
    minor: 999
```

Or disable at runtime:
```python
executor.verification_config.build_enabled = False
```

## Future Enhancements

Planned features:
- Performance regression detection
- Code coverage thresholds
- Dependency update checks
- Documentation completeness validation
- Accessibility testing
- Load testing integration
