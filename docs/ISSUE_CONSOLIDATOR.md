# GitHub Issue Consolidator

## Overview

The GitHub Issue Consolidator is a standalone module that fetches a parent GitHub issue along with its child issues, tracks completion status, and generates structured documentation in both JSON and Markdown formats. This tool is designed to help teams organize and document complex feature work or bug fixes that span multiple related issues.

### Features

- **Async API calls** for fast concurrent fetching of multiple issues
- **Comprehensive error handling** for rate limits, authentication, and missing issues
- **Flexible output formats** (JSON, Markdown, or both)
- **Rich terminal UI** with progress indicators and status messages
- **Comment inclusion** for full context on issue discussions
- **Completion tracking** to monitor progress across child issues

### Use Cases

- Consolidate epic issues with their sub-tasks
- Document feature implementation progress across multiple PRs
- Create comprehensive issue reports for stakeholders
- Generate input documentation for the Agent Orchestrator phase planner

## Installation

### Dependencies

All required dependencies are already included in `requirements.txt`:

```
httpx>=0.25.0
pydantic>=2.0.0
jinja2>=3.1.0
click>=8.1.0
rich>=13.0.0
```

### GitHub Token Setup

To avoid rate limiting and access private repositories, you need a GitHub personal access token:

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (for private repos) or `public_repo` (for public repos only)
4. Copy the generated token
5. Set environment variable:

**Windows (PowerShell):**
```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

**Windows (CMD):**
```cmd
set GITHUB_TOKEN=ghp_your_token_here
```

**Linux/Mac:**
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Alternatively, pass the token directly via `--token` flag.

## Usage

### Command Line Interface

#### Basic Usage

Consolidate a parent issue with child issues:

```bash
python -m agents.issue_consolidator \
  --parent 123 \
  --children 124,125,126 \
  --output issues \
  --repo owner/repo
```

This generates both `issues.json` and `issues.md`.

#### With Completed Issues

Mark specific child issues as completed:

```bash
python -m agents.issue_consolidator \
  --parent 123 \
  --children 124,125,126 \
  --completed 124,125 \
  --output issues \
  --repo owner/repo
```

#### JSON Output Only

Generate only JSON output:

```bash
python -m agents.issue_consolidator \
  --parent 123 \
  --children 124,125 \
  --output issues \
  --repo owner/repo \
  --format json
```

#### Markdown Output Only

Generate only Markdown output:

```bash
python -m agents.issue_consolidator \
  --parent 123 \
  --children 124,125 \
  --output issues \
  --repo owner/repo \
  --format md
```

#### With Token Flag

Provide token directly instead of environment variable:

```bash
python -m agents.issue_consolidator \
  --parent 123 \
  --children 124,125 \
  --output issues \
  --repo owner/repo \
  --token ghp_your_token_here
```

### Programmatic Usage

Use the consolidator directly in Python code:

```python
import asyncio
from pathlib import Path
from agents.issue_consolidator import IssueConsolidator
from agents.github_client import GitHubAPIClient

async def main():
    # Initialize client
    client = GitHubAPIClient(
        token="ghp_your_token_here",  # or None to use GITHUB_TOKEN env var
        repo_owner="owner",
        repo_name="repo"
    )
    
    # Initialize consolidator
    consolidator = IssueConsolidator(client)
    
    # Consolidate issues
    result = await consolidator.consolidate(
        parent_number=123,
        child_numbers=[124, 125, 126],
        completed_numbers=[124]
    )
    
    # Generate outputs
    await consolidator.generate_markdown_output(result, Path("issues.md"))
    await consolidator.generate_json_output(result, Path("issues.json"))
    
    # Access consolidated data
    print(f"Parent: {result.parent_issue.title}")
    print(f"Completed: {result.completed_count}/{len(result.child_issues)}")

asyncio.run(main())
```

## Configuration

### Environment Variables

- **GITHUB_TOKEN**: GitHub personal access token for API authentication

### CLI Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `--parent` | int | Yes | Parent issue number |
| `--children` | str | Yes | Comma-separated child issue numbers |
| `--completed` | str | No | Comma-separated completed issue numbers |
| `--output` | path | Yes | Output file path (without extension) |
| `--repo` | str | Yes | Repository in format `owner/name` |
| `--token` | str | No | GitHub token (defaults to GITHUB_TOKEN env var) |
| `--format` | choice | No | Output format: `md`, `json`, or `both` (default: `both`) |

## Output Formats

### JSON Output

Structured JSON file with complete issue data:

```json
{
  "parent_issue": {
    "number": 123,
    "title": "Parent Issue Title",
    "body": "Description...",
    "state": "open",
    "labels": ["feature", "epic"],
    "assignees": ["user1"],
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T00:00:00Z",
    "comments": [...],
    "url": "https://github.com/owner/repo/issues/123"
  },
  "child_issues": [...],
  "completed_issue_numbers": [124],
  "metadata": {
    "repo_owner": "owner",
    "repo_name": "repo",
    "fetch_time": "2024-01-15T10:30:00",
    "total_issues": 4,
    "completed_count": 1,
    "missing_issues": []
  }
}
```

### Markdown Output

Human-readable documentation with:
- Issue metadata and status
- Full descriptions and comments
- Completion tracking
- Visual indicators for completed issues
- Summary statistics

See `docs/examples/consolidated-issues-example.md` for a complete example.

## Error Handling

### Common Errors and Solutions

#### Authentication Error

**Error:** `GitHub authentication failed`

**Solution:** 
- Ensure GITHUB_TOKEN environment variable is set
- Or use `--token` flag with a valid token
- Verify token has correct permissions (repo/public_repo scope)

#### Rate Limit Error

**Error:** `Maximum retry attempts exceeded for rate limit`

**Solution:**
- Wait for rate limit to reset (check GitHub API rate limit status)
- Use an authenticated token (much higher rate limits)
- Reduce number of issues being fetched

#### Issue Not Found

**Error:** `Resource not found` or `Issue #XXX not found`

