# GitHub Copilot CLI Integration

This document describes how the Agent Orchestrator integrates with GitHub Copilot CLI to execute phase implementations automatically.

## Overview

The Copilot CLI integration enables the orchestrator to leverage GitHub Copilot for automated code implementation. After generating a detailed phase specification, the orchestrator invokes Copilot CLI to execute the implementation, captures the results, and manages the workflow through verification and potential retries.

### Key Features

- **Automated Execution**: Copilot CLI executes phase specifications without manual intervention
- **Structured Prompts**: Phase specs, context, and findings are combined into comprehensive prompts
- **Result Capture**: JSON output from Copilot is parsed and stored in the state database
- **Error Handling**: Comprehensive error detection, logging, and retry logic
- **Branch Mode Support**: Optional branch-per-phase workflow with automatic commits
- **Artifact Management**: All inputs, outputs, and logs are saved for debugging

## Prerequisites

### 1. Install GitHub CLI

Download and install the GitHub CLI from [https://cli.github.com/](https://cli.github.com/)

**Windows:**
```powershell
winget install --id GitHub.cli
```

**macOS:**
```bash
brew install gh
```

**Linux:**
```bash
# Debian/Ubuntu
sudo apt install gh

# Fedora/RHEL
sudo dnf install gh
```

### 2. Authenticate with GitHub

```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

### 3. Install Copilot Extension

```bash
gh extension install github/gh-copilot
```

### 4. Verify Installation

```bash
gh copilot --version
```

You should see version information for the Copilot extension.

## Configuration

### Copilot Settings

Add or modify the `copilot` section in `config/orchestrator-config.yaml`:

```yaml
copilot:
  enabled: true                      # Enable/disable Copilot integration
  cli_path: "gh"                     # Path to gh CLI (default: use PATH)
  timeout: 600                       # Execution timeout in seconds (10 minutes)
  validate_on_startup: true          # Validate Copilot availability before execution
  capture_raw_output: true           # Save raw CLI output for debugging
  
  # Branch mode settings
  auto_commit: true                  # Automatically commit changes in branch mode
  commit_message_template: "Phase {phase_number}: {phase_title}\n\n{copilot_summary}"
  push_branches: false               # Push branches to remote
  
  # Error handling
  retry_on_timeout: true             # Retry if Copilot times out
  max_output_size_mb: 10             # Maximum output size to capture
```

### Execution Modes

Set the execution mode in `config/orchestrator-config.yaml`:

```yaml
execution:
  copilot_mode: "direct"  # or "branch"
```

**Direct Mode** (`"direct"`):
- Copilot executes directly in the current working directory
- Files are modified in place
- No automatic branching or commits
- Faster but less safe for production workflows

**Branch Mode** (`"branch"`):
- Creates a dedicated branch for each phase
- Copilot executes in the branch
- Changes are automatically committed
- Branch is merged on success or kept open on failure
- Safer for production workflows with Git history

## How It Works

### Execution Flow

```
1. Generate Phase Spec
   ├─ Retrieve repository context from RAG system
   ├─ Render phase spec template
   └─ Save spec to artifact directory

2. Render Copilot Prompt
   ├─ Load copilot_prompt.md.j2 template
   ├─ Include phase spec, findings (if retry), and context
   └─ Save prompt to artifact directory

3. Create Execution Record
   └─ Record execution attempt in database

4. Invoke Copilot CLI
   ├─ Execute: gh copilot suggest --target shell
   ├─ Send prompt as stdin
   ├─ Capture stdout/stderr with timeout
   └─ Parse JSON output

5. Process Results
   ├─ Save copilot_output.json
   ├─ Save copilot_raw.txt (if enabled)
   ├─ Update execution record
   └─ Register artifacts

6. Commit Changes (Branch Mode)
   ├─ Stage all changes
   ├─ Create commit with formatted message
   └─ Optionally push to remote

7. Continue or Retry
   ├─ If successful: Mark phase complete
   ├─ If failed: Check retry count
   └─ If max retries: Trigger manual intervention
```

### Prompt Structure

Copilot receives a structured prompt with the following sections:

1. **Phase Specification**: Complete spec with goals, constraints, files, and acceptance criteria
2. **Findings from Previous Pass**: (If retry) Issues found in verification
3. **Repository Context**: Relevant code snippets, symbols, and documentation
4. **Implementation Instructions**: Guidelines, execution mode, and expected output format

See `templates/copilot_prompt.md.j2` for the complete template.

### Expected Output Format

Copilot should return JSON output with this structure:

```json
{
  "files_modified": ["path/to/file1.py", "path/to/file2.py"],
  "files_created": ["path/to/new_file.py"],
  "changes_summary": "Brief description of what was implemented",
  "tests_added": ["test_function_1", "test_function_2"],
  "potential_issues": ["Any concerns or edge cases to review"],
  "completion_status": "complete"
}
```

**completion_status** values:
- `complete`: All requirements implemented successfully
- `partial`: Some requirements implemented, but not all
- `blocked`: Unable to proceed due to dependencies or issues

## Artifact Management

All Copilot-related files are saved to the artifact directory:

```
data/artifacts/{run_id}/{phase_id}/pass_{N}/
├── spec.md                    # Phase specification
├── copilot_prompt.md          # Rendered prompt sent to Copilot
├── copilot_output.json        # Parsed JSON response from Copilot
├── copilot_raw.txt            # Raw CLI output for debugging
├── execution_log.txt          # Execution timing and metadata
└── error.log                  # Error details if execution failed
```

These artifacts are:
- Saved permanently for audit and debugging
- Registered in the state database with metadata
- Accessible through the state manager API
- Included in run summaries and reports

## Error Handling

### Error Types

The system handles several error scenarios:

**1. Timeout (`CopilotErrorType.TIMEOUT`)**
- Copilot execution exceeds configured timeout
- Process is killed
- Partial output is saved
- Retry is attempted (if configured)

**2. Command Not Found (`CopilotErrorType.NOT_FOUND`)**
- `gh` CLI is not installed or not in PATH
- Error includes installation instructions
- No retry (requires manual fix)

**3. Authentication Error (`CopilotErrorType.AUTH_ERROR`)**
- GitHub authentication expired or invalid
- Error includes re-authentication instructions
- No retry (requires manual fix)

**4. Execution Error (`CopilotErrorType.EXECUTION_ERROR`)**
- Copilot CLI returned non-zero exit code
- Error message from stderr is captured
- Retry is attempted

**5. Parse Error (`CopilotErrorType.PARSE_ERROR`)**
- Copilot output is not valid JSON
- Fallback: Use raw text as summary
- Retry is attempted

### Retry Logic

Retries are controlled by `max_retries` in the execution config:

```yaml
execution:
  max_retries: 3
  retry_delay: 5.0
```

**Retry Behavior:**
- Transient errors (timeout, execution errors): Retry automatically
- Configuration errors (not found, auth): No retry, manual intervention required
- Each retry receives findings from the previous pass
- After max retries: Manual intervention is triggered

### Manual Intervention

When max retries are exceeded, the orchestrator:
1. Marks phase status as `paused`
2. Creates a `ManualIntervention` record
3. Logs detailed error information
4. Keeps branch open for manual review (in branch mode)

To resume:
```bash
# Review the error logs
cat data/artifacts/{run_id}/{phase_id}/pass_{N}/error.log

# Make manual fixes
# ...

# Resume orchestration
python -m orchestrator resume {run_id}
```

## Troubleshooting

### Copilot CLI Not Found

**Error:**
```
CopilotCLIError: GitHub CLI not found at 'gh'
```

**Solution:**
1. Install GitHub CLI: https://cli.github.com/
2. Verify installation: `gh --version`
3. Update config if installed in non-standard location:
   ```yaml
   copilot:
     cli_path: "/path/to/gh"
   ```

### Copilot Extension Not Installed

**Error:**
```
Copilot extension not installed
```

**Solution:**
```bash
gh extension install github/gh-copilot
gh copilot --version
```

### Authentication Failed

**Error:**
```
Error: Authentication failed
```

**Solution:**
```bash
gh auth login
# Follow prompts to authenticate
gh auth status  # Verify authentication
```

### Execution Timeout

**Error:**
```
Copilot execution timed out after 600s
```

**Solutions:**
1. Increase timeout in config:
   ```yaml
   copilot:
     timeout: 1200  # 20 minutes
   ```
2. Break phase into smaller sub-phases
3. Simplify phase specification

### Malformed JSON Output

**Issue:** Copilot returns text instead of JSON

**Behavior:** System extracts partial info from raw text and continues

**Solutions:**
1. Check prompt template clarity
2. Review Copilot output format instructions in `config/prompts.yaml`
3. Update prompt to emphasize JSON requirement

## Customization

### Custom Prompts

Modify `templates/copilot_prompt.md.j2` to customize the prompt structure.

**Available template variables:**
- `phase_spec`: Complete phase specification content
- `findings`: Findings from previous pass (if retry)
- `repo_context`: Repository context from RAG system
- `pass_number`: Current pass number
- `execution_mode`: "direct" or "branch"

### Custom Output Processing

Extend `CopilotCLIInterface` class to add custom output processing:

```python
from agents.copilot_interface import CopilotCLIInterface

class CustomCopilotInterface(CopilotCLIInterface):
    def _extract_json_from_output(self, output: str):
        # Custom JSON extraction logic
        result = super()._extract_json_from_output(output)
        # Add custom processing
        return result
```

Update executor initialization to use custom interface.

### Custom Commit Messages

Modify the commit message template in config:

```yaml
copilot:
  commit_message_template: |
    Phase {phase_number}: {phase_title}
    
    {copilot_summary}
    
    Pass: {pass_number}
    Execution ID: {execution_id}
    
    Co-authored-by: GitHub Copilot <copilot@github.com>
```

## Limitations

### Known Issues

1. **Copilot CLI API**: The `gh copilot` command is in active development, and the API may change
2. **Output Format**: Copilot doesn't always return JSON as requested; fallback to text parsing
3. **Context Size**: Large repositories may exceed context window; RAG system helps but isn't perfect
4. **Language Support**: Copilot works best with mainstream languages (Python, JavaScript, Go, etc.)
5. **Network Dependency**: Requires stable internet connection for Copilot API calls

### Workarounds

**Large Repositories:**
- Use more specific file lists in phase specs
- Break large phases into smaller ones
- Tune RAG system to retrieve more relevant context

**Inconsistent Output:**
- Enable `capture_raw_output` for debugging
- Review and refine prompt templates
- Add stricter output format instructions

**Timeout Issues:**
- Increase timeout for complex phases
- Simplify specifications
- Consider manual implementation for extremely complex phases

## Best Practices

1. **Start Small**: Test with simple phases before complex ones
2. **Review Outputs**: Check Copilot outputs in artifact directories regularly
3. **Use Branch Mode**: Safer for production workflows
4. **Monitor Retries**: High retry counts indicate spec or Copilot issues
5. **Validate Specs**: Ensure phase specs are clear and unambiguous
6. **Version Control**: Keep Git history clean with meaningful commit messages
7. **Artifact Retention**: Periodically clean old artifacts to save disk space
8. **Rate Limits**: Be aware of GitHub API rate limits with many phases

## Security Considerations

1. **Credentials**: Never commit GitHub tokens or credentials
2. **Code Review**: Always review Copilot-generated code before production
3. **Sensitive Data**: Be cautious with prompts containing sensitive information
4. **API Access**: Ensure Copilot subscription and access is properly managed
5. **Audit Trail**: All executions are logged for security audit purposes

## Support

For issues related to:
- **Agent Orchestrator**: Open an issue in the orchestrator repository
- **GitHub Copilot**: Visit https://github.com/github/copilot
- **GitHub CLI**: Visit https://github.com/cli/cli

## Future Enhancements

Planned improvements:
- [ ] Support for multiple LLM backends beyond Copilot
- [ ] Interactive mode with user approval before commits
- [ ] Better context management for large repositories
- [ ] Custom verification hooks for Copilot outputs
- [ ] Metrics dashboard for Copilot execution stats
- [ ] Streaming output for real-time progress
