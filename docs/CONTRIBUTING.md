# Contributing to Agent Orchestrator

## Welcome

Thank you for your interest in contributing to Agent Orchestrator! This guide will help you get started with contributing code, documentation, bug reports, and feature requests.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Development Workflow](#development-workflow)
5. [Coding Standards](#coding-standards)
6. [Testing Guidelines](#testing-guidelines)
7. [Documentation](#documentation)
8. [Pull Request Process](#pull-request-process)
9. [Issue Guidelines](#issue-guidelines)
10. [Community](#community)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of age, body size, disability, ethnicity, gender identity, level of experience, nationality, personal appearance, race, religion, or sexual identity.

### Expected Behavior

- Be respectful and considerate
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members
- Give and accept constructive feedback gracefully

### Unacceptable Behavior

- Harassment, discrimination, or trolling
- Personal attacks or inflammatory comments
- Publishing others' private information
- Spamming or excessive self-promotion
- Any conduct that could be considered inappropriate in a professional setting

## Getting Started

### Ways to Contribute

1. **Code Contributions**
   - Bug fixes
   - New features
   - Performance improvements
   - Refactoring

2. **Documentation**
   - Improving existing docs
   - Writing tutorials
   - Adding examples
   - Translating documentation

3. **Testing**
   - Writing test cases
   - Manual testing
   - Reporting bugs
   - Improving test coverage

4. **Design**
   - UI/UX improvements
   - Icons and assets
   - Architecture proposals

5. **Community**
   - Answering questions
   - Reviewing pull requests
   - Organizing events
   - Advocacy

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Ollama (for testing LLM integration)
- A code editor (VS Code recommended)

### Initial Setup

1. **Fork the repository**
   - Click "Fork" on GitHub
   - Clone your fork:
     ```bash
     git clone https://github.com/YOUR-USERNAME/Agent-Orchestrator.git
     cd Agent-Orchestrator
     ```

2. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/ORIGINAL-OWNER/Agent-Orchestrator.git
   ```

3. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   # Install production dependencies
   pip install -r requirements.txt
   
   # Install development dependencies
   pip install pytest pytest-asyncio pytest-cov black flake8 mypy
   ```

5. **Install pre-commit hooks (optional)**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

6. **Verify setup**
   ```bash
   python verify_patch_implementation.py
   pytest tests/
   ```

## Development Workflow

### Branch Strategy

We use a simplified Git Flow:

- `main`: Stable production-ready code
- `develop`: Integration branch for features
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes

### Creating a Feature Branch

```bash
# Update your local repository
git checkout develop
git pull upstream develop

# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes
# ...

# Commit your changes
git add .
git commit -m "feat: add your feature"

# Push to your fork
git push origin feature/your-feature-name
```

### Keeping Your Branch Updated

```bash
# Fetch upstream changes
git fetch upstream

# Rebase your branch on develop
git rebase upstream/develop

# If there are conflicts, resolve them and continue
git add .
git rebase --continue

# Force push to your fork (if you've already pushed)
git push origin feature/your-feature-name --force-with-lease
```

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some exceptions:

- **Line length**: 100 characters (not 79)
- **String quotes**: Use double quotes for strings, single quotes for string keys
- **Imports**: Use absolute imports, group by standard library, third-party, local

### Code Formatting

Use `black` for automatic formatting:

```bash
# Format entire codebase
black .

# Format specific file
black orchestrator/state.py

# Check without modifying
black --check .
```

### Linting

Use `flake8` for linting:

```bash
# Lint entire codebase
flake8 .

# Lint specific file
flake8 orchestrator/state.py

# Configuration in .flake8 or setup.cfg
```

### Type Hints

Always use type hints:

```python
from typing import Optional, List, Dict, Any
from pathlib import Path

async def create_run(
    task: str,
    config: Dict[str, Any],
    dry_run: bool = False
) -> Optional[str]:
    """Create a new orchestration run.
    
    Args:
        task: Task description
        config: Configuration dictionary
        dry_run: If True, only validate without executing
    
    Returns:
        Run ID if created, None if dry run
    
    Raises:
        ConfigError: If configuration is invalid
        StateError: If database operation fails
    """
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def process_document(file_path: Path, chunk_size: int = 1000) -> List[str]:
    """Process a document and split into chunks.
    
    This function reads a file, parses its content, and splits it into
    chunks of approximately the specified size.
    
    Args:
        file_path: Path to the document file
        chunk_size: Target size for each chunk in characters
    
    Returns:
        List of text chunks
    
    Raises:
        FileNotFoundError: If file_path does not exist
        ValueError: If chunk_size is not positive
    
    Example:
        >>> chunks = process_document(Path("doc.txt"), chunk_size=500)
        >>> len(chunks)
        10
    """
    pass
```

### Async/Await

Use async/await for I/O operations:

```python
# Good: Async database operations
async def get_run(self, run_id: str) -> Optional[RunState]:
    async with self.conn.execute(
        "SELECT * FROM runs WHERE id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return RunState.from_row(row) if row else None

# Bad: Blocking operation in async function
async def read_file(path: str) -> str:
    with open(path) as f:  # This blocks!
        return f.read()

# Good: Use aiofiles for async file I/O
import aiofiles

async def read_file(path: str) -> str:
    async with aiofiles.open(path) as f:
        return await f.read()
```

### Error Handling

Use specific exceptions with helpful messages:

```python
from orchestrator.exceptions import StateError, RunNotFoundError

# Good: Specific exception with context
async def update_run(self, run_id: str, status: str) -> None:
    if status not in ["planning", "executing", "completed", "failed"]:
        raise ValueError(f"Invalid status: {status}")
    
    result = await self.conn.execute(
        "UPDATE runs SET status = ? WHERE id = ?",
        (status, run_id)
    )
    
    if result.rowcount == 0:
        raise RunNotFoundError(f"Run not found: {run_id}")

# Bad: Generic exception without context
async def update_run(self, run_id: str, status: str) -> None:
    try:
        await self.conn.execute(
            "UPDATE runs SET status = ? WHERE id = ?",
            (status, run_id)
        )
    except Exception as e:
        raise Exception("Update failed")
```

## Testing Guidelines

### Writing Tests

- **Unit Tests**: Test individual functions/methods in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

### Test Structure

```python
import pytest
from orchestrator import StateManager
from orchestrator.exceptions import RunNotFoundError

class TestStateManager:
    """Tests for StateManager class."""
    
    @pytest.fixture
    async def state_manager(self):
        """Create a StateManager instance for testing."""
        manager = await StateManager.create(":memory:")
        yield manager
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_create_run(self, state_manager):
        """Test creating a new run."""
        # Arrange
        task = "Test task"
        plan = {"phases": []}
        
        # Act
        run_id = await state_manager.create_run(task, plan)
        
        # Assert
        assert run_id is not None
        run = await state_manager.get_run(run_id)
        assert run.task == task
        assert run.status == "planning"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_run(self, state_manager):
        """Test getting a run that doesn't exist."""
        # Act & Assert
        with pytest.raises(RunNotFoundError):
            await state_manager.get_run("nonexistent-id")
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=orchestrator --cov-report=html

# Run specific test file
pytest tests/test_state.py

# Run specific test
pytest tests/test_state.py::TestStateManager::test_create_run

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

### Test Coverage

Aim for at least 80% code coverage:

```bash
# Generate coverage report
pytest --cov=orchestrator --cov-report=term-missing

# View HTML report
pytest --cov=orchestrator --cov-report=html
open htmlcov/index.html
```

### Mocking

Use `unittest.mock` for mocking dependencies:

```python
from unittest.mock import Mock, AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_execute_with_llm():
    """Test execution with mocked LLM."""
    # Arrange
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = {"content": "Response"}
    
    executor = Executor(llm_client=mock_llm)
    
    # Act
    result = await executor.execute_phase("phase-1")
    
    # Assert
    assert result is not None
    mock_llm.chat.assert_called_once()
```

## Documentation

### Documentation Standards

- **Clear and Concise**: Use simple language
- **Examples**: Provide code examples
- **Up-to-Date**: Update docs with code changes
- **Comprehensive**: Cover all features and edge cases

### Markdown Guidelines

- Use ATX-style headers (`#`, `##`, `###`)
- Use fenced code blocks with language identifiers
- Use bullet lists for items without order
- Use numbered lists for sequential steps
- Include a table of contents for long documents

### API Documentation

Document all public APIs:

```python
class StateManager:
    """Manages orchestration state in SQLite database.
    
    This class provides async methods to create, update, and query
    orchestration runs, phases, executions, and findings.
    
    Attributes:
        db_path: Path to the SQLite database file
        conn: Active database connection
    
    Example:
        >>> manager = await StateManager.create("data/orchestrator.db")
        >>> run_id = await manager.create_run("Implement feature X", {})
        >>> await manager.close()
    """
    
    async def create_run(self, task: str, plan: dict) -> str:
        """Create a new orchestration run.
        
        Args:
            task: Description of the task to execute
            plan: Execution plan with phases
        
        Returns:
            Unique identifier for the created run
        
        Raises:
            DatabaseError: If database operation fails
            ValueError: If task is empty or plan is invalid
        """
        pass
```

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] Branch is up to date with develop

### Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(state): add export_run_summary method

Implement markdown and JSON export for run summaries.
Includes phase details, findings, and artifacts.

Closes #123
```

```
fix(rag): handle empty documents in chunking

Fixed IndexError when processing empty files.
Now returns empty list instead of raising exception.

Fixes #456
```

### Submitting Pull Request

1. **Push your branch to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open pull request on GitHub**
   - Base: `develop`
   - Compare: `your-feature-branch`
   - Fill in the PR template

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] All existing tests pass
   - [ ] Added new tests
   - [ ] Manual testing performed
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] No new warnings
   - [ ] Branch is up to date
   
   ## Related Issues
   Closes #123
   ```

4. **Respond to feedback**
   - Address review comments
   - Push updates to the same branch
   - Request re-review when ready

5. **Squash commits (if requested)**
   ```bash
   git rebase -i HEAD~n  # n = number of commits
   git push --force-with-lease
   ```

## Issue Guidelines

### Reporting Bugs

Use the bug report template:

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
1. Step 1
2. Step 2
3. See error

**Expected behavior**
What you expected to happen

**Environment:**
- OS: [e.g., Windows 11]
- Python version: [e.g., 3.10.5]
- Orchestrator version: [e.g., 0.1.0]

**Logs**
```
Relevant log output
```

**Additional context**
Any other relevant information
```

### Requesting Features

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
Clear description of desired functionality

**Describe alternatives you've considered**
Alternative solutions or features

**Additional context**
Mockups, examples, or references
```

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed
- `question`: Further information requested
- `wontfix`: Will not be worked on

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Requests**: Code review and collaboration

### Getting Help

1. **Check documentation**: Start with [USER_GUIDE.md](USER_GUIDE.md)
2. **Search issues**: Your question may already be answered
3. **Ask in discussions**: Post in GitHub Discussions
4. **Be specific**: Include error messages, logs, and context

### Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- Project documentation

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: Backwards-compatible new features
- **PATCH**: Backwards-compatible bug fixes

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`
- [ ] Tag created: `v1.2.3`
- [ ] Release notes written
- [ ] Artifacts built and tested

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

## Thank You!

Thank you for contributing to Agent Orchestrator! Your time and effort help make this project better for everyone.

## Questions?

If you have questions about contributing, feel free to:
- Open a GitHub Discussion
- Ask in an issue
- Review existing documentation

Happy coding! 🚀