**Solution:**
- Verify issue number is correct
- Check issue exists in the specified repository
- Ensure token has access to the repository (for private repos)

#### Invalid Repository Format

**Error:** `Repository must be in format 'owner/name'`

**Solution:**
- Use format: `--repo owner/repo` (e.g., `--repo facebook/react`)
- Don't include `https://github.com/` in the repo parameter

## Integration with Orchestrator

### Using Consolidated Output as Input

The consolidated issue documentation can serve as input to the Agent Orchestrator's phase planner:

1. **Generate consolidated documentation:**
   ```bash
   python -m agents.issue_consolidator \
     --parent 123 \
     --children 124,125,126 \
     --output project-requirements \
     --repo owner/repo
   ```

2. **Use as orchestrator input:**
   ```bash
   python main.py --input-file project-requirements.md
   ```

The orchestrator will parse the consolidated issues and create appropriate execution phases.

### Automated Workflow

Create a script to automate the consolidation → orchestration workflow:

```python
import asyncio
from pathlib import Path
from agents.issue_consolidator import IssueConsolidator
from agents.github_client import GitHubAPIClient

async def consolidate_and_orchestrate():
    # Step 1: Consolidate issues
    client = GitHubAPIClient(
        token=None,  # Uses GITHUB_TOKEN env var
        repo_owner="owner",
        repo_name="repo"
    )
    
    consolidator = IssueConsolidator(client)
    result = await consolidator.consolidate(
        parent_number=123,
        child_numbers=[124, 125, 126],
        completed_numbers=[]
    )
    
    # Generate markdown for orchestrator
    requirements_path = Path("data/requirements.md")
    await consolidator.generate_markdown_output(result, requirements_path)
    
    print(f"Requirements generated: {requirements_path}")
    print("Next: Run orchestrator with this input")
    
asyncio.run(consolidate_and_orchestrate())
```

## API Reference

### Classes

#### GitHubAPIClient

Async client for GitHub REST API v3.

**Methods:**
- `__init__(token, repo_owner, repo_name)`: Initialize client
- `fetch_issue(issue_number, include_comments=True)`: Fetch single issue
- `fetch_issues_batch(issue_numbers, include_comments=True)`: Fetch multiple issues concurrently
- `fetch_issue_comments(issue_number)`: Fetch issue comments with pagination

#### IssueConsolidator

Core consolidation logic.

**Methods:**
- `__init__(client)`: Initialize with GitHubAPIClient
- `consolidate(parent_number, child_numbers, completed_numbers)`: Consolidate issues
- `generate_json_output(consolidated, output_path)`: Generate JSON file
- `generate_markdown_output(consolidated, output_path)`: Generate Markdown file

### Models

#### GitHubIssue

Pydantic model for a GitHub issue.

**Fields:**
- `number: int`: Issue number
- `title: str`: Issue title
- `body: Optional[str]`: Issue description
- `state: str`: Issue state (open/closed)
- `labels: List[str]`: Issue labels
- `assignees: List[str]`: Assigned users
- `created_at: datetime`: Creation timestamp
- `updated_at: datetime`: Last update timestamp
- `comments: List[IssueComment]`: Issue comments
- `url: str`: Issue URL

#### ConsolidatedIssues

Container for consolidated issue hierarchy.

**Fields:**
- `parent_issue: GitHubIssue`: Parent issue
- `child_issues: List[GitHubIssue]`: Child issues
- `completed_issue_numbers: List[int]`: Completed issue numbers
- `metadata: Dict[str, Any]`: Consolidation metadata

**Properties:**
- `total_issues: int`: Total issue count
- `completed_count: int`: Completed issue count
- `in_progress_count: int`: In-progress issue count
- `completion_percentage: float`: Completion percentage

### Exceptions

- **GitHubAPIError**: Base exception for API errors
- **RateLimitError**: Rate limit exceeded
- **AuthenticationError**: Authentication failure
- **IssueNotFoundError**: Issue not found (404)
- **InvalidInputError**: Input validation failure
- **IssueConsolidatorError**: General consolidator error

## Examples

See the following example files:
- `docs/examples/consolidated-issues-example.md`: Example Markdown output
- `docs/examples/consolidated-issues-example.json`: Example JSON output
- `docs/examples/issue_consolidator_usage.py`: Programmatic usage example

## Troubleshooting

### Issue: "Template not found"

**Cause:** Jinja2 template file missing from templates directory

**Solution:** Ensure `templates/consolidated_issues.md.j2` exists in the project

### Issue: Slow performance with many issues

**Cause:** Sequential API calls or rate limiting

**Solution:** 
- Issues are fetched concurrently by default
- Use authenticated token for higher rate limits
- Consider fetching issues in smaller batches

### Issue: Incomplete comment data

**Cause:** Comment pagination not fully processed

**Solution:** This is automatically handled; if issues persist, check network connectivity

## Future Enhancements

Potential improvements for future versions:
- Support for issue dependencies and blocking relationships
- Automatic detection of child issues from parent body
- Integration with GitHub Projects API
- Export to additional formats (PDF, HTML)
- Caching layer to reduce API calls
- Progress persistence for resuming interrupted fetches
