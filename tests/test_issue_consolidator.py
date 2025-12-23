"""
Unit tests for GitHub Issue Consolidator.

Tests the core consolidation logic, output generation, and error handling.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents.issue_consolidator import (
    IssueConsolidator,
    IssueConsolidatorError,
    InvalidInputError
)
from agents.github_client import GitHubAPIClient, IssueNotFoundError
from agents.issue_models import GitHubIssue, IssueComment, ConsolidatedIssues


@pytest.fixture
def mock_client():
    """Create a mock GitHub API client."""
    client = MagicMock(spec=GitHubAPIClient)
    client.repo_owner = "test-owner"
    client.repo_name = "test-repo"
    return client


@pytest.fixture
def sample_issue():
    """Create a sample GitHub issue for testing."""
    return GitHubIssue(
        number=100,
        title="Parent Issue",
        body="Parent issue description",
        state="open",
        labels=["feature", "epic"],
        assignees=["user1"],
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 15, 9, 30, 0),
        comments=[
            IssueComment(
                author="user1",
                body="First comment",
                created_at=datetime(2024, 1, 5, 14, 20, 0)
            )
        ],
        url="https://github.com/test-owner/test-repo/issues/100"
    )


@pytest.fixture
def sample_child_issues():
    """Create sample child issues for testing."""
    return [
        GitHubIssue(
            number=101,
            title="Child Issue 1",
            body="Description 1",
            state="closed",
            labels=["backend"],
            assignees=["user2"],
            created_at=datetime(2024, 1, 5, 15, 0, 0),
            updated_at=datetime(2024, 1, 12, 16, 30, 0),
            comments=[],
            url="https://github.com/test-owner/test-repo/issues/101"
        ),
        GitHubIssue(
            number=102,
            title="Child Issue 2",
            body="Description 2",
            state="open",
            labels=["frontend"],
            assignees=["user3"],
            created_at=datetime(2024, 1, 5, 15, 15, 0),
            updated_at=datetime(2024, 1, 14, 13, 20, 0),
            comments=[],
            url="https://github.com/test-owner/test-repo/issues/102"
        )
    ]


class TestIssueConsolidator:
    """Test suite for IssueConsolidator class."""
    
    @pytest.mark.asyncio
    async def test_consolidate_success(self, mock_client, sample_issue, sample_child_issues):
        """Test successful issue consolidation."""
        # Setup mocks
        mock_client.fetch_issue = AsyncMock(return_value=sample_issue)
        mock_client.fetch_issues_batch = AsyncMock(return_value={
            101: sample_child_issues[0],
            102: sample_child_issues[1]
        })
        
        # Create consolidator and run
        consolidator = IssueConsolidator(mock_client)
        result = await consolidator.consolidate(
            parent_number=100,
            child_numbers=[101, 102],
            completed_numbers=[101]
        )
        
        # Assertions
        assert isinstance(result, ConsolidatedIssues)
        assert result.parent_issue.number == 100
        assert len(result.child_issues) == 2
        assert result.completed_issue_numbers == [101]
        assert result.completed_count == 1
        assert result.total_issues == 3
        
        # Verify API calls
        mock_client.fetch_issue.assert_called_once_with(100, include_comments=True)
        mock_client.fetch_issues_batch.assert_called_once_with([101, 102], include_comments=True)
    
    @pytest.mark.asyncio
    async def test_consolidate_with_missing_child(self, mock_client, sample_issue, sample_child_issues):
        """Test consolidation when some child issues are not found."""
        # Setup mocks - only return one child issue
        mock_client.fetch_issue = AsyncMock(return_value=sample_issue)
        mock_client.fetch_issues_batch = AsyncMock(return_value={
            101: sample_child_issues[0]
            # 102 is missing
        })
        
        consolidator = IssueConsolidator(mock_client)
        result = await consolidator.consolidate(
            parent_number=100,
            child_numbers=[101, 102],
            completed_numbers=[]
        )
        
        # Should only include found issues
        assert len(result.child_issues) == 1
        assert result.child_issues[0].number == 101
        assert 102 in result.metadata['missing_issues']
    
    @pytest.mark.asyncio
    async def test_consolidate_invalid_parent_number(self, mock_client):
        """Test error handling for invalid parent issue number."""
        consolidator = IssueConsolidator(mock_client)
        
        with pytest.raises(InvalidInputError, match="Parent issue number must be positive"):
            await consolidator.consolidate(
                parent_number=-1,
                child_numbers=[101, 102],
                completed_numbers=[]
            )
    
    @pytest.mark.asyncio
    async def test_consolidate_invalid_child_numbers(self, mock_client):
        """Test error handling for invalid child issue numbers."""
        consolidator = IssueConsolidator(mock_client)
        
        with pytest.raises(InvalidInputError, match="All child issue numbers must be positive"):
            await consolidator.consolidate(
                parent_number=100,
                child_numbers=[101, -5, 103],
                completed_numbers=[]
            )
    
    @pytest.mark.asyncio
    async def test_consolidate_parent_not_found(self, mock_client):
        """Test error handling when parent issue doesn't exist."""
        mock_client.fetch_issue = AsyncMock(
            side_effect=IssueNotFoundError("Issue not found")
        )
        
        consolidator = IssueConsolidator(mock_client)
        
        with pytest.raises(IssueNotFoundError):
            await consolidator.consolidate(
                parent_number=999999,
                child_numbers=[101],
                completed_numbers=[]
            )
    
    @pytest.mark.asyncio
    async def test_generate_json_output(self, mock_client, tmp_path):
        """Test JSON output generation."""
        # Create consolidated data
        consolidated = ConsolidatedIssues(
            parent_issue=GitHubIssue(
                number=100,
                title="Test Issue",
                body="Description",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                comments=[],
                url="https://github.com/test/test/issues/100"
            ),
            child_issues=[],
            completed_issue_numbers=[],
            metadata={"test": "data"}
        )
        
        # Generate output
        output_path = tmp_path / "test.json"
        consolidator = IssueConsolidator(mock_client)
        await consolidator.generate_json_output(consolidated, output_path)
        
        # Verify file exists and contains valid JSON
        assert output_path.exists()
        with open(output_path, 'r') as f:
            data = json.load(f)
        
        assert data['parent_issue']['number'] == 100
        assert data['parent_issue']['title'] == "Test Issue"
    
    @pytest.mark.asyncio
    async def test_generate_json_output_creates_directory(self, mock_client, tmp_path):
        """Test that JSON generation creates parent directories."""
        consolidated = ConsolidatedIssues(
            parent_issue=GitHubIssue(
                number=100,
                title="Test",
                body="",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                comments=[],
                url="https://github.com/test/test/issues/100"
            ),
            child_issues=[],
            completed_issue_numbers=[],
            metadata={}
        )
        
        # Output to non-existent directory
        output_path = tmp_path / "subdir" / "test.json"
        consolidator = IssueConsolidator(mock_client)
        await consolidator.generate_json_output(consolidated, output_path)
        
        assert output_path.exists()
    
    @pytest.mark.asyncio
    async def test_generate_markdown_output(self, mock_client, tmp_path):
        """Test Markdown output generation."""
        consolidated = ConsolidatedIssues(
            parent_issue=GitHubIssue(
                number=100,
                title="Test Issue",
                body="Description",
                state="open",
                labels=["feature"],
                assignees=["user1"],
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                updated_at=datetime(2024, 1, 15, 9, 30, 0),
                comments=[],
                url="https://github.com/test/test/issues/100"
            ),
            child_issues=[],
            completed_issue_numbers=[],
            metadata={
                'repo_owner': 'test-owner',
                'repo_name': 'test-repo',
                'fetch_time': '2024-01-15T14:30:00'
            }
        )
        
        output_path = tmp_path / "test.md"
        consolidator = IssueConsolidator(mock_client)
        
        # Mock template environment
        with patch.object(consolidator, 'template_env') as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "# Test Markdown Output"
            mock_env.get_template.return_value = mock_template
            
            await consolidator.generate_markdown_output(consolidated, output_path)
        
        # Verify file was created
        assert output_path.exists()
        with open(output_path, 'r') as f:
            content = f.read()
        assert "# Test Markdown Output" in content
    
    @pytest.mark.asyncio
    async def test_completion_percentage_calculation(self, mock_client, sample_issue):
        """Test completion percentage calculation."""
        child_issues = [
            GitHubIssue(
                number=i,
                title=f"Issue {i}",
                body="",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                comments=[],
                url=f"https://github.com/test/test/issues/{i}"
            )
            for i in range(101, 105)  # 4 child issues
        ]
        
        consolidated = ConsolidatedIssues(
            parent_issue=sample_issue,
            child_issues=child_issues,
            completed_issue_numbers=[101, 102],  # 2 completed
            metadata={}
        )
        
        assert consolidated.completed_count == 2
        assert consolidated.in_progress_count == 2
        assert consolidated.completion_percentage == 50.0


class TestConsolidatedIssuesModel:
    """Test ConsolidatedIssues model properties."""
    
    def test_total_issues(self, sample_issue):
        """Test total_issues property."""
        consolidated = ConsolidatedIssues(
            parent_issue=sample_issue,
            child_issues=[sample_issue, sample_issue],
            completed_issue_numbers=[],
            metadata={}
        )
        
        assert consolidated.total_issues == 3  # 1 parent + 2 children
    
    def test_completed_count_excludes_parent(self, sample_issue):
        """Test that completed_count only counts child issues."""
        consolidated = ConsolidatedIssues(
            parent_issue=sample_issue,
            child_issues=[
                GitHubIssue(
                    number=101,
                    title="Child",
                    body="",
                    state="closed",
                    labels=[],
                    assignees=[],
                    created_at=datetime(2024, 1, 1),
                    updated_at=datetime(2024, 1, 1),
                    comments=[],
                    url="https://github.com/test/test/issues/101"
                )
            ],
            completed_issue_numbers=[100, 101],  # Both parent and child
            metadata={}
        )
        
        # Should only count child issue 101, not parent 100
        assert consolidated.completed_count == 1
