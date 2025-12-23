"""
Specialized Agents

Copilot CLI interface, GitHub issue consolidator, and other
task-specific automation agents.
"""

from agents.issue_consolidator import IssueConsolidator
from agents.github_client import GitHubAPIClient
from agents.issue_models import GitHubIssue, ConsolidatedIssues

__version__ = "0.1.0"

__all__ = [
    'IssueConsolidator',
    'GitHubAPIClient',
    'GitHubIssue',
    'ConsolidatedIssues',
]
